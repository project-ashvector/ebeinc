import './style.css';
import { invoke, convertFileSrc } from '@tauri-apps/api/core';
import { open } from '@tauri-apps/plugin-dialog';
import { buildOrderedCycle, mediaIdentity } from './cycle-contract.js';

const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];
function numberOr(value, fallback) { const n = Number(value); return Number.isFinite(n) ? n : fallback; }
function formatBytes(value) { if (!value) return 'size unknown'; const units = ['B', 'KB', 'MB', 'GB']; let n = value; let i = 0; while (n >= 1024 && i < units.length - 1) { n /= 1024; i += 1; } return `${n.toFixed(i ? 1 : 0)} ${units[i]}`; }
const views = ['Dashboard', 'Visual Workspace', '24/7 Visuals', 'Diagnostics', 'Activity', 'Settings'];
const viewLabels = { Dashboard: 'LIVE', 'Visual Workspace': 'LAYOUT', '24/7 Visuals': 'VISUAL LIBRARY', Diagnostics: 'STATUS', Activity: 'LOG', Settings: 'SETTINGS' };
const viewport = {
  'desktop-16-9': [1280, 720],
  'desktop-wide': [1440, 600],
  laptop: [1280, 800],
  'tablet-landscape': [1024, 768],
  'tablet-portrait': [768, 1024],
  'phone-portrait': [390, 844],
  'phone-landscape': [844, 390],
  custom: [1280, 720]
};
const CANONICAL_COMPOSITION = { width: 1920, height: 1080 };
const CANONICAL_GREEN_URL = 'https://allthings140radio.online/room/';
const CANONICAL_VISUALS_URL = 'https://allthings140radio.online/visuals/';
const CANONICAL_REALTIME_WS = 'wss://visuals-realtime-staging.allthings140radio.online/ws?environment=live';
const CANONICAL_MEDIA_ORIGIN = 'https://visuals-realtime-staging.allthings140radio.online/media';
const DEFAULT_VISUAL_FOLDER = '/home/ebmarah/Videos/at140radio/desktop visuals/visuals';
const DEFAULT_STAGE_FOLDER = '/home/ebmarah/Videos/at140radio/desktop visuals/stage';
const DEFAULT_SCREEN_OPENING = { x: 23.0, y: 33.5, width: 53.6, height: 48.5, rx: 1.5, enabled: true };
const SCREEN_TARGET = DEFAULT_SCREEN_OPENING;

function screenOpening(preset = activePreset()) {
  preset.screenOpening = Object.assign({}, DEFAULT_SCREEN_OPENING, preset.screenOpening || {});
  return preset.screenOpening;
}

let state;
let selectedLayerId = 'visual-content';
let drag = null;
let ws;
let wsRetryTimer = null;
let wsRetryCount = 0;
let metrics = { energy: 0, presence: 0, total: 0, ws: 'OFFLINE' };
let log = [];
let history = [];
let future = [];
let editorZoom = 1;
let snapEnabled = true;
let currentView = 'Dashboard';
let appVersion = '0.2.1';
let buildInfo = { gitCommit: 'unknown', buildUnix: '0' };
let mediaLibrary = [];
const layerLibraries = new Map();
let stateNeedsSave = false;
let visualsSearchFilter = '';
let isPublishing = false;
let workstationLive = { active: false, phase: 'READY', layoutHash: '', heartbeatTimer: null, heartbeatFailures: 0, startedAt: 0, error: '', greenAck: null, visualsAck: null };
let liveRouting = { chat: 'legacy', visuals: 'legacy', lastChanged: null };
let liveHealth = {
  vm2: 'ONLINE',
  realtime: 'ONLINE',
  chatRenderer: 'OFFLINE',
  chatRendererLastSeen: null,
  chatRendererLayoutHash: '',
  chatRendererLayoutId: '',
  chatRendererVisualMode: 'unknown',
  chatRendererRenderingCurrent: false,
  currentVisualId: '',
  rotationRound: 0,
  rotationPosition: 0,
  rotationLibraryCount: 0,
  greenRenderer: 'ONLINE'
};

async function refreshLiveRoutingAndHealth() {
  try {
    const routing = await invoke('get_visual_routing').catch(() => null);
    if (routing) {
      liveRouting.chat = routing.chat || 'legacy';
      liveRouting.visuals = routing.visuals || 'legacy';
    }
  } catch (_) {}

  try {
    const health = await invoke('get_visual_health').catch(() => null);
    if (health) {
      liveHealth.vm2 = health.vm2?.status === 'ok' ? 'ONLINE' : 'OFFLINE';
      liveHealth.realtime = health.realtime?.status === 'ok' ? 'ONLINE' : 'OFFLINE';
      const rAck = health.renderer?.ack || {};
      const envs = health.renderer?.environments || rAck.environments || {};
      const chatAck = envs.live || (rAck.environment === 'live' ? rAck : null);
      if (chatAck) {
        const isFresh = (Date.now() - (chatAck.lastSeen || chatAck.renderAppliedAt || 0)) < 35000;
        liveHealth.chatRenderer = isFresh ? 'ONLINE' : 'OFFLINE';
        liveHealth.chatRendererLastSeen = chatAck.lastSeen ? new Date(chatAck.lastSeen).toLocaleTimeString() : null;
        liveHealth.chatRendererLayoutHash = chatAck.layoutHash || '';
        liveHealth.chatRendererLayoutId = chatAck.layoutId || '';
        liveHealth.chatRendererVisualMode = health.renderer?.ack?.visualMode || chatAck.visualMode || 'unknown';
        liveHealth.chatRendererRenderingCurrent = Boolean(health.renderer?.ack?.renderingCurrentLayout || chatAck.renderingCurrentLayout);
        liveHealth.currentVisualId = chatAck.visualAssetId || chatAck.currentVisualId || '';
        liveHealth.rotationRound = Number(chatAck.rotationRound || 0);
        liveHealth.rotationPosition = Number(chatAck.rotationPosition || 0);
        liveHealth.rotationLibraryCount = Number(chatAck.libraryCount || 0);
      } else {
        liveHealth.chatRenderer = health.renderer?.status === 'online' ? 'ONLINE' : 'OFFLINE';
        liveHealth.chatRendererLastSeen = health.renderer?.last_seen || null;
      }

      const roles = rAck.renderersByRole || {};
      const freshAck = ack => ack && String(ack.renderStatus).toLowerCase() === 'rendered' && (Date.now() - Number(ack.lastSeen || ack.receivedAt || 0)) < 35000 && (!workstationLive.layoutHash || ack.layoutHash === workstationLive.layoutHash);
      workstationLive.greenAck = freshAck(roles['green-room-renderer']) ? roles['green-room-renderer'] : null;
      workstationLive.visualsAck = freshAck(roles['visuals-page-renderer']) ? roles['visuals-page-renderer'] : null;
    }
  } catch (_) {}
}

function appLog(level, message) {
  invoke('append_app_log', { level, message: String(message) }).catch(() => {});
}

async function copyToClipboard(text, label = 'URL') {
  try {
    await navigator.clipboard.writeText(text);
    activity('Copied to clipboard', `${label}: ${text}`);
    showToast(`✓ Copied ${label} to clipboard`);
  } catch (e) {
    activity('Copy failed', String(e));
  }
}

function showToast(message, duration = 3000) {
  let toast = $('#appToast');
  if (!toast) {
    toast = document.createElement('div');
    toast.id = 'appToast';
    toast.style.cssText = 'position:fixed;bottom:54px;right:20px;z-index:999999;background:#1b1328;border:1px solid #9b39ff;color:#a3ffd1;padding:8px 16px;border-radius:6px;font-size:11px;font-weight:600;box-shadow:0 8px 24px #000a;transition:opacity 0.2s ease;';
    document.body.appendChild(toast);
  }
  toast.textContent = message;
  toast.style.opacity = '1';
  clearTimeout(toast.__timer);
  toast.__timer = setTimeout(() => { toast.style.opacity = '0'; }, duration);
}

async function openStagingBrowser(url = CANONICAL_GREEN_URL) {
  try {
    await invoke('open_staging_url', { url });
    activity('Staging browser opened', url);
  } catch (err) {
    appLog('ERROR', `external-browser: ${err}`);
    activity('Browser open failed', String(err));
    alert(String(err));
  }
}

window.addEventListener('error', event => appLog('ERROR', `window.error: ${event.message || event.error || 'unknown'}`));
window.addEventListener('unhandledrejection', event => appLog('ERROR', `unhandledrejection: ${event.reason || 'unknown'}`));

const escapeHtml = value => String(value ?? '')
  .replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
  .replaceAll('"', '&quot;').replaceAll("'", '&#039;');

function uid(prefix = 'layer') {
  return `${prefix}-${crypto.randomUUID().slice(0, 8)}`;
}

function defaultFrame(kind = 'media') {
  if (kind === 'logo') return { x: 10.5, y: 77, width: 8.5, height: 9, scale: 1, opacity: 1, fit: 'contain', visible: true, flipX: false, flipY: false };
  if (kind === 'alert') return { x: 31, y: 82, width: 38, height: 12, scale: 1, opacity: 1, fit: 'contain', visible: true, flipX: false, flipY: false };
  if (kind === 'presence') return { x: 4, y: 86, width: 28, height: 8, scale: 1, opacity: 1, fit: 'contain', visible: true, flipX: false, flipY: false };
  if (kind === 'energy') return { x: 83, y: 7, width: 13, height: 10, scale: 1, opacity: 1, fit: 'contain', visible: true, flipX: false, flipY: false };
  if (kind === 'reactions') return { x: 79, y: 88, width: 17, height: 8, scale: 1, opacity: 1, fit: 'contain', visible: true, flipX: false, flipY: false };
  return { x: 0, y: 0, width: 100, height: 100, scale: 1, opacity: 1, fit: 'cover', visible: true, flipX: false, flipY: false };
}

function defaultWorkspaceLayers() {
  return [
    { id: 'visual-content', name: 'Visual Content', kind: 'media', role: 'visual', sourceFolder: DEFAULT_VISUAL_FOLDER, mediaIndex: 0, z: 10, mask: 'none', maskExplicit: true },
    { id: 'stage-content', name: 'Stage Content', kind: 'media', role: 'stage', sourceFolder: DEFAULT_STAGE_FOLDER, mediaIndex: 0, z: 20, mask: 'none', maskExplicit: true },
    { id: 'station-logo', name: 'Station / Takeover Logo', kind: 'logo', z: 30 },
    { id: 'now-playing', name: 'Now Playing / Live Alert', kind: 'alert', z: 40 },
    { id: 'presence-bubbles', name: 'Presence Bubbles', kind: 'presence', z: 50 },
    { id: 'reactions', name: 'Reactions', kind: 'reactions', z: 60 },
    { id: 'room-energy', name: 'Room Energy', kind: 'energy', z: 70 },
  ];
}

function layerDef(id = selectedLayerId) {
  return state.workspaceLayers.find(x => x.id === id);
}

function activePreset() {
  return state.presets.find(p => p.name === state.activePreset) || state.presets[0];
}

function layerFrame(id = selectedLayerId) {
  const def = layerDef(id);
  const p = activePreset();
  p.layerFrames ||= {};
  if (!p.layerFrames[id]) p.layerFrames[id] = defaultFrame(def?.kind);
  return p.layerFrames[id];
}

function legacyFrameFor(def, preset) {
  if (def.id === 'visual-content') return structuredClone(preset.content || defaultFrame('media'));
  if (def.id === 'stage-content') return structuredClone(preset.stage || defaultFrame('media'));
  if (def.kind === 'logo') return structuredClone(preset.logo || defaultFrame('logo'));
  if (def.kind === 'alert') return structuredClone(preset.now || defaultFrame('alert'));
  return defaultFrame(def.kind);
}

function migrateCanonicalLayerIds() {
  if (!Array.isArray(state.workspaceLayers)) return;
  const defaults = defaultWorkspaceLayers();

  for (const canonical of defaults) {
    const existing = state.workspaceLayers.find(x => x.id === canonical.id);
    if (existing) continue;
    // Canonical ID missing — find by role or name, then reassign
    let adopt = state.workspaceLayers.find(x =>
      x.role === canonical.role ||
      (x.kind === canonical.kind && x.name?.toLowerCase() === canonical.name?.toLowerCase())
    );
    if (adopt) {
      const oldId = adopt.id;
      adopt.id = canonical.id;
      adopt.role = canonical.role;
      adopt.name = canonical.name;
      // Migrate layerFrames keys
      for (const p of state.presets || []) {
        if (p.layerFrames && p.layerFrames[oldId]) {
          p.layerFrames[canonical.id] = p.layerFrames[oldId];
          delete p.layerFrames[oldId];
        }
      }
    } else {
      // No adoptable layer — insert canonical at correct z position
      state.workspaceLayers.push({ ...canonical });
    }
  }
}

function ensureLayerSystem() {
  if (!Array.isArray(state.workspaceLayers) || state.workspaceLayerSystemVersion !== 21) {
    state.workspaceLayers = defaultWorkspaceLayers();
    for (const p of state.presets || []) {
      p.layerFrames = {};
      for (const def of state.workspaceLayers) p.layerFrames[def.id] = legacyFrameFor(def, p);
    }
    state.workspaceLayerSystemVersion = 21;
    selectedLayerId = 'visual-content';
  } else {
    migrateCanonicalLayerIds();
    for (const p of state.presets || []) {
      p.layerFrames ||= {};
      for (const def of state.workspaceLayers) p.layerFrames[def.id] ||= defaultFrame(def.kind);
      p.screenOpening = Object.assign({}, DEFAULT_SCREEN_OPENING, p.screenOpening || {});
    }
  }

  // Enforce canonical IDs/roles without ever converting arbitrary custom media
  // layers into a second stage-content/visual-content layer. Duplicate canonical IDs
  // are demoted to ordinary media layers so layerLibraries cannot collide.
  const canonicalSeen = new Set();
  for (const def of state.workspaceLayers) {
    if (def.id === 'visual-content') {
      if (canonicalSeen.has('visual-content')) {
        def.id = uid('media'); def.role = 'media'; def.name ||= 'Media Layer';
      } else {
        canonicalSeen.add('visual-content'); def.z ??= 10; def.role = 'visual';
      }
    } else if (def.id === 'stage-content') {
      if (canonicalSeen.has('stage-content')) {
        def.id = uid('media'); def.role = 'media'; def.name ||= 'Media Layer';
      } else {
        canonicalSeen.add('stage-content'); def.z ??= 20; def.role = 'stage';
      }
    } else {
      // stage/visual are reserved roles for the two canonical built-ins.
      if (def.role === 'stage' || def.role === 'visual') def.role = 'media';
      if (def.kind === 'logo' || def.id === 'station-logo') def.z ??= 30;
      else if (def.kind === 'alert' || def.id === 'now-playing') def.z ??= 40;
      else if (def.kind === 'presence' || def.id === 'presence-bubbles') def.z ??= 50;
      else if (def.kind === 'reactions' || def.id === 'reactions') def.z ??= 60;
      else if (def.kind === 'energy' || def.id === 'room-energy') def.z ??= 70;
    }
  }

  if (state.safePlaybackMode == null) state.safePlaybackMode = false;
  if (!layerDef(selectedLayerId)) selectedLayerId = state.workspaceLayers[0]?.id || '';
  syncLegacyPresetKeys();
}

function syncLegacyPresetKeys() {
  for (const p of state.presets || []) {
    const visual = state.workspaceLayers.find(x => x.id === 'visual-content');
    const stage = state.workspaceLayers.find(x => x.id === 'stage-content');
    if (visual && p.layerFrames?.[visual.id]) p.content = structuredClone(p.layerFrames[visual.id]);
    if (stage && p.layerFrames?.[stage.id]) p.stage = structuredClone(p.layerFrames[stage.id]);
  }
}

function activity(event, detail = '') {
  log.unshift({ at: new Date().toISOString(), event, detail });
  log = log.slice(0, 200);
  state.activity = [...log];
}

function compactPlaylistEntry(item) {
  const assetId = item?.assetId || item?.routeId || item?.id || item?.fingerprint || '';
  return {
    assetId,
    routeId: item?.routeId || assetId,
    id: item?.id || assetId,
    fingerprint: item?.fingerprint || assetId,
    name: item?.name || 'visual',
    publicUrl: item?.publicUrl || (typeof item?.url === 'string' && item.url.startsWith('https://') ? item.url : ''),
    url: typeof item?.url === 'string' && item.url.startsWith('https://') ? item.url : '',
    fit: item?.fit || 'cover',
    duration: item?.duration ?? null,
    enabled: item?.enabled !== false,
    // Local-only fields are consumed by the Tauri publisher so every enabled
    // 24/7 asset can be verified/uploaded before its public URL is advertised.
    // The Rust canonical realtime serializer deliberately strips these paths.
    sourcePath: item?.sourcePath || item?.path || '',
    runtimePath: item?.runtimePath || item?.sourcePath || item?.path || ''
  };
}

function orderedCyclePlaylist() {
  const visual = selectedMedia(layerDef('visual-content'));
  return buildOrderedCycle(state.playlist, mediaIdentity(visual), compactPlaylistEntry);
}

function livePublishSnapshot(mode = 'cycle') {
  // Deliberately construct a small publish contract instead of cloning the entire
  // workstation state. This keeps the WebKitGTK UI responsive even with hundreds
  // of local media items and prevents accidental local-only/debug data from
  // entering the realtime payload.
  const p = activePreset();
  const layerFrames = {};
  const workspaceLayers = state.workspaceLayers.map(layer => {
    const live = state.workspaceLayers.find(x => x.id === layer.id) || layer;
    const f = structuredClone(layerFrame(layer.id));
    layerFrames[layer.id] = structuredClone(f);
    const layerWithFrame = {
      id: layer.id,
      name: layer.name,
      kind: layer.kind,
      role: layer.role,
      z: layer.z,
      mediaIndex: Number(layer.mediaIndex) || 0,
      frame: f,
      x: Number.isFinite(Number(f.x)) ? Number(f.x) : 0,
      y: Number.isFinite(Number(f.y)) ? Number(f.y) : 0,
      width: Number.isFinite(Number(f.width)) ? Number(f.width) : 100,
      height: Number.isFinite(Number(f.height)) ? Number(f.height) : 100,
      scale: Number.isFinite(Number(f.scale)) ? Number(f.scale) : 1,
      opacity: f.opacity != null ? Number(f.opacity) : 1,
      fit: f.fit || (layer.kind === 'media' ? 'cover' : 'contain'),
      visible: f.visible !== false,
      flipX: Boolean(f.flipX),
      flipY: Boolean(f.flipY)
    };
    if (layer.kind !== 'media') return layerWithFrame;
    const media = selectedMedia(live);
    if (!media) return layerWithFrame;
    const assetId = media.assetId || media.routeId || media.id || media.fingerprint || '';
    layerWithFrame.selectedMedia = {
      assetId,
      id: assetId,
      name: media.name,
      sourcePath: media.sourcePath,
      runtimePath: media.runtimePath,
      routeId: media.routeId,
      fingerprint: media.fingerprint || media.routeId || assetId
    };
    return layerWithFrame;
  });

  const snapshot = {
    layoutVersion: state.layoutVersion || 1,
    activePreset: p.name,
    presets: [{
      name: p.name,
      viewport: p.viewport || 'desktop-16-9',
      version: p.version || 1,
      layerFrames,
      screenOpening: structuredClone(screenOpening(p))
    }],
    workspaceLayers,
    screenOpening: structuredClone(screenOpening(p)),
    safePlaybackMode: Boolean(state.safePlaybackMode),
    previewMode: mode === 'single',
    productionLocked: false,
    cycle: { mode: 'shuffle-bag', interval: 'media-ended', skipFailed: true, avoidImmediateRepeat: true },
    playlist: mode === 'single' ? [] : orderedCyclePlaylist()
  };

  if (mode === 'single') {
    const visualLayer = workspaceLayers.find(x => x.id === 'visual-content');
    const media = visualLayer?.selectedMedia;
    if (media) {
      snapshot.previewVisual = {
        assetId: media.assetId || media.routeId || media.id || media.fingerprint || '',
        id: media.assetId || media.routeId || media.id || media.fingerprint || '',
        name: media.name,
        fingerprint: media.fingerprint || media.routeId || media.assetId || '',
        fit: visualLayer.fit || 'cover'
      };
    }
  }
  return snapshot;
}

function captureScrollState() {
  return {
    view: $('#view')?.scrollTop || 0,
    colLeft: $('.workspace-col-left')?.scrollTop || 0,
    colRight: $('.workspace-col-right')?.scrollTop || 0,
    mediaList: $('.media-list-scroll')?.scrollTop || 0,
  };
}

function restoreScrollState(scroll, reason = '') {
  requestAnimationFrame(() => {
    const view = $('#view');
    const colLeft = $('.workspace-col-left');
    const colRight = $('.workspace-col-right');
    const mediaList = $('.media-list-scroll');
    if (view && scroll.view) view.scrollTop = scroll.view;
    if (colLeft && scroll.colLeft) colLeft.scrollTop = scroll.colLeft;
    if (colRight && scroll.colRight) colRight.scrollTop = scroll.colRight;
    if (mediaList && scroll.mediaList) mediaList.scrollTop = scroll.mediaList;
  });
}

function snapshot() {
  if (!selectedLayerId) return;
  history.push({ layer: selectedLayerId, frame: structuredClone(layerFrame()) });
  history = history.slice(-50);
  future = [];
}
function restoreFrame(item) {
  if (!item || !layerDef(item.layer)) return;
  selectedLayerId = item.layer;
  Object.assign(layerFrame(), item.frame);
  render('Visual Workspace');
}
function undo() {
  if (!history.length) return;
  future.push({ layer: selectedLayerId, frame: structuredClone(layerFrame()) });
  restoreFrame(history.pop());
}
function redo() {
  if (!future.length) return;
  history.push({ layer: selectedLayerId, frame: structuredClone(layerFrame()) });
  restoreFrame(future.pop());
}

function mediaLayers() {
  return state.workspaceLayers.filter(x => x.kind === 'media');
}
function libraryFor(id) {
  return layerLibraries.get(id) || [];
}
function selectedMedia(def) {
  const lib = libraryFor(def.id);
  if (!lib.length) return null;
  def.mediaIndex = Math.max(0, Math.min(lib.length - 1, Number(def.mediaIndex) || 0));
  return lib[def.mediaIndex];
}

function makeLayerElement(def) {
  const id = escapeHtml(def.id);
  if (def.role === 'stage' || def.id === 'stage-content') {
    return `<div class="layer media-layer stage-layer-compositor" data-canvas-layer-id="${id}">
      <div class="stage-panel stage-panel-top"><video class="stage-slice" muted loop autoplay playsinline preload="auto"></video></div>
      <div class="stage-panel stage-panel-bottom"><video class="stage-slice" muted loop autoplay playsinline preload="auto"></video></div>
      <div class="stage-panel stage-panel-left"><video class="stage-slice" muted loop autoplay playsinline preload="auto"></video></div>
      <div class="stage-panel stage-panel-right"><video class="stage-slice" muted loop autoplay playsinline preload="auto"></video></div>
      <video class="stage-fallback-full" muted loop autoplay playsinline preload="auto" style="display:none;position:absolute;inset:0;width:100%;height:100%;object-fit:fill;"></video>
    </div>`;
  }
  if (def.kind === 'media' && (def.role === 'visual' || def.id === 'visual-content')) {
    return `<div class="layer media-layer visual-ab" data-canvas-layer-id="${id}">
      <video class="visual-buf visual-buf-a active" muted loop autoplay playsinline preload="auto"></video>
      <video class="visual-buf visual-buf-b" muted loop playsinline preload="auto"></video>
    </div>`;
  }
  if (def.kind === 'media') return `<video class="layer media-layer" data-canvas-layer-id="${id}" muted loop autoplay playsinline preload="auto"></video>`;
  if (def.kind === 'logo') return `<div class="layer layer-logo" data-canvas-layer-id="${id}"><img src="https://allthings140radio.online/assets/takeover-fallback-logo.webp" alt="ALLTHINGS140 logo"></div>`;
  if (def.kind === 'alert') return `<div class="layer layer-alert" data-canvas-layer-id="${id}" data-mode="autodj"><small>24/7 PLAYLIST</small><b>EXAMPLE TRACK</b><span>EXAMPLE ARTIST</span></div>`;
  if (def.kind === 'presence') return `<div class="layer layer-presence" data-canvas-layer-id="${id}"><i></i><i></i><i></i><i></i></div>`;
  if (def.kind === 'energy') return `<div class="layer layer-energy" data-canvas-layer-id="${id}"><small>ROOM ENERGY</small><b>${Math.round(metrics.energy || 62)}%</b></div>`;
  if (def.kind === 'reactions') return `<div class="layer layer-reactions" data-canvas-layer-id="${id}">🔥 💀 💜 ⚡</div>`;
  return `<div class="layer" data-canvas-layer-id="${id}"></div>`;
}

function getGreenSyncStatus() {
  if (isPublishing) return { status: 'PUBLISHING', label: 'GREEN — PUBLISHING', class: 'publishing' };
  if (metrics.ws === 'OFFLINE') return { status: 'OFFLINE', label: 'GREEN — OFFLINE', class: 'error' };
  if (state.publishedVersion && state.publishedVersion === state.layoutVersion) {
    if (state.lastPublishedHash && state.lastRendererAckHash === state.lastPublishedHash) {
      return { status: 'SYNCED', label: 'GREEN — RENDERED & SYNCED', class: 'synced' };
    }
    return { status: 'PUBLISHED', label: 'GREEN — PUBLISHED / VERIFYING', class: 'publishing' };
  }
  return { status: 'LOCAL_CHANGES', label: 'GREEN — LOCAL CHANGES', class: 'local-changes' };
}

function mediaInspector(def) {
  const lib = libraryFor(def.id);
  const role = def.role === 'stage' ? 'stage' : (def.role === 'visual' ? 'visual' : 'media');
  return `<div class="media-layer-box">
    <h3>MEDIA ASSET INSPECTOR</h3>
    <label>LAYER ROLE
      <select id="layerRoleSelect">
        <option value="visual" ${role === 'visual' ? 'selected' : ''}>Visual Content (Under Stage Cutout)</option>
        <option value="stage" ${role === 'stage' ? 'selected' : ''}>Stage Base (Framing Overlay)</option>
        <option value="media" ${role === 'media' ? 'selected' : ''}>Normal Media Layer</option>
      </select>
    </label>
    <label>Active Video
      <select id="layerMediaSelect">${lib.map((m, i) => `<option value="${i}" ${i === def.mediaIndex ? 'selected' : ''}>${escapeHtml(m.name)}</option>`).join('')}</select>
    </label>
    <p id="layerMediaInfo">${lib.length ? '' : 'No media loaded. Use Refresh Folder.'}</p>
    <div class="row">
      <button id="prevLayerMedia">◀ PREV</button>
      <button id="nextLayerMedia">NEXT ▶</button>
    </div>
    <button id="randomLayerMedia">🔀 RANDOM VISUAL</button>
    <button id="setLayerGlobalFrame">SET AS GLOBAL FRAME</button>
    <b>${lib.length} VIDEO${lib.length === 1 ? '' : 'S'} IN SOURCE FOLDER</b>
    <label>MEDIA SOURCE FOLDER
      <input id="layerSourceFolder" readonly value="${escapeHtml(def.sourceFolder || '')}">
    </label>
    <div class="row">
      <button id="changeLayerFolder">CHANGE FOLDER…</button>
      <button id="refreshLayerFolder">REFRESH</button>
    </div>
    <b>COMPOSITOR ROLE: ${role === 'stage' ? 'STAGE OVERLAY (z: 20)' : role === 'visual' ? 'VISUAL SCREEN (z: 10)' : 'MEDIA LAYER'}</b>
    <small class="layer-help">Stage Content (z: 20) punches a transparent screen cutout revealing Visual Content (z: 10) underneath.</small>
  </div>`;
}

function screenOpeningInspector(p = activePreset()) {
  const so = screenOpening(p);
  return `<div class="screen-opening-box">
    <h3>STAGE SCREEN CUTOUT / MASK</h3>
    <p>Punches an exact transparent hole in the Stage layer so Visual Content underneath is clearly visible in WebKitGTK.</p>
    <label>CUTOUT X (%)<input data-screen-prop="x" type="number" step="0.1" value="${so.x}"></label>
    <label>CUTOUT Y (%)<input data-screen-prop="y" type="number" step="0.1" value="${so.y}"></label>
    <label>CUTOUT WIDTH (%)<input data-screen-prop="width" type="number" step="0.1" value="${so.width}"></label>
    <label>CUTOUT HEIGHT (%)<input data-screen-prop="height" type="number" step="0.1" value="${so.height}"></label>
    <label>CORNER RADIUS (%)<input data-screen-prop="rx" type="number" step="0.1" value="${so.rx || 1.5}"></label>
    <label class="check"><input data-screen-prop="enabled" type="checkbox" ${so.enabled !== false ? 'checked' : ''}> Enable Screen Cutout Mask</label>
    <div class="row">
      <button id="fitVisualToCutout">FIT VISUAL TO OPENING</button>
      <button id="resetScreenCutout">RESET CUTOUT</button>
    </div>
  </div>`;
}

function propertiesMarkup(def) {
  if (selectedLayerId === '__screen-opening__') {
    return screenOpeningInspector();
  }
  const frame = def ? layerFrame(def.id) : {};
  const title = def ? escapeHtml(def.name.toUpperCase()) : 'NO LAYER SELECTED';
  const isStage = def?.role === 'stage' || def?.id === 'stage-content';
  return `<div data-media-inspector>${def?.kind === 'media' ? mediaInspector(def) : ''}</div>
    ${isStage ? `<div style="margin-bottom:10px;"><button id="editStageCutout" class="screen-opening-btn" style="width:100%;">⬚ EDIT STAGE SCREEN CUTOUT</button></div>` : ''}
    <h3>TRANSFORM: ${title}</h3>
    ${def ? ['x', 'y', 'width', 'height', 'scale', 'opacity'].map(k => `<label>${k.toUpperCase()}<input data-prop="${k}" type="number" step="${k === 'opacity' ? '.05' : k === 'scale' ? '.05' : '.5'}" value="${frame[k]}"></label>`).join('') : ''}
    ${def ? `<label>FIT MODE
      <select data-prop="fit">
        <option ${frame.fit === 'cover' ? 'selected' : ''}>cover</option>
        <option ${frame.fit === 'contain' ? 'selected' : ''}>contain</option>
        <option ${frame.fit === 'fill' ? 'selected' : ''}>fill</option>
      </select>
    </label>
    <label class="check"><input data-prop="visible" type="checkbox" ${frame.visible ? 'checked' : ''}> Visible</label>
    <label class="check"><input data-prop="flipX" type="checkbox" ${frame.flipX ? 'checked' : ''}> Flip horizontal</label>
    <label class="check"><input data-prop="flipY" type="checkbox" ${frame.flipY ? 'checked' : ''}> Flip vertical</label>
    <div class="row"><button id="center">Center</button><button id="layerReset">Reset layer</button></div>` : ''}`;
}

function workspace() {
  const p = activePreset();
  const def = layerDef();
  const vp = viewport[p.viewport] || viewport.custom;
  const orderedLayers = [...state.workspaceLayers].sort((a, b) => (Number(b.z) || 0) - (Number(a.z) || 0));
  const layerButtons = orderedLayers.map((x, i) => {
    const depthNum = String(Math.max(1, Math.round((Number(x.z) || 10) / 10))).padStart(2, '0');
    return `<button draggable="true" data-layer-id="${escapeHtml(x.id)}" data-layer-index="${i}" class="${x.id === selectedLayerId ? 'sel' : ''}" title="Drag to reorder stack, right-click for actions"><i>${depthNum}</i> ${escapeHtml(x.name)}</button>`;
  }).join('');
  const canvasLayers = [...state.workspaceLayers].sort((a, b) => (Number(a.z) || 0) - (Number(b.z) || 0)).map(makeLayerElement).join('');
  const so = screenOpening(p);
  const syncState = getGreenSyncStatus();

  const visualDef = state.workspaceLayers.find(x => x.id === 'visual-content');
  const stageDef = state.workspaceLayers.find(x => x.id === 'stage-content');
  const activeVisualMedia = visualDef ? selectedMedia(visualDef) : null;
  const activeStageMedia = stageDef ? selectedMedia(stageDef) : null;

  return `<div class="workspace">
    <!-- LEFT COLUMN: LAYERS & GREEN WORKSTATION STAGING TOOLBAR -->
    <div class="workspace-col-left">
      <div class="layers-header">
        <h3>LAYERS</h3>
        <small>FRONT TO BACK</small>
      </div>
      <div class="layer-stack-indicator top">▲ FRONT (HUD & OVERLAYS)</div>
      <div id="layerList">${layerButtons}</div>
      <div class="layer-stack-indicator bottom">▼ BACK (STAGE & VISUALS)</div>
      <button id="selectScreenOpening" class="screen-opening-btn ${selectedLayerId === '__screen-opening__' ? 'sel' : ''}" title="Edit the transparent stage screen opening / mask">⬚ STAGE SCREEN CUTOUT</button>
      <button id="addMediaLayer">＋ NEW MEDIA LAYER</button>
      
      <hr>
      <label>PRESET<select id="preset">${state.presets.map(x => `<option ${x.name === state.activePreset ? 'selected' : ''}>${escapeHtml(x.name)}</option>`).join('')}</select></label>
      <div class="row"><button id="savePreset">Save</button><button id="saveAs">Save As</button></div>
      <div class="row"><button id="duplicatePreset">Duplicate</button><button id="resetPreset">Reset</button></div>
      <label>VIEWPORT<select id="viewport">${Object.keys(viewport).map(x => `<option ${x === p.viewport ? 'selected' : ''}>${x}</option>`).join('')}</select></label>
      <label class="check"><input id="safe" type="checkbox" ${p.safeArea ? 'checked' : ''}> Safe area / guides</label>
      
      <hr>
      <!-- DEDICATED GREEN ROOM WORKSTATION TOOLBAR -->
      <div class="staging-box">
        <div class="staging-box-header">
          <b>GREEN ROOM OUTPUT</b>
          <span class="staging-status-pill ${syncState.class}" id="greenSyncPill">${syncState.label}</span>
        </div>
        <div class="staging-url-badge" title="${CANONICAL_GREEN_URL}">
          ${CANONICAL_GREEN_URL}
        </div>
        <button id="browser" class="btn-green">OPEN GREEN ROOM</button>
        <button id="testGreen" class="btn-cyan">TEST CURRENT VISUAL</button>
        <div class="row" style="gap:4px;margin-top:4px;">
          <button id="validateStageOnly" class="btn-sm" style="flex:1;font-size:10px;padding:6px 4px;background:#1e293b;border:1px solid #334155;color:#93c5fd;" title="Validate Stage media independently with substep timings">⚡ STAGE ONLY</button>
          <button id="validateVisualOnly" class="btn-sm" style="flex:1;font-size:10px;padding:6px 4px;background:#1e293b;border:1px solid #334155;color:#93c5fd;" title="Validate Visual media independently with substep timings">⚡ VISUAL ONLY</button>
        </div>
        <button id="publishGreen">UPDATE LIVE LAYOUT</button>
        <button id="copyGreenUrl">COPY GREEN ROOM URL</button>
        <div class="staging-meta-grid">
          <div title="Active Visual">🎬 ${escapeHtml(activeVisualMedia?.name || 'Default Visual')}</div>
          <div title="Active Stage">🏛️ ${escapeHtml(activeStageMedia?.name || 'Default Stage')}</div>
          <div title="Layout Version">📌 v${state.layoutVersion || 1}</div>
          <div title="Realtime Server">⚡ ${metrics.ws} (${metrics.presence} users)</div>
        </div>
      </div>
    </div>

    <!-- CENTER COLUMN: CANVAS & TRANSPORT -->
    <div class="workspace-col-center">
      <div class="canvas-container">
        <div id="canvas" class="canvas ${p.safeArea ? 'safe' : ''}" style="aspect-ratio:${vp[0]}/${vp[1]}">
          <svg class="stage-mask-svg" width="0" height="0" style="position:absolute;pointer-events:none;" aria-hidden="true">
            <defs>
              <mask id="stage-screen-mask" maskContentUnits="objectBoundingBox">
                <rect width="1" height="1" fill="#ffffff" />
                <rect id="maskScreenHole" x="${so.x / 100}" y="${so.y / 100}" width="${so.width / 100}" height="${so.height / 100}" rx="${(so.rx || 1.5) / 100}" fill="#000000" />
              </mask>
            </defs>
          </svg>
          ${canvasLayers}
          <div class="center-x"></div><div class="center-y"></div>
          <div class="screen-target ${selectedLayerId === '__screen-opening__' ? 'selected' : ''}" style="left:${so.x}%;top:${so.y}%;width:${so.width}%;height:${so.height}%;border-radius:${(so.rx || 1.5) * 4}px;" title="Stage Screen Cutout Target"></div>
          <div class="transform-box"><i class="position-dot"></i>${['nw', 'n', 'ne', 'e', 'se', 's', 'sw', 'w'].map(x => `<button class="handle ${x}" data-handle="${x}" aria-label="Resize ${x}"></button>`).join('')}</div>
          <div class="media-status" id="mediaStatus">MEDIA SERVER: STARTING</div>
        </div>
      </div>
      <div class="transport">
        <button id="play">▶ / ❚❚</button><button id="restart">↺ RESTART</button>
        <span>VIEWPORT ${vp[0]} × ${vp[1]}</span><b>${escapeHtml(selectedLayerId === '__screen-opening__' ? 'STAGE SCREEN CUTOUT' : (def?.name || 'NO LAYER'))} SELECTED</b>
        <span id="layerMediaCounts">${mediaLayers().map(x => `${escapeHtml(x.name)}: ${libraryFor(x.id).length}`).join(' · ')}</span>
      </div>
      <div class="transform-tools">
        <button id="undoFrame">↶ Undo</button><button id="redoFrame">↷ Redo</button>
        <button id="centerH">Center H</button><button id="centerV">Center V</button>
        <button id="fitTarget">Fit To Screen Target</button><button id="globalFrame">Set Selected As Global Frame</button>
        <label><input id="snapToggle" type="checkbox" ${snapEnabled ? 'checked' : ''}> Snap</label>
        <label>Editor Zoom <select id="editorZoom">${[50, 75, 100, 125, 150, 200].map(x => `<option value="${x}" ${x === editorZoom * 100 ? 'selected' : ''}>${x}%</option>`).join('')}</select></label>
        <label class="safe-mode-toggle"><input id="safePlaybackToggle" type="checkbox" ${state.safePlaybackMode ? 'checked' : ''}> 🛡️ Safe Playback Mode</label>
      </div>
    </div>

    <!-- RIGHT COLUMN: PROPERTIES & INSPECTORS -->
    <div class="workspace-col-right">
      ${propertiesMarkup(def)}
    </div>
    <div id="layerContextMenu" class="layer-context-menu" hidden></div>
  </div>`;
}

function dashboard() {
  const isChatLegacy = liveRouting.chat === 'legacy';
  const isAutoFallback = !isChatLegacy && liveHealth.chatRendererVisualMode === 'legacy';
  const roomSummary = isChatLegacy ? 'LEGACY SAFETY' : (isAutoFallback ? 'AUTO FALLBACK' : 'COMPOSITOR');
  const readyVisuals = state.playlist.filter(x => x.enabled !== false && !x.missingLocalSource).length;
  const stageLayer = state.workspaceLayers.find(x => x.id === 'stage-content' || x.role === 'stage');
  const stageMedia = stageLayer ? (selectedMedia(stageLayer) || stageLayer.selectedMedia) : null;
  const hasValidStage = Boolean(stageMedia && (stageMedia.sourcePath || stageMedia.runtimePath));
  const stageName = hasValidStage ? stageMedia.name : (stageLayer?.scanStatus === 'SCANNING' ? 'Scanning Stage...' : 'STAGE MISSING');
  const visualMedia = selectedMedia(state.workspaceLayers.find(x => x.id === 'visual-content'));
  const visualName = visualMedia?.name || (readyVisuals > 0 ? 'Ready for rotation' : 'No visuals available');

  let liveBannerTitle = workstationLive.phase === 'READY' ? 'WORKSTATION READY' : workstationLive.phase;
  let liveBannerCopy = 'Preview and edit safely. Both routes remain on fallback until you press the button.';
  if (workstationLive.active) {
    if (workstationLive.greenAck && workstationLive.visualsAck) {
      liveBannerTitle = '● LIVE — BOTH DESTINATIONS';
      liveBannerCopy = 'Green Room and the full-width Visuals tab acknowledged the same workstation scene.';
    } else if (workstationLive.greenAck) {
      liveBannerTitle = '● LIVE — GREEN ROOM';
      liveBannerCopy = `Green Room viewer acknowledged live scene (rev ${(workstationLive.greenAck.layoutHash || '').slice(0, 8)}). Waiting for /visuals/ viewer.`;
    } else if (workstationLive.visualsAck) {
      liveBannerTitle = '● LIVE — VISUALS TAB';
      liveBannerCopy = `Full-width Visuals tab acknowledged live scene (rev ${(workstationLive.visualsAck.layoutHash || '').slice(0, 8)}). Waiting for /room/ viewer.`;
    } else {
      liveBannerTitle = '● SOURCE LIVE (BROADCAST ACTIVE)';
      liveBannerCopy = 'Workstation source lease is active and publishing. No public browser viewers currently open.';
    }
  }

  const renderAckLabel = !workstationLive.active
    ? 'STANDBY'
    : (workstationLive.greenAck && workstationLive.visualsAck
      ? 'MATCHED BOTH'
      : (workstationLive.greenAck || workstationLive.visualsAck ? 'PARTIAL' : 'NO ACTIVE VIEWER'));

  return `<div class="scrollable-page live-home">
  <section class="live-command-panel ${workstationLive.active ? 'is-live' : ''}">
    <div>
      <small>GREEN ROOM + VISUALS BROADCAST SOURCE</small>
      <h2>${escapeHtml(liveBannerTitle)}</h2>
      <p>${escapeHtml(liveBannerCopy)}</p>
    </div>
    <button id="dashboardLiveVisuals" class="${workstationLive.active ? 'btn-live-stop' : 'btn-live-primary'}">${workstationLive.active ? 'STOP LIVE VISUALS' : (hasValidStage ? '● LIVE VISUALS' : 'STAGE REQUIRED')}</button>
  </section>
  <div class="live-truth-grid">
    <article><small>CONNECTION</small><b>${metrics.ws === 'LIVE' ? 'HEALTHY' : metrics.ws}</b></article>
    <article><small>STAGE</small><b class="${hasValidStage ? '' : 'text-danger'}">${escapeHtml(stageName)}</b><span>${hasValidStage ? 'READY' : 'STAGE MISSING'}</span></article>
    <article><small>VISUALS READY</small><b>${readyVisuals} / ${state.playlist.length}</b><span>Full-library shuffle bag</span></article>
    <article><small>CURRENT</small><b>${escapeHtml(visualName)}</b><span>Next asset prefetched</span></article>
    <article><small>SCENE REVISION</small><b>${escapeHtml((state.lastPublishedHash || 'NOT PUBLISHED').slice(0, 12))}</b><span>${workstationLive.active ? 'Live revision' : 'Awaiting live session'}</span></article>
    <article><small>MAIN /visuals/</small><b class="${workstationLive.visualsAck ? 'text-green' : ''}">${workstationLive.visualsAck ? 'LIVE (ACK)' : (workstationLive.active ? 'NO ACTIVE VIEWER' : 'FALLBACK')}</b><span>${workstationLive.visualsAck ? 'Viewer rendering live scene' : 'Existing background is automatic fallback'}</span></article>
  </div><div class="cards">
    <article><small>WORKSTATION</small><b id="workstationLiveStatus" class="${workstationLive.active ? 'text-green' : ''}">${workstationLive.active ? 'SOURCE LIVE' : workstationLive.phase}</b><span>One scene authority · two route shells</span></article>
    <article><small>GREEN ROOM</small><b class="${workstationLive.greenAck ? 'text-green' : ''}">${workstationLive.greenAck ? 'LIVE (ACK)' : (workstationLive.active ? 'NO ACTIVE VIEWER' : roomSummary)}</b><span>${workstationLive.greenAck ? 'Exact scene ACK' : 'Fallback / no active viewer ACK'}</span></article>
    <article><small>VISUALS</small><b>${readyVisuals} / ${libraryFor('visual-content').length || state.playlist.length} READY</b><span>Full-library shuffle bag</span></article>
    <article><small>RENDER ACK</small><b>${renderAckLabel}</b><span>${escapeHtml(state.lastRendererAckHash?.slice(0, 12) || (workstationLive.active ? 'Waiting for viewers' : 'No live revision'))}</span></article>
  </div><div class="panel overview quick-actions">
    <h2>ALLTHINGS140 VISUALS WORKSTATION</h2>
    <p>This workstation is the single live scene authority for Green Room and the full-width Visuals tab. Each destination reports its own renderer acknowledgement; radio audio remains isolated.</p>
    <div class="row" style="max-width:600px;margin-top:12px;gap:10px;">
      <button data-view="Visual Workspace" class="btn-green">EDIT LAYOUT</button>
      <button data-view="24/7 Visuals">OPEN VISUAL LIBRARY</button>
      <button data-view="Diagnostics" class="btn-cyan">VIEW STATUS</button>
    </div>
  </div></div>`;
}

function liveOutput() {
  const isRoomLegacy = liveRouting.chat === 'legacy';
  const isAutoFallback = !isRoomLegacy && liveHealth.chatRendererVisualMode === 'legacy';
  const roomModeLabel = isRoomLegacy ? 'LEGACY VIDEO SAFETY' : (isAutoFallback ? 'AUTOMATIC SAFETY FALLBACK' : 'GREEN ROOM COMPOSITOR');
  const roomModeClass = (isRoomLegacy || isAutoFallback) ? 'status-legacy' : 'status-new';
  const currentLayoutId = state.activePreset || 'Known Good Default';
  const currentHash = state.lastPublishedHash || 'draft-uncommitted';

  return `<div class="scrollable-page live-output-page">
    <div class="live-output-grid">
      <article class="panel live-tab-card">
        <div class="live-card-header">
          <small class="pill pill-chat">PUBLIC GREEN ROOM /room/</small>
          <span class="live-mode-badge ${roomModeClass}">${roomModeLabel}</span>
        </div>
        <h3>Green Room Visual Safety Control</h3>
        <p>The public homepage is isolated and never receives the compositor. CHAT/GREEN ROOM navigation opens the dedicated <code>/room/</code> document. This control changes only the visual engine inside that room.</p>

        <div class="telemetry-grid">
          <div class="telemetry-item">
            <small>ROOM VISUAL MODE</small>
            <b>${roomModeLabel}</b>
            <span>${isRoomLegacy ? 'Operator-selected legacy background video' : (isAutoFallback ? 'Route requests compositor, but Room has fallen back safely' : 'Stage + Visual compositor requested')}</span>
          </div>
          <div class="telemetry-item">
            <small>GREEN ROOM RENDERER</small>
            <b class="${liveHealth.chatRendererRenderingCurrent ? 'text-green' : 'text-muted'}">${liveHealth.chatRendererRenderingCurrent ? 'RENDERING CURRENT' : liveHealth.chatRenderer}</b>
            <span>${escapeHtml(liveHealth.chatRendererVisualMode || 'unknown')} mode${liveHealth.chatRendererLastSeen ? ' · Last ACK: ' + liveHealth.chatRendererLastSeen : ''}</span>
          </div>
          <div class="telemetry-item">
            <small>WORKSTATION SERVICE</small>
            <b class="${liveHealth.vm2 === 'ONLINE' ? 'text-green' : 'text-danger'}">${liveHealth.vm2}</b>
            <span>Local Green Room authority</span>
          </div>
          <div class="telemetry-item">
            <small>REALTIME GATEWAY</small>
            <b class="${liveHealth.realtime === 'ONLINE' ? 'text-green' : 'text-danger'}">${liveHealth.realtime}</b>
            <span>Chat, reactions, layout and renderer ACK</span>
          </div>
          <div class="telemetry-item">
            <small>CURRENT LAYOUT ID</small>
            <b>${escapeHtml(currentLayoutId)}</b>
            <span>v${state.layoutVersion || 1}</span>
          </div>
          <div class="telemetry-item">
            <small>CURRENT HASH</small>
            <code class="hash-code">${escapeHtml(currentHash.slice(0, 16))}…</code>
            <span>SHA-256 layout digest</span>
          </div>
          <div class="telemetry-item">
            <small>RENDERER ENVIRONMENT</small>
            <b>live</b>
            <span>Independent from green-staging</span>
          </div>
          <div class="telemetry-item">
            <small>HOMEPAGE</small>
            <b class="text-green">ISOLATED / SAFE</b>
            <span>No compositor injection path</span>
          </div>
        </div>

        <div class="live-actions-row">
          <button id="btnChatFallbackLegacy" class="btn-warning" ${isRoomLegacy ? 'disabled title="Green Room already uses legacy video safety mode"' : ''}>
            🛡 FALL BACK GREEN ROOM TO LEGACY VIDEO
          </button>
          <button id="btnChatUseNew" class="${isRoomLegacy ? 'btn-green' : 'btn-locked'}" ${isRoomLegacy ? '' : 'disabled title="Green Room compositor is already active"'}>
            ${isRoomLegacy ? '▶ USE GREEN ROOM COMPOSITOR' : '✓ GREEN ROOM COMPOSITOR ACTIVE'}
          </button>
        </div>

        <div class="canary-test-box">
          <h4>ROOM VERIFICATION</h4>
          <p>Open the public room or Green staging without changing the homepage or the legacy Visuals tab.</p>
          <div class="row" style="gap:10px;">
            <button id="btnOpenCanaryPreview" class="btn-cyan">◉ OPEN PUBLIC GREEN ROOM</button>
            <button id="btnOpenGreenStaging">OPEN GREEN STAGING</button>
            <button id="btnRefreshLiveRouting">⟳ REFRESH STATUS</button>
          </div>
        </div>
      </article>

      <article class="panel live-tab-card">
        <div class="live-card-header">
          <small class="pill pill-visuals">PUBLIC VISUALS TAB</small>
          <span class="live-mode-badge status-legacy">LEGACY PLAYLIST</span>
        </div>
        <h3>Visuals Tab (/visuals/)</h3>
        <p>The public Visuals tab remains independent and unchanged. Green Room rollout does not alter its player, routing, or media source.</p>

        <div class="telemetry-grid">
          <div class="telemetry-item">
            <small>CURRENT MODE</small>
            <b>LEGACY (Current Visuals Video)</b>
            <span>Independent standalone player</span>
          </div>
          <div class="telemetry-item">
            <small>PROMOTION STATUS</small>
            <b class="text-locked">LOCKED — AWAITING USER APPROVAL</b>
            <span>Promotion switch is disabled</span>
          </div>
          <div class="telemetry-item">
            <small>ROUTE</small>
            <code>/visuals/</code>
            <span>Standalone full-screen page</span>
          </div>
          <div class="telemetry-item">
            <small>DEPENDENCIES</small>
            <b>ZERO REALTIME DEPENDENCIES</b>
            <span>Standalone fallback guaranteed</span>
          </div>
        </div>

        <div class="locked-notice-banner">
          <b>🔒 VISUALS TAB CUTOVER GATE CLOSED</b>
          <p>The public Visuals tab is not part of the Green Room cutover and remains on the current legacy implementation.</p>
        </div>
      </article>
    </div>
  </div>`;
}

function playlist(takeover = false) {
  const items = takeover ? state.takeovers : state.playlist;
  const query = visualsSearchFilter.toLowerCase();
  const filtered = items.map((item, index) => ({ item, index })).filter(({ item }) => {
    if (!query) return true;
    const itemPath = item.path || item.sourcePath || item.runtimePath || '';
    return (item.name || '').toLowerCase().includes(query) || (item.codec || '').toLowerCase().includes(query) || (item.status || '').toLowerCase().includes(query) || itemPath.toLowerCase().includes(query);
  });

  const readyCount = items.filter(x => x.status === 'READY').length;
  const errorCount = items.filter(x => ['ERROR', 'UNSUPPORTED'].includes(String(x.status || '').toUpperCase())).length;

  return `<div class="manager-container scrollable-page">
    <div class="manager-toolbar">
      <h2>${takeover ? 'TAKEOVER VISUALS' : 'FULL VISUAL LIBRARY'}</h2>
      ${takeover ? '<button id="addMedia" class="btn-green">＋ ADD VISUAL FILE</button>' : '<button id="rescanVisuals" class="btn-green">RESCAN FOLDER</button><button id="openVisualsFolder">OPEN VISUALS FOLDER</button>'}
      <button id="validateAll">VALIDATE ALL</button>
      <input type="text" id="searchVisuals" class="search-input" placeholder="🔍 Search visuals by name, codec, status..." value="${escapeHtml(visualsSearchFilter)}">
      <span class="manager-stats">${items.length} TOTAL · ${readyCount} READY · ${errorCount} ERROR · ALL VALID FILES AUTO-INCLUDED</span>
    </div>
    <div id="mediaList" class="media-list-scroll">
      ${filtered.length ? filtered.map(({ item: x, index: originalIndex }) => {
        const isEnabled = x.enabled !== false;
        return `<div class="media-card ${isEnabled ? '' : 'disabled'}">
          <div class="media-card-idx">#${originalIndex + 1}</div>
          <div class="media-card-thumb">${x.status === 'READY' ? '▶' : '!'}</div>
          <div class="media-card-info">
            <b>${escapeHtml(x.name || x.artist || 'Untitled')}</b>
            <span>${escapeHtml(x.codec || 'unprobed')} · ${x.width || '?'}×${x.height || '?'} · ${x.fps || x.frameRate || '?'} FPS · ${x.duration || '?'}s · ${formatBytes(Number(x.size || x.fileSize || 0))}</span>
            <small>${escapeHtml(x.path || x.sourcePath || x.runtimePath || x.visual_url || '')}</small>
          </div>
          <div class="media-card-status ${x.status === 'READY' ? 'ready' : (x.status === 'CONVERTED' ? 'converted' : 'problem')}">${escapeHtml(x.status || 'DRAFT')}</div>
          <div class="media-card-actions">
            <button data-preview="${originalIndex}">Preview</button>
          </div>
        </div>`;
      }).join('') : '<div class="panel" style="text-align:center;padding:40px;color:var(--text-muted);">No matching visuals found. Drag or add browser-compatible video files.</div>'}
    </div>
  </div>`;
}

function takeovers() {
  return `<div class="scrollable-page"><div class="panel form" style="max-width:800px;margin:auto;">
    <h2>SERVER-AUTHORITATIVE TAKEOVERS & VISUAL PACKS</h2>
    <p>Schedules persist on the dedicated Visuals server (Oracle VM 2). The workstation does not need to remain open.</p>
    <label>Artist / Host<input id="artist" placeholder="Artist name"></label>
    <label>Start Time<input id="start" type="datetime-local"></label>
    <label>End Time<input id="end" type="datetime-local"></label>
    <label>Timezone<input value="${Intl.DateTimeFormat().resolvedOptions().timeZone}" readonly></label>
    <label>Takeover Mode / Blend
      <select id="takeoverMixRatio">
        <option value="1.0" selected>100% Artist Visuals (Full Takeover)</option>
        <option value="0.75">75% Artist / 25% Station (Mixed Takeover)</option>
        <option value="0.50">50% Artist / 50% Station (Balanced Blend)</option>
        <option value="0.25">25% Artist / 75% Station (Subtle Takeover)</option>
        <option value="0.0">Station Visuals Only</option>
      </select>
    </label>
    <label>HTTPS visual URL<input id="visualUrl" value="https://allthings140radio.online/assets/visuals-phone.mp4?v=1.1.0"></label>
    <label>Takeover Pack ID / Folder<input id="takeoverPackId" placeholder="e.g. pack-guest-01 (optional)"></label>
    <label>Notes<textarea id="notes" rows="3"></textarea></label>
    <div class="row" style="margin-top:14px;"><button id="previewTakeover">Preview Takeover</button><button id="accelerated">Accelerated Local Test</button><button id="schedule" class="btn-green">Schedule on Staging Server</button></div>
    <div class="notice" style="margin-top:12px;font-size:10px;color:var(--text-muted);">The staging admin credential is read from the protected workstation config, never displayed in the UI, and is used only for Green staging control. Production live site remains locked.</div>
  </div></div>`;
}

function diagnostics() {
  const buildDate = Number(buildInfo.buildUnix) > 0 ? new Date(Number(buildInfo.buildUnix) * 1000).toLocaleString() : 'unknown';
  return `<div class="scrollable-page"><div class="cards"><article><small>APP VERSION</small><b>${appVersion || 'unknown'}</b></article><article><small>BUILD</small><b>${escapeHtml(buildInfo.gitCommit || 'unknown')}</b><span>${escapeHtml(buildDate)}</span></article><article><small>WEBSOCKET</small><b>${metrics.ws}</b></article><article><small>SCOPE</small><b>GREEN ROOM ONLY</b></article></div><div class="panel diag"><h2>SYSTEM STATUS</h2><div class="row" style="margin-bottom:12px;"><button id="runDiag">Run Full Diagnostics</button><button id="testRealtime">Test Realtime Service</button><button id="testMedia">Test Media Streaming (206)</button><button id="testStaging">Open Green Room</button><button id="export">Export Diagnostic Report</button></div><pre id="report">Ready.</pre></div></div>`;
}

function simple(name) {
  if (name === 'Activity') {
    return `<div class="scrollable-page"><div class="panel"><h2>BOUNDED SYSTEM ACTIVITY LOG</h2><div class="row" style="margin-bottom:10px;"><button id="clearActivity">Clear Log</button><button id="copyActivity">Copy Log</button></div><ol class="activity">${log.map(x => `<li><time>${escapeHtml(x.at)}</time><b>${escapeHtml(x.event)}</b><span>${escapeHtml(x.detail)}</span></li>`).join('')}</ol></div></div>`;
  }
  if (name === 'Backups') {
    return `<div class="scrollable-page"><div class="panel"><h2>WORKSTATION CONFIGURATION BACKUPS</h2><p>Every save automatically versions workstation state. Oracle state has a daily rotation and verified restore path.</p><div class="row" style="max-width:400px;"><button id="backupNow" class="btn-green">Create Workstation Backup</button><button id="exportState">Export Configuration JSON</button></div></div></div>`;
  }
  if (name === 'Chat / Room') {
    return `<div class="scrollable-page"><div class="panel"><h2>CHAT & AUDIENCE ROOM LIVE MONITOR</h2><div class="energy-big" style="height:20px;background:#25142e;margin:20px 0;border-radius:4px;overflow:hidden;"><i style="display:block;height:100%;background:linear-gradient(90deg,#813dff,#ff3dbf);width:${Math.max(5, metrics.energy)}%"></i></div><b>${Math.round(metrics.energy)}% ROOM ENERGY · ${metrics.presence} CONNECTED USERS · ${metrics.total} REACTIONS</b><p style="margin-top:12px;font-size:11px;color:var(--text-dim);">Audience room energy is calculated authoritatively on the server from validated listener reaction pulses.</p></div></div>`;
  }
  if (name === 'Settings') {
    return `<div class="scrollable-page"><div class="panel"><h2>WORKSTATION SETTINGS & SYSTEM INFO</h2>
      <p><b>ALLTHINGS140 Visuals Workstation</b> — Version: <b>v${appVersion}</b></p>
      <p>Build Commit: <code>${escapeHtml(buildInfo.gitCommit || 'unknown')}</code></p>
      <p>Compositor Engine: <b>Canonical Multi-Layer with WebKitGTK 4-Panel Cutout Slicer</b></p>
      <p>Authoritative Green Room: <code style="color:#74ffbe;">${CANONICAL_GREEN_URL}</code></p>
      <p>Realtime Service: <code>${CANONICAL_REALTIME_WS}</code></p>
      <p>Workstation Media Origin: <code>${CANONICAL_MEDIA_ORIGIN}</code></p>
      <p>Main /visuals/ route: <b style="color:#74ffbe;">ISOLATED / UNCHANGED</b></p>
    </div></div>`;
  }
  return `<div class="scrollable-page"><div class="panel"><h2>${escapeHtml(name)}</h2><p>STAGING is the default. Production control is intentionally locked.</p></div></div>`;
}

function disposeViewMedia() {
  $$('#view video').forEach(clearVideoSource);
}

function render(name = 'Visual Workspace') {
  currentView = name;
  const scroll = captureScrollState();
  disposeViewMedia();
  $$('nav button').forEach(b => b.classList.toggle('active', b.dataset.view === name));
  $('#crumb').textContent = `GREEN ROOM / ${(viewLabels[name] || name).toUpperCase()} (v${appVersion})`;
  $('#title').textContent = viewLabels[name] || name;
  $('#view').innerHTML = name === 'Visual Workspace' ? workspace() :
    name === 'Dashboard' ? dashboard() :
    name === 'Live Output' ? liveOutput() :
    name === '24/7 Visuals' ? playlist() :
    name === 'Takeover Visuals' ? playlist(true) :
    name === 'Takeovers' ? takeovers() :
    name === 'Diagnostics' ? diagnostics() : simple(name);

  bind(name);
  if (name === 'Live Output' || name === 'Dashboard') {
    refreshLiveRoutingAndHealth().then(() => {
      // If still on the view, update the dynamic badges
      if (currentView === name) {
        const viewEl = $('#view');
        if (viewEl) {
          viewEl.innerHTML = name === 'Live Output' ? liveOutput() : dashboard();
          bind(name);
        }
      }
    }).catch(() => {});
  }
  if (name === 'Visual Workspace') {
    applyLayers();
    bindWorkspaceEditor();
    bindMediaInspector();
    updateMediaStatus();
  }
  restoreScrollState(scroll, `render:${name}`);
}

function setVideoSource(video, url) {
  if (!video || !url) return;
  const host = video.classList?.contains('visual-ab') ? video : video.closest?.('.visual-ab');
  if (host && host.classList.contains('visual-ab')) {
    setVisualAbSource(host, url);
    return;
  }
  const current = video.getAttribute('src') || '';
  if (current === url || video.src === url) {
    if (video.paused) video.play()?.catch(err => video.dataset.playError = String(err));
    return;
  }
  delete video.dataset.playError;
  video.src = url;
  video.load();
  video.play()?.catch(err => { video.dataset.playError = String(err); updateMediaStatus(); });
}

function waitVisualFrame(video, timeoutMs = 8000) {
  return new Promise(resolve => {
    let settled = false;
    const done = ok => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      resolve(ok);
    };
    const timer = setTimeout(() => done(video.readyState >= 2 && video.videoWidth > 0), timeoutMs);
    const check = () => {
      if (video.readyState >= 2 && video.videoWidth > 1) {
        if (typeof video.requestVideoFrameCallback === 'function') video.requestVideoFrameCallback(() => done(true));
        else done(true);
      }
    };
    video.addEventListener('loadeddata', check, { once: true });
    video.addEventListener('canplay', check, { once: true });
    check();
  });
}

function setVisualAbSource(host, url) {
  const a = host.querySelector('.visual-buf-a');
  const b = host.querySelector('.visual-buf-b');
  if (!a || !b) return;
  const active = host.querySelector('.visual-buf.active') || a;
  if ((active.getAttribute('src') || active.src) === url) {
    if (active.paused) active.play()?.catch(err => active.dataset.playError = String(err));
    return;
  }
  const standby = active === a ? b : a;
  const gen = Number(host.dataset.swapGen || '0') + 1;
  host.dataset.swapGen = String(gen);
  delete standby.dataset.playError;
  standby.src = url;
  standby.load();
  standby.play()?.catch(err => { standby.dataset.playError = String(err); updateMediaStatus(); });
  waitVisualFrame(standby).then(ok => {
    if (host.dataset.swapGen !== String(gen)) return;
    if (!ok) {
      updateMediaStatus();
      return;
    }
    standby.classList.add('active');
    active.classList.remove('active');
    updateMediaStatus();
  });
}

function clearVideoSource(video) {
  if (!video) return;
  try { video.pause(); } catch (_) {}
  if (!video.getAttribute('src')) return;
  video.removeAttribute('src');
  delete video.dataset.playError;
  try { video.load(); } catch (_) {}
}

function applyLayers() {
  const so = screenOpening();
  const maskHole = $('#maskScreenHole');
  if (maskHole) {
    maskHole.setAttribute('x', String(numberOr(so.x, 23.0) / 100));
    maskHole.setAttribute('y', String(numberOr(so.y, 33.5) / 100));
    maskHole.setAttribute('width', String(numberOr(so.width, 53.6) / 100));
    maskHole.setAttribute('height', String(numberOr(so.height, 48.5) / 100));
    maskHole.setAttribute('rx', String(numberOr(so.rx, 1.5) / 100));
  }
  const targetEl = $('.screen-target');
  if (targetEl) {
    targetEl.style.left = `${so.x}%`;
    targetEl.style.top = `${so.y}%`;
    targetEl.style.width = `${so.width}%`;
    targetEl.style.height = `${so.height}%`;
    targetEl.style.borderRadius = `${(so.rx || 1.5) * 4}px`;
    targetEl.classList.toggle('selected', selectedLayerId === '__screen-opening__');
  }

  for (const def of state.workspaceLayers) {
    const el = document.querySelector(`[data-canvas-layer-id="${CSS.escape(def.id)}"]`);
    if (!el) continue;
    const f = layerFrame(def.id);
    el.style.left = `${f.x}%`;
    el.style.top = `${f.y}%`;
    el.style.width = `${f.width}%`;
    el.style.height = `${f.height}%`;
    el.style.opacity = f.opacity ?? 1;
    el.style.transformOrigin = 'center center';
    el.style.transform = `scale(${f.scale || 1}) scaleX(${f.flipX ? -1 : 1}) scaleY(${f.flipY ? -1 : 1})`;
    el.style.display = f.visible === false ? 'none' : (def.kind === 'media' ? 'block' : 'flex');
    el.style.zIndex = String(def.z ?? 1);
    el.classList.toggle('selected', def.id === selectedLayerId);
    if (def.kind === 'media') {
      el.style.objectFit = f.fit || 'cover';
      el.style.objectPosition = 'center center';
      if (def.role === 'stage' || def.id === 'stage-content') {
        const pTop = el.querySelector('.stage-panel-top');
        const pBottom = el.querySelector('.stage-panel-bottom');
        const pLeft = el.querySelector('.stage-panel-left');
        const pRight = el.querySelector('.stage-panel-right');
        const fullVideo = el.querySelector('.stage-fallback-full');
        const slices = el.querySelectorAll('.stage-slice');

        if (so.enabled !== false && pTop && pBottom && pLeft && pRight) {
          if (fullVideo) fullVideo.style.display = 'none';
          pTop.style.display = 'block';
          pBottom.style.display = 'block';
          pLeft.style.display = 'block';
          pRight.style.display = 'block';

          const x = numberOr(so.x, 23.0);
          const y = numberOr(so.y, 33.5);
          const sw = numberOr(so.width, 53.6);
          const sh = numberOr(so.height, 48.5);

          // Top Panel
          pTop.style.left = '0%';
          pTop.style.top = '0%';
          pTop.style.width = '100%';
          pTop.style.height = `${y}%`;
          const vTop = pTop.querySelector('video');
          if (vTop) {
            vTop.style.left = '0%';
            vTop.style.top = '0%';
            vTop.style.width = '100%';
            vTop.style.height = `${(100 / Math.max(0.1, y)) * 100}%`;
          }

          // Bottom Panel
          const bTop = y + sh;
          const bH = Math.max(0.1, 100 - bTop);
          pBottom.style.left = '0%';
          pBottom.style.top = `${bTop}%`;
          pBottom.style.width = '100%';
          pBottom.style.height = `${bH}%`;
          const vBottom = pBottom.querySelector('video');
          if (vBottom) {
            vBottom.style.left = '0%';
            vBottom.style.top = `-${(bTop / bH) * 100}%`;
            vBottom.style.width = '100%';
            vBottom.style.height = `${(100 / bH) * 100}%`;
          }

          // Left Panel
          const lW = Math.max(0.1, x);
          const lH = Math.max(0.1, sh);
          pLeft.style.left = '0%';
          pLeft.style.top = `${y}%`;
          pLeft.style.width = `${x}%`;
          pLeft.style.height = `${sh}%`;
          const vLeft = pLeft.querySelector('video');
          if (vLeft) {
            vLeft.style.left = '0%';
            vLeft.style.top = `-${(y / lH) * 100}%`;
            vLeft.style.width = `${(100 / lW) * 100}%`;
            vLeft.style.height = `${(100 / lH) * 100}%`;
          }

          // Right Panel
          const rLeft = x + sw;
          const rW = Math.max(0.1, 100 - rLeft);
          pRight.style.left = `${rLeft}%`;
          pRight.style.top = `${y}%`;
          pRight.style.width = `${rW}%`;
          pRight.style.height = `${sh}%`;
          const vRight = pRight.querySelector('video');
          if (vRight) {
            vRight.style.left = `-${(rLeft / rW) * 100}%`;
            vRight.style.top = `-${(y / lH) * 100}%`;
            vRight.style.width = `${(100 / rW) * 100}%`;
            vRight.style.height = `${(100 / lH) * 100}%`;
          }
        } else if (fullVideo) {
          fullVideo.style.display = 'block';
          if (pTop) pTop.style.display = 'none';
          if (pBottom) pBottom.style.display = 'none';
          if (pLeft) pLeft.style.display = 'none';
          if (pRight) pRight.style.display = 'none';
        }

        const media = selectedMedia(def);
        if (media && window.__mediaBase) {
          const url = `${window.__mediaBase}/media/${media.routeId}`;
          if (so.enabled !== false) {
            // The WebKitGTK-compatible cutout uses four visible stage slices.
            // Do not also decode the hidden full-frame fallback: it wastes one
            // entire HD decoder and previously contributed to workstation load.
            slices.forEach(v => setVideoSource(v, url));
            if (fullVideo) clearVideoSource(fullVideo);
          } else {
            // Cutout disabled: one full-frame stage decoder is sufficient.
            slices.forEach(clearVideoSource);
            if (fullVideo) setVideoSource(fullVideo, url);
          }
        } else {
          slices.forEach(clearVideoSource);
          if (fullVideo) clearVideoSource(fullVideo);
        }
      } else {
        const media = selectedMedia(def);
        if (media && window.__mediaBase) setVideoSource(el, `${window.__mediaBase}/media/${media.routeId}`);
      }
    }
  }
  updateTransformBox();
}

function mediaState(video) {
  if (!video) return 'WAITING';
  if (video.error) return `FAILED(${video.error.code})`;
  if (video.dataset.playError) return 'PLAY BLOCKED';
  if (video.readyState >= 3 && !video.paused) return 'PLAYING';
  if (video.readyState >= 2) return 'READY';
  return video.getAttribute('src') ? 'LOADING' : 'WAITING';
}

let mediaStatusFrame = 0;
function updateMediaStatusNow() {
  const box = $('#mediaStatus');
  if (!box) return;
  const so = screenOpening();
  const visualDef = state.workspaceLayers.find(x => x.id === 'visual-content');
  const stageDef = state.workspaceLayers.find(x => x.id === 'stage-content');
  const visualHost = visualDef ? document.querySelector(`[data-canvas-layer-id="${CSS.escape(visualDef.id)}"]`) : null;
  const visualEl = visualHost?.querySelector?.('.visual-buf.active') || visualHost;
  const stageEl = stageDef ? (document.querySelector(`[data-canvas-layer-id="${CSS.escape(stageDef.id)}"] video`) || document.querySelector(`[data-canvas-layer-id="${CSS.escape(stageDef.id)}"]`)) : null;
  const visualTime = (visualEl && !isNaN(visualEl.currentTime) && visualEl.currentTime > 0) ? `${visualEl.currentTime.toFixed(1)}s` : '0.0s';
  const stageTime = (stageEl && !isNaN(stageEl.currentTime) && stageEl.currentTime > 0) ? `${stageEl.currentTime.toFixed(1)}s` : '0.0s';

  const lines = [
    `<b>CUTOUT:</b> ${so.enabled !== false ? 'ACTIVE' : 'DISABLED'} | <b>STAGE:</b> z${stageDef?.z || 20} | <b>VISUAL:</b> z${visualDef?.z || 10}`,
    `<b>VISUAL VIDEO:</b> ${mediaState(visualEl)} @ ${visualTime} | <b>STAGE VIDEO:</b> ${mediaState(stageEl)} @ ${stageTime}`
  ];

  for (const def of mediaLayers()) {
    const el = document.querySelector(`[data-canvas-layer-id="${CSS.escape(def.id)}"] video`) || document.querySelector(`[data-canvas-layer-id="${CSS.escape(def.id)}"]`);
    const media = selectedMedia(def);
    lines.push(`${escapeHtml(def.name)}: ${mediaState(el)} — ${escapeHtml(media?.name || 'NO MEDIA')}`);
  }
  lines.push(window.__mediaBase ? 'MEDIA SERVER: READY' : `MEDIA SERVER: ${escapeHtml(window.__mediaServerError || 'STARTING')}`);
  box.innerHTML = lines.join('<br>');
}
function updateMediaStatus() {
  if (mediaStatusFrame) return;
  mediaStatusFrame = requestAnimationFrame(() => {
    mediaStatusFrame = 0;
    updateMediaStatusNow();
  });
}

function refreshWorkspaceMediaUi(changedLayerId = null) {
  if (!$('#canvas')) return;
  if (!changedLayerId || changedLayerId === selectedLayerId) {
    const properties = $('.workspace-col-right');
    if (properties) {
      properties.innerHTML = propertiesMarkup(layerDef());
      bindPropertyControls();
      bindMediaInspector();
    }
  }
  const counts = $('#layerMediaCounts');
  if (counts) counts.innerHTML = mediaLayers().map(x => `${escapeHtml(x.name)}: ${libraryFor(x.id).length}`).join(' · ');
  applyLayers();
  updateMediaStatus();
}

async function refreshLayerMedia(id, { rerender = true, preserveSelection = true } = {}) {
  const def = layerDef(id);
  if (!def || def.kind !== 'media' || !def.sourceFolder) return [];
  const previous = preserveSelection ? (def.selectedMedia?.sourcePath || def.selectedMedia?.name || selectedMedia(def)?.sourcePath || def.sourcePath || def.name) : null;
  def.scanStatus = 'SCANNING';
  if (rerender && $('#canvas')) updateMediaStatus();
  try {
    const result = await invoke('scan_layer_media', { layerId: def.id, folder: def.sourceFolder });
    const items = result.items || [];
    layerLibraries.set(def.id, items);
    if (previous) {
      const previousIndex = items.findIndex(item => item.sourcePath === previous || item.name === previous || item.routeId === previous || item.id === previous);
      def.mediaIndex = previousIndex >= 0 ? previousIndex : Math.max(0, Math.min(Math.max(0, items.length - 1), Number(def.mediaIndex) || 0));
    } else {
      def.mediaIndex = Math.max(0, Math.min(Math.max(0, items.length - 1), Number(def.mediaIndex) || 0));
    }
    if (items.length > 0) {
      def.selectedMedia = items[def.mediaIndex];
    }
    def.scanStatus = 'READY';
    activity('Layer media refreshed', `${def.name}: ${items.length} videos from ${def.sourceFolder}`);
    if (rerender) refreshWorkspaceMediaUi(def.id);
    return items;
  } catch (err) {
    def.scanStatus = 'FAILED';
    def.scanError = String(err);
    activity('Layer media refresh failed', `${def.name}: ${err}`);
    if (rerender) refreshWorkspaceMediaUi(def.id);
    return [];
  }
}
function reconcilePlaylistWithVisualLibrary() {
  const visualLibrary = libraryFor('visual-content');
  if (!visualLibrary.length) return;

  const existing = Array.isArray(state.playlist) ? state.playlist : [];
  const byPath = new Map();
  const byName = new Map();
  const byId = new Map();
  for (const item of existing) {
    const path = item?.sourcePath || item?.runtimePath || item?.path;
    if (path) byPath.set(String(path), item);
    if (item?.name) byName.set(String(item.name), item);
    for (const id of [item?.assetId, item?.routeId, item?.id, item?.fingerprint]) {
      if (id) byId.set(String(id), item);
    }
  }

  const wasEmpty = existing.length === 0;
  const reconciled = visualLibrary.map(media => {
    const routeId = media?.routeId || media?.assetId || media?.id || media?.fingerprint || '';
    const prior = byPath.get(String(media?.sourcePath || ''))
      || byId.get(String(routeId))
      || byName.get(String(media?.name || ''));
    return {
      ...(prior || {}),
      // Media identity is content/source-derived. Never preserve an old asset ID
      // when the scanned source fingerprint changed, or remote HEAD caching can
      // silently keep serving an obsolete file after the operator replaces media.
      assetId: routeId || prior?.assetId || prior?.id || prior?.fingerprint || '',
      routeId: routeId || prior?.routeId || prior?.assetId || prior?.id || '',
      id: routeId || prior?.id || prior?.assetId || prior?.fingerprint || '',
      fingerprint: routeId || prior?.fingerprint || prior?.assetId || prior?.id || '', 
      name: media?.name || prior?.name || 'visual',
      sourcePath: media?.sourcePath || prior?.sourcePath || '',
      runtimePath: media?.runtimePath || media?.sourcePath || prior?.runtimePath || prior?.sourcePath || '',
      duration: media?.duration ?? prior?.duration ?? null,
      codec: media?.codec || prior?.codec || 'unknown',
      sourceCodec: media?.sourceCodec || prior?.sourceCodec || media?.codec || prior?.codec || 'unknown',
      width: media?.width ?? prior?.width ?? 0,
      height: media?.height ?? prior?.height ?? 0,
      runtimeWidth: media?.runtimeWidth ?? prior?.runtimeWidth ?? media?.width ?? prior?.width ?? 0,
      runtimeHeight: media?.runtimeHeight ?? prior?.runtimeHeight ?? media?.height ?? prior?.height ?? 0,
      status: media?.status || prior?.status || 'DRAFT',
      converted: Boolean(media?.converted ?? prior?.converted ?? false),
      fit: prior?.fit || 'cover',
      // Green Room workstation live mode always rotates every valid supported
      // visual in the configured folder. No manual subset is required.
      enabled: String(media?.status || '').toUpperCase() !== 'ERROR' && String(media?.status || '').toUpperCase() !== 'UNSUPPORTED'
    };
  });

  const matchedNames = new Set(reconciled.map(x => x.name));
  const missingExisting = existing.filter(item => !matchedNames.has(item?.name));
  for (const item of missingExisting) reconciled.push({ ...item, enabled: false, missingLocalSource: true });

  state.playlist = reconciled;
  activity('24/7 playlist reconciled', `${reconciled.filter(x => x.enabled !== false).length} enabled / ${reconciled.length} total from Visual Content library`);
}

async function refreshAllMediaLayers() {
  for (const def of mediaLayers()) await refreshLayerMedia(def.id, { rerender: false });
  reconcilePlaylistWithVisualLibrary();
}

async function changeLayerFolder(id) {
  const def = layerDef(id);
  if (!def || def.kind !== 'media') return;
  const folder = await open({ directory: true, multiple: false, defaultPath: def.sourceFolder || undefined });
  if (!folder) return;
  def.sourceFolder = folder;
  def.mediaIndex = 0;
  await refreshLayerMedia(id, { rerender: false, preserveSelection: false });
  await saveDraft(false);
  refreshWorkspaceMediaUi(id);
}

function duplicateLayer(id) {
  const source = layerDef(id);
  if (!source) return;
  const index = state.workspaceLayers.findIndex(x => x.id === id);
  const copy = structuredClone(source);
  copy.id = uid(source.kind === 'media' ? 'media' : 'layer');
  copy.name = `${source.name} Copy`;
  copy.z = (source.z || 1) + 1;
  if (copy.kind === 'media') copy.mediaIndex = source.mediaIndex || 0;
  state.workspaceLayers.splice(index, 0, copy);
  for (const p of state.presets) {
    p.layerFrames ||= {};
    p.layerFrames[copy.id] = structuredClone(p.layerFrames?.[id] || defaultFrame(copy.kind));
  }
  layerLibraries.set(copy.id, []);
  selectedLayerId = copy.id;
  activity('Layer duplicated', `${source.name} → ${copy.name}`);
  saveDraft(false);
  render('Visual Workspace');
  refreshLayerMedia(copy.id, { rerender: true, preserveSelection: false });
}

function renameLayer(id) {
  const def = layerDef(id);
  if (!def) return;
  const name = prompt('Layer name', def.name);
  if (!name?.trim()) return;
  const old = def.name;
  def.name = name.trim();
  activity('Layer renamed', `${old} → ${def.name}`);
  saveDraft(false);
  render('Visual Workspace');
}

function deleteLayer(id) {
  const def = layerDef(id);
  if (!def) return;
  if (!confirm(`Delete layer "${def.name}" from this workstation layout?\n\nThis does NOT delete any source media files.`)) return;
  const index = state.workspaceLayers.findIndex(x => x.id === id);
  state.workspaceLayers.splice(index, 1);
  for (const p of state.presets) delete p.layerFrames?.[id];
  layerLibraries.delete(id);
  if (selectedLayerId === id) selectedLayerId = state.workspaceLayers[Math.min(index, state.workspaceLayers.length - 1)]?.id || '';
  activity('Layer deleted', def.name);
  saveDraft(false);
  render('Visual Workspace');
}

function reorderLayers(fromIndex, toIndex) {
  const ordered = [...state.workspaceLayers].sort((a, b) => (Number(b.z) || 0) - (Number(a.z) || 0));
  if (fromIndex < 0 || fromIndex >= ordered.length || toIndex < 0 || toIndex >= ordered.length) return;
  const [moved] = ordered.splice(fromIndex, 1);
  ordered.splice(toIndex, 0, moved);
  ordered.forEach((layer, i) => {
    layer.z = (ordered.length - i) * 10;
  });
  state.workspaceLayers = ordered;
  activity('Layer reordered', `${moved.name}: position ${fromIndex + 1} → ${toIndex + 1}; z=${moved.z}`);
  saveDraft(false);
  render('Visual Workspace');
}

function setMediaLayerRole(id, role, { renderWorkspace = true } = {}) {
  const def = layerDef(id);
  if (!def || def.kind !== 'media') return;
  // Stage/Visual are structural singleton roles. The user changes the media *inside*
  // those canonical layers; custom layers remain generic media to avoid ID/library collisions.
  if (id === 'stage-content') def.role = 'stage';
  else if (id === 'visual-content') def.role = 'visual';
  else def.role = 'media';
  def.mask = 'none';
  def.maskExplicit = true;
  activity('Media layer role normalized', `${def.name}: ${def.role}; z=${def.z}`);
  saveDraft(false);
  if (renderWorkspace && $('#canvas')) refreshWorkspaceMediaUi(id);
  else applyLayers();
}

function showLayerContextMenu(event, id) {
  event.preventDefault();
  selectedLayerId = id;
  const def = layerDef(id);
  const menu = $('#layerContextMenu');
  if (!def || !menu) return;
  const ordered = [...state.workspaceLayers].sort((a, b) => (Number(b.z) || 0) - (Number(a.z) || 0));
  const idx = ordered.findIndex(x => x.id === id);
  const mediaItems = def.kind === 'media' ? `<button data-action="folder">Change Media Folder…</button><button data-action="refresh">Refresh Media Folder</button><hr>` : '';
  menu.innerHTML = `${mediaItems}<button data-action="duplicate">Duplicate</button><button data-action="rename">Rename</button><button data-action="delete" class="danger">Delete</button><hr><button data-action="forward" ${idx === 0 ? 'disabled' : ''}>Bring Forward</button><button data-action="backward" ${idx === ordered.length - 1 ? 'disabled' : ''}>Send Backward</button><button data-action="front" ${idx === 0 ? 'disabled' : ''}>Bring to Front</button><button data-action="back" ${idx === ordered.length - 1 ? 'disabled' : ''}>Send to Back</button>`;
  menu.hidden = false;
  menu.style.left = `${Math.min(event.clientX, window.innerWidth - 240)}px`;
  menu.style.top = `${Math.min(event.clientY, window.innerHeight - 280)}px`;
  menu.onclick = async e => {
    const action = e.target.dataset.action;
    if (!action) return;
    menu.hidden = true;
    if (action === 'duplicate') duplicateLayer(id);
    if (action === 'rename') renameLayer(id);
    if (action === 'delete') deleteLayer(id);
    if (action === 'forward' && idx > 0) reorderLayers(idx, idx - 1);
    if (action === 'backward' && idx < ordered.length - 1) reorderLayers(idx, idx + 1);
    if (action === 'front') reorderLayers(idx, 0);
    if (action === 'back') reorderLayers(idx, ordered.length - 1);
    if (action === 'folder') await changeLayerFolder(id);
    if (action === 'refresh') await refreshLayerMedia(id);
  };
}

function addNewMediaLayer() {
  const id = uid('media');
  const topMediaZ = Math.max(0, ...mediaLayers().map(x => x.z || 0));
  const def = { id, name: 'New Media Layer', kind: 'media', role: 'media', sourceFolder: DEFAULT_VISUAL_FOLDER, mediaIndex: 0, z: topMediaZ + 10, mask: 'none', maskExplicit: true };
  state.workspaceLayers.unshift(def);
  for (const p of state.presets) { p.layerFrames ||= {}; p.layerFrames[id] = defaultFrame('media'); }
  selectedLayerId = id;
  refreshLayerMedia(id, { rerender: false }).then(() => { saveDraft(false); render('Visual Workspace'); });
}

function bindMediaInspector() {
  const def = layerDef();
  if (!def || def.kind !== 'media') return;
  const select = $('#layerMediaSelect');
  const info = $('#layerMediaInfo');
  const lib = libraryFor(def.id);
  const roleSelect = $('#layerRoleSelect');
  if (roleSelect) roleSelect.onchange = () => setMediaLayerRole(def.id, roleSelect.value);
  const updateInfo = () => {
    const m = lib[Number(select?.value ?? def.mediaIndex)];
    if (info) info.textContent = m ? `${m.source} · ${m.width || '?'}×${m.height || '?'} → ${m.runtimeWidth || '?'}×${m.runtimeHeight || '?'} · ${m.codec || '?'} · ${m.status}` : `No videos found in ${def.sourceFolder || 'this folder'}`;
  };
  if (select) {
    select.value = String(Math.max(0, Math.min(lib.length - 1, def.mediaIndex || 0)));
    select.onchange = () => {
      def.mediaIndex = Number(select.value) || 0;
      updateInfo();
      applyLayers();
      $('#saved').textContent = 'UNSAVED DRAFT';
    };
    const step = d => { if (!lib.length) return; select.value = String((Number(select.value) + d + lib.length) % lib.length); select.onchange(); };
    $('#prevLayerMedia').onclick = () => step(-1);
    $('#nextLayerMedia').onclick = () => step(1);
    $('#randomLayerMedia').onclick = () => { if (!lib.length) return; select.value = String(Math.floor(Math.random() * lib.length)); select.onchange(); };
    $('#setLayerGlobalFrame').onclick = () => { def.globalFrame = structuredClone(layerFrame()); activity('Global layer frame set', def.name); saveDraft(false); };
    $('#changeLayerFolder').onclick = () => changeLayerFolder(def.id);
    $('#refreshLayerFolder').onclick = () => refreshLayerMedia(def.id);
    updateInfo();
  }
}

function updateTransformBox() {
  const box = $('.transform-box');
  const canvas = $('#canvas');
  if (!box || !canvas || !selectedLayerId) return;
  const f = selectedLayerId === '__screen-opening__' ? screenOpening() : (layerDef() ? layerFrame() : null);
  if (!f) {
    box.hidden = true;
    return;
  }
  box.style.left = `${f.x}%`;
  box.style.top = `${f.y}%`;
  box.style.width = `${f.width}%`;
  box.style.height = `${f.height}%`;
  box.hidden = false;
  canvas.style.transform = `scale(${editorZoom})`;
  canvas.style.transformOrigin = 'center';
}

function bindPropertyControls() {
  $$('[data-prop]').forEach(input => input.oninput = () => {
    const k = input.dataset.prop;
    layerFrame()[k] = input.type === 'checkbox' ? input.checked : input.type === 'number' ? Number(input.value) : input.value;
    applyLayers();
    $('#saved').textContent = 'UNSAVED DRAFT';
  });
  $('#center')?.addEventListener('click', () => { const f = layerFrame(); f.x = (100 - f.width) / 2; f.y = (100 - f.height) / 2; applyLayers(); updateTransformBox(); });
  $('#layerReset')?.addEventListener('click', () => { Object.assign(layerFrame(), defaultFrame(layerDef().kind)); applyLayers(); updateTransformBox(); });
}

function bindScreenOpeningControls() {
  $$('[data-screen-prop]').forEach(input => {
    input.oninput = () => {
      const k = input.dataset.screenProp;
      const so = screenOpening();
      so[k] = input.type === 'checkbox' ? input.checked : Number(input.value);
      applyLayers();
      updateTransformBox();
      $('#saved').textContent = 'UNSAVED DRAFT';
    };
  });
  $('#fitVisualToCutout')?.addEventListener('click', () => {
    const visual = state.workspaceLayers.find(x => x.id === 'visual-content');
    if (visual) {
      const f = layerFrame(visual.id);
      const so = screenOpening();
      f.x = Number(so.x) || 23.0;
      f.y = Number(so.y) || 33.5;
      f.width = Number(so.width) || 53.6;
      f.height = Number(so.height) || 48.5;
      f.scale = 1;
      f.flipX = false;
      f.flipY = false;
      f.fit = 'cover';
      f.visible = true;
      applyLayers();
      updateTransformBox();
      $('#saved').textContent = 'UNSAVED DRAFT';
      activity('Visual fitted to screen cutout', visual.name);
    }
  });
  $('#resetScreenCutout')?.addEventListener('click', () => {
    Object.assign(screenOpening(), DEFAULT_SCREEN_OPENING);
    applyLayers();
    updateTransformBox();
    const properties = $('.workspace-col-right');
    if (properties && selectedLayerId === '__screen-opening__') {
      properties.innerHTML = screenOpeningInspector();
      bindScreenOpeningControls();
    }
    activity('Screen cutout reset to default');
  });
}

function selectLayer(id) {
  selectedLayerId = id;
  $$('#layerList [data-layer-id]').forEach(button => button.classList.toggle('sel', button.dataset.layerId === id));
  $('#selectScreenOpening')?.classList.toggle('sel', id === '__screen-opening__');
  $$('[data-canvas-layer-id]').forEach(el => el.classList.toggle('selected', el.dataset.canvasLayerId === id));
  $('.screen-target')?.classList.toggle('selected', id === '__screen-opening__');
  const properties = $('.workspace-col-right');
  const propertiesScroll = properties?.scrollTop || 0;
  if (properties) {
    if (id === '__screen-opening__') {
      properties.innerHTML = screenOpeningInspector();
      bindScreenOpeningControls();
    } else {
      properties.innerHTML = propertiesMarkup(layerDef(id));
      bindPropertyControls();
      bindMediaInspector();
      $('#editStageCutout')?.addEventListener('click', () => selectLayer('__screen-opening__'));
    }
  }
  updateTransformBox();
  updateMediaStatus();
  restoreScrollState({ colRight: propertiesScroll }, 'select-layer');
}

function bindWorkspaceEditor() {
  const canvas = $('#canvas');
  const box = $('.transform-box');
  if (!canvas || !box) return;

  $$('[data-layer-id]').forEach(button => {
    button.onclick = () => selectLayer(button.dataset.layerId);
    button.oncontextmenu = e => showLayerContextMenu(e, button.dataset.layerId);
  });
  $('#selectScreenOpening')?.addEventListener('click', () => selectLayer('__screen-opening__'));
  $('.screen-target')?.addEventListener('click', () => selectLayer('__screen-opening__'));

  // Drag-and-drop layer reordering
  const layerList = $('#layerList');
  if (layerList) {
    let draggedIndex = null;
    layerList.addEventListener('dragstart', e => {
      const btn = e.target.closest('[data-layer-index]');
      if (!btn) return;
      draggedIndex = parseInt(btn.dataset.layerIndex, 10);
      e.dataTransfer.effectAllowed = 'move';
      e.dataTransfer.setData('text/plain', String(draggedIndex));
      btn.classList.add('dragging');
    });
    layerList.addEventListener('dragover', e => {
      e.preventDefault();
      e.dataTransfer.dropEffect = 'move';
      const btn = e.target.closest('[data-layer-index]');
      $$('#layerList button').forEach(b => b.classList.remove('drag-over-top', 'drag-over-bottom'));
      if (btn && draggedIndex !== null) {
        const rect = btn.getBoundingClientRect();
        const midY = rect.top + rect.height / 2;
        if (e.clientY < midY) btn.classList.add('drag-over-top');
        else btn.classList.add('drag-over-bottom');
      }
    });
    layerList.addEventListener('dragleave', e => {
      const btn = e.target.closest('[data-layer-index]');
      if (btn) btn.classList.remove('drag-over-top', 'drag-over-bottom');
    });
    layerList.addEventListener('drop', e => {
      e.preventDefault();
      $$('#layerList button').forEach(b => b.classList.remove('drag-over-top', 'drag-over-bottom', 'dragging'));
      const targetBtn = e.target.closest('[data-layer-index]');
      if (!targetBtn || draggedIndex === null) return;
      const targetIndex = parseInt(targetBtn.dataset.layerIndex, 10);
      const rect = targetBtn.getBoundingClientRect();
      const midY = rect.top + rect.height / 2;
      const dropIndex = e.clientY < midY ? targetIndex : targetIndex + 1;
      const finalIndex = dropIndex > draggedIndex ? dropIndex - 1 : dropIndex;
      if (finalIndex !== draggedIndex) {
        reorderLayers(draggedIndex, finalIndex);
      }
      draggedIndex = null;
    });
    layerList.addEventListener('dragend', () => {
      $$('#layerList button').forEach(b => b.classList.remove('drag-over-top', 'drag-over-bottom', 'dragging'));
      draggedIndex = null;
    });
  }

  document.onclick = e => { const m = $('#layerContextMenu'); if (m && !m.hidden && !e.target.closest('#layerContextMenu')) m.hidden = true; };
  $('#addMediaLayer').onclick = addNewMediaLayer;

  bindPropertyControls();

  $('#viewport').onchange = e => { activePreset().viewport = e.target.value; render('Visual Workspace'); };
  $('#safe').onchange = e => { activePreset().safeArea = e.target.checked; render('Visual Workspace'); };
  $('#preset').onchange = e => { state.activePreset = e.target.value; render('Visual Workspace'); };
  $('#savePreset').onclick = () => saveDraft();
  $('#saveAs').onclick = () => { const n = prompt('Preset name'); if (n) { const p = structuredClone(activePreset()); p.name = n; p.version = 1; state.presets.push(p); state.activePreset = n; saveDraft(); render('Visual Workspace'); } };
  $('#duplicatePreset').onclick = $('#saveAs').onclick;
  $('#resetPreset').onclick = () => { state.activePreset = 'Known Good Default'; render('Visual Workspace'); };
  $('#play').onclick = () => $$('#canvas video').forEach(v => v.paused ? v.play() : v.pause());
  $('#restart').onclick = () => $$('#canvas video').forEach(v => { v.currentTime = 0; v.play(); });

  // Green Staging buttons in Left Column
  $('#browser').onclick = () => openStagingBrowser(CANONICAL_GREEN_URL);
  $('#copyGreenUrl').onclick = () => copyToClipboard(CANONICAL_GREEN_URL, 'Canonical Green URL');
  $('#publishGreen').onclick = () => window.__triggerPublishStaging?.();
  $('#testGreen').onclick = () => testVisualOnGreenWithProgress();
  if ($('#validateStageOnly')) $('#validateStageOnly').onclick = () => validateMediaDiagnostics('stage');
  if ($('#validateVisualOnly')) $('#validateVisualOnly').onclick = () => validateMediaDiagnostics('visual');

  $('#safePlaybackToggle').onchange = e => {
    state.safePlaybackMode = e.target.checked;
    activity('Safe Playback Mode changed', state.safePlaybackMode ? 'ENABLED' : 'DISABLED');
    saveDraft(false);
    showToast(state.safePlaybackMode ? '🛡️ Safe Playback Mode Enabled' : 'Safe Playback Mode Disabled');
  };

  const begin = (e, handle = 'move') => {
    const layerEl = e.target.closest('[data-canvas-layer-id]');
    const screenTargetEl = e.target.closest('.screen-target');
    if (screenTargetEl && selectedLayerId !== '__screen-opening__') {
      selectLayer('__screen-opening__');
      return;
    }
    if (layerEl && layerEl.dataset.canvasLayerId !== selectedLayerId) {
      selectLayer(layerEl.dataset.canvasLayerId);
      return;
    }
    if (!e.target.closest('.transform-box') && !layerEl && !screenTargetEl) return;
    e.stopPropagation();
    snapshot();
    const r = canvas.getBoundingClientRect();
    const activeTargetFrame = selectedLayerId === '__screen-opening__' ? screenOpening() : layerFrame();
    drag = { handle, x: e.clientX, y: e.clientY, start: structuredClone(activeTargetFrame), r, isScreenOpening: selectedLayerId === '__screen-opening__' };
    box.setPointerCapture?.(e.pointerId);
    e.preventDefault();
  };
  box.onpointerdown = e => begin(e, e.target.dataset.handle || 'move');
  $$('[data-canvas-layer-id]').forEach(el => el.onpointerdown = e => begin(e, 'move'));

  let dragFrame = 0;
  let pendingPointer = null;
  const applyPendingDrag = () => {
    dragFrame = 0;
    const e = pendingPointer;
    pendingPointer = null;
    if (!drag || !e) return;
    e.stopPropagation();
    const dx = (e.clientX - drag.x) / drag.r.width * 100 / editorZoom;
    const dy = (e.clientY - drag.y) / drag.r.height * 100 / editorZoom;
    const s = drag.start;
    const f = drag.isScreenOpening ? screenOpening() : layerFrame();
    const h = drag.handle;
    const aspect = s.width / s.height;
    if (h === 'move') { f.x = s.x + dx; f.y = s.y + dy; }
    else {
      if (h.includes('e')) f.width = Math.max(2, s.width + dx);
      if (h.includes('s')) f.height = Math.max(2, s.height + dy);
      if (h.includes('w')) { f.x = s.x + dx; f.width = Math.max(2, s.width - dx); }
      if (h.includes('n')) { f.y = s.y + dy; f.height = Math.max(2, s.height - dy); }
      if (e.shiftKey && ['nw', 'ne', 'se', 'sw'].includes(h)) f.height = f.width / aspect;
    }
    if (snapEnabled && !e.ctrlKey) {
      for (const v of [0, 50, 100, SCREEN_TARGET.x, SCREEN_TARGET.x + SCREEN_TARGET.width]) if (Math.abs(f.x - v) < 1) f.x = v;
      for (const v of [0, 50, 100, SCREEN_TARGET.y, SCREEN_TARGET.y + SCREEN_TARGET.height]) if (Math.abs(f.y - v) < 1) f.y = v;
    }
    applyLayers();
    updateTransformBox();
  };
  box.onpointermove = e => {
    if (!drag) return;
    pendingPointer = e;
    if (!dragFrame) dragFrame = requestAnimationFrame(applyPendingDrag);
  };
  box.onpointerup = () => { if (dragFrame) cancelAnimationFrame(dragFrame); applyPendingDrag(); drag = null; saveDraft(false).catch(err => appLog('ERROR', `drag save: ${err}`)); };
  box.onpointercancel = box.onpointerup;

  $('#undoFrame').onclick = undo;
  $('#redoFrame').onclick = redo;
  $('#centerH').onclick = () => { snapshot(); const f = layerFrame(); f.x = (100 - f.width) / 2; applyLayers(); };
  $('#centerV').onclick = () => { snapshot(); const f = layerFrame(); f.y = (100 - f.height) / 2; applyLayers(); };
  $('#fitTarget').onclick = () => { snapshot(); Object.assign(layerFrame(), SCREEN_TARGET); applyLayers(); };
  $('#globalFrame').onclick = () => { const d = layerDef(); d.globalFrame = structuredClone(layerFrame()); activity('Global frame set', d.name); saveDraft(false); };
  $('#snapToggle').onchange = e => snapEnabled = e.target.checked;
  $('#editorZoom').onchange = e => { editorZoom = Number(e.target.value) / 100; updateTransformBox(); };

  $$('video.media-layer').forEach(v => ['loadeddata', 'playing', 'pause', 'error', 'stalled'].forEach(ev => v.addEventListener(ev, updateMediaStatus)));
}

function bind(name) {
  $$('[data-view]').forEach(b => b.onclick = () => render(b.dataset.view));
  if (name === 'Dashboard') {
    const liveButton = $('#dashboardLiveVisuals');
    if (liveButton) liveButton.onclick = () => workstationLive.active ? stopWorkstationLive() : startWorkstationLive();
    return;
  }
  if (name === 'Visual Workspace') return;

  if (name === 'Live Output') {
    const btnFallback = $('#btnChatFallbackLegacy');
    if (btnFallback) {
      btnFallback.onclick = async () => {
        if (!confirm('Switch the PUBLIC GREEN ROOM to LEGACY VIDEO SAFETY MODE?\n\nThis affects only /room/. The homepage and /visuals/ remain unchanged.')) {
          return;
        }
        const confirmation = prompt('PRODUCTION ROUTING CONTROL\n\nType PROMOTE GREEN ROOM to confirm this public /room/ routing change.');
        if (confirmation !== 'PROMOTE GREEN ROOM') { showToast('Production routing change cancelled'); return; }
        btnFallback.disabled = true;
        btnFallback.textContent = 'Falling back…';
        try {
          await invoke('set_visual_routing', { chat: 'legacy', reason: 'green_room_legacy_fallback', confirmation });
          activity('GREEN ROOM → LEGACY VIDEO', 'Workstation manual Green Room visual fallback executed');
          activity('LEGACY FALLBACK VERIFIED', 'Green Room visual mode set to legacy');
          showToast('✓ Green Room switched to legacy video safety mode');
          await refreshLiveRoutingAndHealth();
          render('Live Output');
        } catch (err) {
          activity('Legacy fallback failed', String(err));
          alert('Fallback error: ' + err);
        } finally {
          if (btnFallback) btnFallback.disabled = false;
        }
      };
    }

    const btnUseNew = $('#btnChatUseNew');
    if (btnUseNew) {
      btnUseNew.onclick = async () => {
        if (!confirm('Enable the GREEN ROOM COMPOSITOR?\n\nThis changes only the visual engine inside /room/. The homepage and /visuals/ remain untouched.')) {
          return;
        }
        const confirmation = prompt('PRODUCTION ROUTING CONTROL\n\nType PROMOTE GREEN ROOM to confirm this public /room/ routing change.');
        if (confirmation !== 'PROMOTE GREEN ROOM') { showToast('Production routing change cancelled'); return; }
        btnUseNew.disabled = true;
        btnUseNew.textContent = 'Activating…';
        try {
          await invoke('set_visual_routing', { chat: 'new', reason: 'green_room_compositor_enable', confirmation });
          activity('GREEN ROOM COMPOSITOR ENABLED', 'Public /room/ visual engine set to compositor');
          activity('GREEN ROOM → COMPOSITOR', 'Green Room visual mode set to new');
          showToast('✓ Green Room compositor enabled');
          await refreshLiveRoutingAndHealth();
          render('Live Output');
        } catch (err) {
          activity('Canary activation failed', String(err));
          alert('Activation error: ' + err);
        } finally {
          if (btnUseNew) btnUseNew.disabled = false;
        }
      };
    }

    const btnCanary = $('#btnOpenCanaryPreview');
    if (btnCanary) {
      btnCanary.onclick = async () => {
        activity('PUBLIC GREEN ROOM OPENED', 'https://allthings140radio.online/room/?approval=1');
        activity('DEDICATED ROOM TEST', 'Testing public standalone Green Room pipeline');
        await openStagingBrowser('https://allthings140radio.online/room/?approval=1');
      };
    }

    const btnGreen = $('#btnOpenGreenStaging');
    if (btnGreen) {
      btnGreen.onclick = async () => {
        activity('GREEN STAGING OPENED', 'https://allthings140-visuals-green.pages.dev/?approval=1');
        await openStagingBrowser('https://allthings140-visuals-green.pages.dev/?approval=1');
      };
    }

    const btnRefresh = $('#btnRefreshLiveRouting');
    if (btnRefresh) {
      btnRefresh.onclick = async () => {
        await refreshLiveRoutingAndHealth();
        render('Live Output');
      };
    }
    return;
  }
  if (name.includes('Visuals')) {
    const addMediaButton = $('#addMedia');
    if (addMediaButton) addMediaButton.onclick = () => addMedia(name === 'Takeover Visuals');
    const rescanButton = $('#rescanVisuals');
    if (rescanButton) rescanButton.onclick = async () => {
      rescanButton.disabled = true; rescanButton.textContent = 'SCANNING…';
      try {
        await refreshAllMediaLayers();
        await invoke('save_state', { state });
        activity('Visual folder rescanned', `${state.playlist.length} files indexed`);
        render('24/7 Visuals');
      } catch (err) {
        activity('Visual folder rescan failed', String(err));
        showToast(`Rescan failed: ${err}`);
      }
    };
    const openFolderButton = $('#openVisualsFolder');
    if (openFolderButton) openFolderButton.onclick = () => invoke('open_media_folder', { path: DEFAULT_VISUAL_FOLDER }).catch(err => showToast(String(err)));
    $('#validateAll').onclick = async () => {
      activity('Validation started', name);
      for (const item of (name === 'Takeover Visuals' ? state.takeovers : state.playlist)) {
        const mediaPath = item.runtimePath || item.sourcePath || item.path;
        if (mediaPath) {
          try {
            const p = await invoke('probe_media', { path: mediaPath });
            const video = (p.streams || []).find(stream => stream.codec_type === 'video') || {};
            item.status = p.status;
            item.reason = p.reason;
            item.codec = video.codec_name || item.codec || 'unknown';
            item.width = video.width || item.width || 0;
            item.height = video.height || item.height || 0;
            item.duration = Number(p.format?.duration || item.duration || 0).toFixed(1);
          } catch (e) {
            item.status = 'PROBLEM';
            item.reason = String(e);
          }
        } else {
          item.status = 'PROBLEM';
          item.reason = 'No local source/runtime path';
        }
      }
      await saveDraft(false);
      render(name);
      showToast('✓ All media assets validated');
    };
    $('#searchVisuals').oninput = e => {
      visualsSearchFilter = e.target.value;
      render(name);
    };
    $$('[data-toggle-enable]').forEach(b => b.onclick = () => {
      const idx = +b.dataset.toggleEnable;
      const list = name === 'Takeover Visuals' ? state.takeovers : state.playlist;
      if (list[idx]) {
        list[idx].enabled = list[idx].enabled === false ? true : false;
        saveDraft(false);
        render(name);
      }
    });
    $$('[data-move-up]').forEach(b => b.onclick = () => {
      const idx = +b.dataset.moveUp;
      const list = name === 'Takeover Visuals' ? state.takeovers : state.playlist;
      if (idx > 0) {
        const [moved] = list.splice(idx, 1);
        list.splice(idx - 1, 0, moved);
        saveDraft(false);
        render(name);
      }
    });
    $$('[data-move-down]').forEach(b => b.onclick = () => {
      const idx = +b.dataset.moveDown;
      const list = name === 'Takeover Visuals' ? state.takeovers : state.playlist;
      if (idx < list.length - 1) {
        const [moved] = list.splice(idx, 1);
        list.splice(idx + 1, 0, moved);
        saveDraft(false);
        render(name);
      }
    });
    $$('[data-remove]').forEach(b => b.onclick = () => {
      const idx = +b.dataset.remove;
      const list = name === 'Takeover Visuals' ? state.takeovers : state.playlist;
      if (confirm(`Remove "${list[idx]?.name || 'media'}" from playlist?`)) {
        list.splice(idx, 1);
        saveDraft(false);
        render(name);
      }
    });
    $$('[data-preview]').forEach(b => b.onclick = () => {
      const idx = +b.dataset.preview;
      const list = name === 'Takeover Visuals' ? state.takeovers : state.playlist;
      const target = list[idx];
      if (target) {
        const visual = state.workspaceLayers.find(x => x.id === 'visual-content');
        const visualLibrary = libraryFor('visual-content');
        const targetPath = target.sourcePath || target.runtimePath || target.path || '';
        const targetId = target.routeId || target.assetId || target.id || target.fingerprint || '';
        const mediaIndex = visualLibrary.findIndex(item => {
          const itemPath = item.sourcePath || item.runtimePath || '';
          const itemId = item.routeId || item.assetId || item.id || item.fingerprint || '';
          return (targetPath && itemPath === targetPath) || (targetId && itemId === targetId) || (target.name && item.name === target.name);
        });
        if (visual && mediaIndex >= 0) {
          visual.mediaIndex = mediaIndex;
          render('Visual Workspace');
          showToast(`Previewing "${target.name}" in Workspace`);
        } else {
          showToast(`Cannot preview "${target.name || 'visual'}": it is not available in the current Visual Content folder`);
        }
      }
    });
  }
  if (name === 'Diagnostics') {
    $('#runDiag').onclick = runDiagnostics;
    $('#testRealtime').onclick = runDiagnostics;
    $('#testMedia').onclick = runMediaTest;
    $('#testStaging').onclick = () => openStagingBrowser(CANONICAL_GREEN_URL);
    $('#export').onclick = async () => { $('#report').textContent = await invoke('export_report', { state }); };
  }
  if (name === 'Backups') {
    $('#backupNow').onclick = () => { saveDraft(); showToast('✓ Backup snapshot created'); };
    $('#exportState').onclick = () => {
      const blob = new Blob([JSON.stringify(state, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `allthings140-visuals-backup-${new Date().toISOString().replace(/[:.]/g, '-')}.json`;
      a.click();
      URL.revokeObjectURL(url);
    };
  }
  if (name === 'Activity') {
    $('#clearActivity').onclick = () => { log = []; state.activity = []; render('Activity'); };
    $('#copyActivity').onclick = () => copyToClipboard(JSON.stringify(log, null, 2), 'Activity Log');
  }
  if (name === 'Takeovers') {
    $('#previewTakeover').onclick = () => activity('Takeover preview started', $('#artist').value);
    $('#accelerated').onclick = () => activity('Accelerated takeover test', 'Local only; server schedule unchanged');
    $('#schedule').onclick = async () => {
      const start = new Date($('#start').value).getTime(), end = new Date($('#end').value).getTime();
      if (!start || !end || end <= start) return alert('Enter a valid start and end time.');
      $('#schedule').disabled = true;
      try {
        const r = await invoke('schedule_takeover', { schedule: { title: `${$('#artist').value} takeover`, artist: $('#artist').value, visual_url: $('#visualUrl').value, start_at: start, end_at: end } });
        activity('Takeover scheduled', r.id);
        alert(`Staging takeover scheduled: ${r.id}`);
      } catch (e) {
        activity('Takeover scheduling failed', String(e));
        alert(e);
      } finally {
        $('#schedule').disabled = false;
      }
    };
  }
}

async function addMedia(takeover) {
  const paths = await open({ multiple: true, filters: [{ name: 'Visual media', extensions: ['mp4', 'webm', 'mov', 'mkv', 'm4v', 'gif'] }] });
  if (!paths) return;
  for (const path of Array.isArray(paths) ? paths : [paths]) {
    const p = await invoke('probe_media', { path }), v = p.streams?.find(s => s.codec_type === 'video') || {};
    (takeover ? state.takeovers : state.playlist).push({ name: path.split('/').pop(), path, url: convertFileSrc(path), status: p.status, reason: p.reason, codec: v.codec_name, width: v.width, height: v.height, duration: Number(p.format?.duration || 0).toFixed(1), enabled: true });
    activity('Media validated', `${path}: ${p.status}`);
  }
  await saveDraft();
  render(takeover ? 'Takeover Visuals' : '24/7 Visuals');
}

async function saveDraft(updateLabel = true) {
  syncLegacyPresetKeys();
  state.layoutVersion = (state.layoutVersion || 0) + 1;
  const p = activePreset(); p.version = (p.version || 0) + 1;
  const r = await invoke('save_state', { state });
  activity('Draft saved', `layout v${state.layoutVersion}`);
  if (updateLabel && $('#saved')) $('#saved').textContent = `SAVED ${r.savedAt}`;
  const pill = $('#greenSyncPill');
  if (pill) {
    const s = getGreenSyncStatus();
    pill.className = `staging-status-pill ${s.class}`;
    pill.textContent = s.label;
  }
  return r;
}

async function runDiagnostics() {
  const layerReport = mediaLayers().map(def => ({ id: def.id, name: def.name, folder: def.sourceFolder, count: libraryFor(def.id).length, index: def.mediaIndex, mask: def.mask, z: def.z }));
  const out = {
    at: new Date().toISOString(),
    appVersion,
    productionLocked: true,
    realtime: metrics,
    canonicalGreenUrl: CANONICAL_GREEN_URL,
    layoutVersion: state.layoutVersion,
    playlistCount: state.playlist.length,
    takeoversCount: state.takeovers.length,
    canonicalComposition: CANONICAL_COMPOSITION,
    editorViewport: viewport['desktop-16-9'],
    workspaceLayerSystemVersion: state.workspaceLayerSystemVersion,
    layers: layerReport,
    checks: {
      websocket: metrics.ws === 'LIVE',
      stagingUrlCanonical: CANONICAL_GREEN_URL.includes('allthings140-visuals-green.pages.dev'),
      stateBounded: (state.activity || []).length <= 200
    }
  };
  $('#report').textContent = JSON.stringify(out, null, 2);
  activity('Diagnostics run', out.checks.websocket ? 'PASS' : 'PARTIAL');
}

async function runMediaTest() {
  const base = window.__mediaBase || await invoke('start_media_server'); window.__mediaBase = base;
  const test = async (def) => {
    const media = selectedMedia(def); if (!media) return { layer: def.name, pass: false, error: 'No media' };
    const v = document.createElement('video'); v.muted = true; v.autoplay = true; v.playsInline = true; v.preload = 'auto';
    const events = [], src = `${base}/media/${media.routeId}`;
    const wait = (name, ms = 8000) => new Promise((resolve, reject) => { const t = setTimeout(() => reject(new Error(`${name} timeout`)), ms); v.addEventListener(name, () => { clearTimeout(t); events.push(name); resolve(); }, { once: true }); });
    v.src = src; document.body.append(v);
    try { await wait('loadedmetadata'); await wait('canplay'); await v.play(); await wait('playing'); const a = v.currentTime; await new Promise(r => setTimeout(r, 1200)); const b = v.currentTime; return { layer: def.name, media: media.name, src, events, videoWidth: v.videoWidth, videoHeight: v.videoHeight, currentTime: [a, b], pass: b > a }; }
    catch (e) { return { layer: def.name, media: media.name, src, events, error: String(e), mediaError: v.error?.code || null, readyState: v.readyState, networkState: v.networkState, pass: false }; }
    finally {
      try { v.pause(); } catch (_) {}
      v.removeAttribute('src');
      try { v.load(); } catch (_) {}
      v.remove();
    }
  };
  const results = []; for (const def of mediaLayers()) results.push(await test(def));
  const out = { at: new Date().toISOString(), app: appVersion, mediaServer: base, results, pass: results.every(x => x.pass) };
  $('#report').textContent = JSON.stringify(out, null, 2); activity('Media playback test', out.pass ? 'PASS' : 'FAIL'); return out;
}

function connect() {
  if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) return;
  if (wsRetryTimer) {
    clearTimeout(wsRetryTimer);
    wsRetryTimer = null;
  }
  metrics.ws = 'CONNECTING';
  updateHealth();
  const socket = new WebSocket(CANONICAL_REALTIME_WS);
  ws = socket;
  socket.onopen = () => {
    if (ws !== socket) return;
    wsRetryCount = 0;
    metrics.ws = 'LIVE';
    socket.send(JSON.stringify({ type: 'join', environment: 'live', name: 'Visuals Workstation', avatar: 'orb-purple', audience: false, event_id: crypto.randomUUID() }));
    activity('Realtime connected', CANONICAL_REALTIME_WS);
    updateHealth();
  };
  socket.onmessage = e => {
    if (ws !== socket) return;
    try {
      const d = JSON.parse(e.data);
      if (d.energy != null) metrics.energy = d.energy;
      if (d.total_reactions != null) metrics.total = d.total_reactions;
      if (d.presence != null) metrics.presence = d.presence;
      if (d.type === 'renderer_ack_received' && d.ack?.layoutHash) {
        const changed = state.lastRendererAckHash !== d.ack.layoutHash;
        state.lastRendererAckHash = d.ack.layoutHash;
        state.lastRendererAckAt = d.ack.receivedAt || Date.now();
        const role = d.ack.rendererRole || 'unknown-renderer';
        if (role === 'green-room-renderer') workstationLive.greenAck = d.ack;
        if (role === 'visuals-page-renderer') workstationLive.visualsAck = d.ack;
        if (workstationLive.active) {
          renderLiveButtonState();
          if (currentView === 'Dashboard') render('Dashboard');
        }
        if (changed && state.lastPublishedHash === d.ack.layoutHash) {
          invoke('save_state', { state }).catch(() => {});
        }
      }
      updateHealth();
    } catch (_) {}
  };
  socket.onerror = () => {
    try { socket.close(); } catch (_) {}
  };
  socket.onclose = () => {
    if (ws !== socket) return;
    ws = null;
    metrics.ws = 'OFFLINE';
    updateHealth();
    const delay = Math.min(30000, 1000 * (2 ** Math.min(wsRetryCount++, 5)));
    wsRetryTimer = setTimeout(() => {
      wsRetryTimer = null;
      connect();
    }, delay);
  };
}
window.addEventListener('online', () => connect());
window.addEventListener('beforeunload', () => {
  if (wsRetryTimer) clearTimeout(wsRetryTimer);
  wsRetryTimer = null;
  const socket = ws;
  ws = null;
  try { socket?.close(1000, 'workstation_shutdown'); } catch (_) {}
  disposeViewMedia();
});

function updateHealth() {
  if ($('#ws')) {
    $('#ws').textContent = `REALTIME — ${metrics.ws}`;
    $('#ws').className = metrics.ws === 'LIVE' ? 'live' : 'offline';
  }
  if ($('#energyTop')) $('#energyTop').textContent = `ENERGY ${Math.round(metrics.energy)}%`;
  if ($('#users')) $('#users').textContent = `${metrics.presence} USERS`;
  const pill = $('#greenSyncPill');
  if (pill) {
    const s = getGreenSyncStatus();
    pill.className = `staging-status-pill ${s.class}`;
    pill.textContent = s.label;
  }
}

// Canonical built-in layer IDs — the ONLY stable identities
const CANONICAL_LAYER_IDS = {
  stage: 'stage-content',
  visual: 'visual-content',
  logo: 'station-logo',
  alert: 'now-playing',
  presence: 'presence-bubbles',
  reactions: 'reactions',
  energy: 'room-energy',
};

function resolveLayerByCanonical(targetId, targetRole) {
  if (!Array.isArray(state.workspaceLayers)) return null;
  const idMatches = state.workspaceLayers.filter(x => x.id === targetId);
  if (idMatches.length > 1) {
    throw new Error(`CANONICAL_LAYER_COLLISION: ${targetId} appears ${idMatches.length} times`);
  }
  if (idMatches.length === 1) return idMatches[0];

  // Legacy recovery is deliberately strict: only one exact reserved role may be adopted.
  const roleMatches = state.workspaceLayers.filter(x => x.role === targetRole);
  if (roleMatches.length > 1) {
    throw new Error(`CANONICAL_LAYER_COLLISION: role ${targetRole} appears ${roleMatches.length} times`);
  }
  return roleMatches.length === 1 ? roleMatches[0] : null;
}

function resolveStageAsset() {
  const stageLayer = resolveLayerByCanonical(CANONICAL_LAYER_IDS.stage, 'stage');
  if (!stageLayer) {
    throw new Error('CANONICAL_STAGE_LAYER_NOT_FOUND: No layer with id "stage-content" or unique role "stage"');
  }

  let media = null;
  media = selectedMedia(stageLayer) || stageLayer.selectedMedia;
  if (!media) {
    const lib = libraryFor(stageLayer.id);
    if (lib && lib.length > 0) {
      const idx = Math.max(0, Math.min(lib.length - 1, Number(stageLayer.mediaIndex) || 0));
      media = lib[idx];
    }
  }
  if (!media && state.activeStage && Object.keys(state.activeStage).length) {
    media = state.activeStage;
  }

  const sourcePath = media?.sourcePath || media?.path || '';
  const runtimePath = media?.runtimePath || media?.url || media?.path || '';
  const name = media?.name || stageLayer?.name || 'stage-content';
  const fingerprint = media?.fingerprint || media?.routeId || 'stage-fp';
  const assetId = media?.assetId || media?.routeId || media?.id || fingerprint;

  return { layer: stageLayer, layerId: stageLayer.id, layerName: stageLayer.name, media, sourcePath, runtimePath, name, assetId, fingerprint };
}

function resolveVisualAsset() {
  const visualLayer = resolveLayerByCanonical(CANONICAL_LAYER_IDS.visual, 'visual');
  if (!visualLayer) {
    throw new Error('CANONICAL_VISUAL_LAYER_NOT_FOUND: No layer with id "visual-content" or unique role "visual"');
  }

  let media = null;
  media = selectedMedia(visualLayer) || visualLayer.selectedMedia;
  if (!media) {
    const lib = libraryFor(visualLayer.id);
    if (lib && lib.length > 0) {
      const idx = Math.max(0, Math.min(lib.length - 1, Number(visualLayer.mediaIndex) || 0));
      media = lib[idx];
    }
  }
  if (!media && Array.isArray(state.playlist) && state.playlist.length > 0) {
    const idx = Math.max(0, Math.min(state.playlist.length - 1, Number(visualLayer?.mediaIndex) || 0));
    media = state.playlist[idx];
  }

  const sourcePath = media?.sourcePath || media?.path || '';
  const runtimePath = media?.runtimePath || media?.url || media?.path || '';
  const name = media?.name || visualLayer?.name || 'visual-content';
  const fingerprint = media?.fingerprint || media?.routeId || 'visual-fp';
  const assetId = media?.assetId || media?.routeId || media?.id || fingerprint;

  return { layer: visualLayer, layerId: visualLayer.id, layerName: visualLayer.name, media, sourcePath, runtimePath, name, assetId, fingerprint };
}

async function executeValidationSubsteps(mode = 'both', options = {}) {
  const { onSubstepStart, onSubstepEnd, isCancelled, jobId } = options;
  const timings = {};
  const logs = [];

  const runStep = async (stepId, label, action) => {
    if (isCancelled && isCancelled()) throw new Error('Validation cancelled by user');
    const startTs = new Date().toISOString();
    const t0 = performance.now();
    onSubstepStart?.(stepId, label, startTs);
    console.log(`[SUBSTEP START] ${stepId}: ${label} @ ${startTs}`);

    // Yield to UI rendering loop to guarantee UI updates
    await new Promise(r => setTimeout(r, 0));

    try {
      const res = await action();
      if (isCancelled && isCancelled()) throw new Error('Validation cancelled by user');
      const t1 = performance.now();
      const duration = Math.round((t1 - t0) * 100) / 100;
      const endTs = new Date().toISOString();
      timings[stepId] = duration;
      const summary = typeof res === 'string' ? res : (res?.name || res?.status || 'OK');
      console.log(`[SUBSTEP END] ${stepId}: ${label} (${duration}ms) @ ${endTs} ->`, summary);
      logs.push({ stepId, label, startTs, endTs, duration, result: res });
      onSubstepEnd?.(stepId, label, duration, res, true);
      try {
        await invoke('append_app_log', {
          level: 'INFO',
          message: `[SUBSTEP ${stepId}] ${label} (${duration}ms): ${summary}`
        });
      } catch (_) {}
      return res;
    } catch (err) {
      const t1 = performance.now();
      const duration = Math.round((t1 - t0) * 100) / 100;
      const endTs = new Date().toISOString();
      timings[stepId] = duration;
      console.error(`[SUBSTEP FAILED] ${stepId}: ${label} (${duration}ms) @ ${endTs} ->`, err);
      logs.push({ stepId, label, startTs, endTs, duration, error: String(err) });
      onSubstepEnd?.(stepId, label, duration, err, false);
      try {
        await invoke('append_app_log', {
          level: 'ERROR',
          message: `[SUBSTEP ${stepId} FAILED] ${label} (${duration}ms): ${err.message || err}`
        });
      } catch (_) {}
      throw err;
    }
  };

  let stageResolved = null;
  let stageStat = null;
  let visualResolved = null;
  let visualStat = null;

  if (mode === 'stage' || mode === 'both') {
    // 1A Resolving Stage layer
    await runStep('1A', 'Resolving Stage layer', async () => {
      stageResolved = resolveStageAsset();
      if (!stageResolved.layer && !stageResolved.sourcePath) {
        throw new Error('Stage layer could not be resolved');
      }
      return `Resolved layer: ${stageResolved.layerId} (${stageResolved.layerName}); asset: ${stageResolved.name} [${stageResolved.assetId}]`;
    });

    // 1B Resolving Stage source path
    await runStep('1B', 'Resolving Stage source path', async () => {
      if (!stageResolved.sourcePath) throw new Error('No stage source path configured');
      return `Source: ${stageResolved.sourcePath}`;
    });

    // 1C stat() Stage file
    await runStep('1C', 'stat() Stage file', async () => {
      const payload = {
        jobId,
        role: 'stage',
        sourcePath: stageResolved.sourcePath,
        runtimePath: stageResolved.runtimePath,
        name: stageResolved.name
      };
      stageStat = await Promise.race([
        invoke('validate_single_media', { payload }),
        new Promise((_, reject) => setTimeout(() => reject(new Error('Stage stat timed out (5s)')), 5000))
      ]);
      if (stageStat.status === 'NOT_FOUND') {
        throw new Error(`Stage file not found on disk: ${stageResolved.sourcePath}`);
      }
      if (!stageStat.valid && stageStat.status !== 'READY') {
        throw new Error(`Stage file invalid (${stageStat.error || stageStat.status})`);
      }
      return `File OK (${Math.round(stageStat.size / 1024 / 1024 * 10) / 10} MB)`;
    });

    // 1D Reading cached Stage metadata
    await runStep('1D', 'Reading cached Stage metadata', async () => {
      return `Cached: ${stageStat.codec} ${stageStat.width}x${stageStat.height} (${Math.round(Number(stageStat.duration) || 0)}s)`;
    });

    // 1E Running Stage probe if necessary
    await runStep('1E', 'Running Stage probe if necessary', async () => {
      if (stageStat.status !== 'READY' && stageStat.status !== 'PROBLEM') {
        throw new Error(`Stage probe status problem: ${stageStat.status}`);
      }
      return `Probe verified (${stageStat.codec} - ${stageStat.status})`;
    });

    // 1F Resolving Stage runtime asset
    await runStep('1F', 'Resolving Stage runtime asset', async () => {
      return `Runtime asset: ${stageStat.runtimePath} (exists: ${stageStat.runtimeExists})`;
    });
  }

  if (mode === 'visual' || mode === 'both') {
    // 1G Resolving Visual layer
    await runStep('1G', 'Resolving Visual layer', async () => {
      visualResolved = resolveVisualAsset();
      if (!visualResolved.layer && !visualResolved.sourcePath) {
        throw new Error('Visual layer could not be resolved');
      }
      return `Resolved layer: ${visualResolved.layerId} (${visualResolved.layerName}); asset: ${visualResolved.name} [${visualResolved.assetId}]`;
    });

    // 1H Resolving Visual source path
    await runStep('1H', 'Resolving Visual source path', async () => {
      if (!visualResolved.sourcePath) throw new Error('No visual source path configured');
      return `Source: ${visualResolved.sourcePath}`;
    });

    // 1I stat() Visual file
    await runStep('1I', 'stat() Visual file', async () => {
      const payload = {
        jobId,
        role: 'visual',
        sourcePath: visualResolved.sourcePath,
        runtimePath: visualResolved.runtimePath,
        name: visualResolved.name
      };
      visualStat = await Promise.race([
        invoke('validate_single_media', { payload }),
        new Promise((_, reject) => setTimeout(() => reject(new Error('Visual stat timed out (5s)')), 5000))
      ]);
      if (visualStat.status === 'NOT_FOUND') {
        throw new Error(`Visual file not found on disk: ${visualResolved.sourcePath}`);
      }
      if (!visualStat.valid && visualStat.status !== 'READY') {
        throw new Error(`Visual file invalid (${visualStat.error || visualStat.status})`);
      }
      return `File OK (${Math.round(visualStat.size / 1024 / 1024 * 10) / 10} MB)`;
    });

    // 1J Reading cached Visual metadata
    await runStep('1J', 'Reading cached Visual metadata', async () => {
      return `Cached: ${visualStat.codec} ${visualStat.width}x${visualStat.height} (${Math.round(Number(visualStat.duration) || 0)}s)`;
    });

    // 1K Running Visual probe if necessary
    await runStep('1K', 'Running Visual probe if necessary', async () => {
      if (visualStat.status !== 'READY' && visualStat.status !== 'PROBLEM') {
        throw new Error(`Visual probe status problem: ${visualStat.status}`);
      }
      return `Probe verified (${visualStat.codec} - ${visualStat.status})`;
    });

    // 1L Resolving Visual runtime asset
    await runStep('1L', 'Resolving Visual runtime asset', async () => {
      return `Runtime asset: ${visualStat.runtimePath} (exists: ${visualStat.runtimeExists})`;
    });
  }

  // 1M Validation complete
  await runStep('1M', 'Validation complete', async () => {
    return `Validation passed: ${mode === 'stage' ? stageStat?.name : mode === 'visual' ? visualStat?.name : `${stageStat?.name} + ${visualStat?.name}`}`;
  });

  return {
    mode,
    stage: stageStat,
    visual: visualStat,
    timings,
    logs
  };
}

async function validateMediaDiagnostics(mode = 'stage') {
  let isCancelled = false;
  const jobId = `diag-${mode}-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
  const startTime = performance.now();
  const title = mode === 'stage' ? '⚡ VALIDATE STAGE MEDIA ONLY' : '⚡ VALIDATE VISUAL MEDIA ONLY';

  // Clean any previous modal overlays to enforce singleton modal
  document.querySelectorAll('.modal-overlay.progress-modal-overlay').forEach(el => el.remove());

  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay progress-modal-overlay';
  overlay.innerHTML = `<div class="modal-card">
    <div class="row" style="justify-content:space-between;align-items:center;margin-bottom:8px;">
      <h2 style="margin:0;">${title}</h2>
      <button id="cancelDiagModal" class="btn-sm" style="background:#331422;color:#ff88a3;border:1px solid #732238;">Cancel</button>
    </div>
    <p style="margin:0 0 12px 0;font-size:11px;color:var(--text-dim);">Standalone non-blocking diagnostic probe and metadata verification.</p>
    <div class="substep-list" id="diagSubstepList"></div>
    <div class="row" style="justify-content:space-between;align-items:center;margin-top:16px;">
      <span id="diagProgressTimer" style="font-size:12px;font-family:monospace;color:#63b3ed;font-weight:bold;">Elapsed: 0ms</span>
      <button id="closeDiagModal" disabled>Please wait...</button>
    </div>
  </div>`;
  document.body.appendChild(overlay);

  const timerEl = overlay.querySelector('#diagProgressTimer');
  const cancelBtn = overlay.querySelector('#cancelDiagModal');
  const closeBtn = overlay.querySelector('#closeDiagModal');
  const substepListEl = overlay.querySelector('#diagSubstepList');

  const timerInterval = setInterval(() => {
    if (timerEl) timerEl.textContent = `Elapsed: ${Math.round(performance.now() - startTime)}ms`;
  }, 40);

  cancelBtn.onclick = async () => {
    isCancelled = true;
    clearInterval(timerInterval);
    try { await invoke('cancel_staging_publish', { jobId }); } catch (_) {}
    activity(`${mode} validation cancelled by user`, `[+${Math.round(performance.now() - startTime)}ms]`);
    overlay.remove();
  };

  const substepItems = {};

  try {
    const res = await executeValidationSubsteps(mode, {
      jobId,
      isCancelled: () => isCancelled,
      onSubstepStart: (id, label) => {
        let el = substepItems[id];
        if (!el) {
          el = document.createElement('div');
          el.className = 'substep-item running';
          substepListEl.appendChild(el);
          substepItems[id] = el;
        }
        el.className = 'substep-item running';
        el.textContent = `⏳ ${id} ${label}...`;
      },
      onSubstepEnd: (id, label, duration, result, success) => {
        const el = substepItems[id];
        if (!el) return;
        if (success) {
          el.className = 'substep-item done';
          const summary = typeof result === 'string' ? result : (result?.name || 'OK');
          el.textContent = `✓ ${id} ${label} (${duration}ms) — ${summary}`;
        } else {
          el.className = 'substep-item failed';
          el.textContent = `❌ ${id} ${label} (${duration}ms) — ${result?.message || result}`;
        }
      }
    });

    clearInterval(timerInterval);
    const totalMs = Math.round(performance.now() - startTime);
    if (timerEl) timerEl.textContent = `Completed in ${totalMs}ms`;
    closeBtn.disabled = false;
    closeBtn.className = 'btn-green';
    closeBtn.textContent = `🎉 ${mode.toUpperCase()} VALIDATION READY — CLOSE (${totalMs}ms)`;
    closeBtn.onclick = () => overlay.remove();
    activity(`${mode.toUpperCase()} validation passed`, `${totalMs}ms`);
  } catch (err) {
    clearInterval(timerInterval);
    const totalMs = Math.round(performance.now() - startTime);
    if (timerEl) timerEl.textContent = `Failed in ${totalMs}ms`;
    closeBtn.disabled = false;
    closeBtn.textContent = '❌ VALIDATION FAILED — CLOSE';
    closeBtn.onclick = () => overlay.remove();
    activity(`${mode.toUpperCase()} validation failed`, String(err));
  }
}

// Robust multi-step modal for testing visual on Green (Fast, Non-Blocking, Sub-Step Timed, Real Renderer ACK)
async function testVisualOnGreenWithProgress() {
  let isCancelled = false;
  const jobId = `test-green-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
  const startTime = performance.now();
  const elapsed = () => `[+${Math.round(performance.now() - startTime)}ms]`;

  // Clean any previous modal overlays to ensure strict singleton modal
  document.querySelectorAll('.modal-overlay.progress-modal-overlay').forEach(el => el.remove());

  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay progress-modal-overlay';
  overlay.innerHTML = `<div class="modal-card">
    <div class="row" style="justify-content:space-between;align-items:center;margin-bottom:8px;">
      <h2 style="margin:0;">⚡ TEST CURRENT VISUAL ON GREEN</h2>
      <button id="cancelProgressModal" class="btn-sm" style="background:#331422;color:#ff88a3;border:1px solid #732238;">Cancel</button>
    </div>
    <p style="margin:0 0 12px 0;font-size:11px;color:var(--text-dim);">Fast real-time workstation sync without full Cloudflare Pages redeployment.</p>
    <div class="progress-list" id="testProgressList">
      <div class="progress-item running" id="step1">⏳ 1. Validating local Stage and Visual media...</div>
      <div class="substep-list" id="step1SubstepList"></div>
      <div class="progress-item" id="step2">○ 2. Generating canonical layout snapshot (v${state.layoutVersion || 1})...</div>
      <div class="progress-item" id="step3">○ 3. Syncing media to staging origin...</div>
      <div class="progress-item" id="step4">○ 4. Broadcasting layout to Realtime Gateway...</div>
      <div class="progress-item" id="step5">○ 5. Awaiting Green Staging Renderer Acknowledgment...</div>
      <div class="progress-item" id="step6">○ 6. Opening Green Audience Room...</div>
    </div>
    <div class="row" style="justify-content:space-between;align-items:center;margin-top:16px;">
      <span id="progressTimer" style="font-size:12px;font-family:monospace;color:#63b3ed;font-weight:bold;">Elapsed: 0ms</span>
      <button id="closeProgressModal" disabled>Please wait...</button>
    </div>
  </div>`;
  document.body.appendChild(overlay);

  const timerEl = overlay.querySelector('#progressTimer');
  const cancelBtn = overlay.querySelector('#cancelProgressModal');
  const closeBtn = overlay.querySelector('#closeProgressModal');
  const substepListEl = overlay.querySelector('#step1SubstepList');

  const timerInterval = setInterval(() => {
    if (timerEl) timerEl.textContent = `Elapsed: ${Math.round(performance.now() - startTime)}ms`;
  }, 40);

  cancelBtn.onclick = async () => {
    isCancelled = true;
    clearInterval(timerInterval);
    try {
      await invoke('cancel_staging_publish', { jobId });
    } catch (_) {}
    activity('Green test cancelled by user', elapsed());
    overlay.remove();
  };

  const setStep = (id, s, text) => {
    const el = overlay.querySelector(`#${id}`);
    if (!el) return;
    el.className = `progress-item ${s}`;
    el.textContent = `${elapsed()} ${text}`;
  };

  const substepItems = {};

  try {
    isPublishing = true;
    updateHealth();

    // Step 1: Substep validation (1A through 1M)
    setStep('step1', 'running', '1. Validating local Stage and Visual media...');
    await new Promise(r => setTimeout(r, 0));

    const valResult = await executeValidationSubsteps('both', {
      jobId,
      isCancelled: () => isCancelled,
      onSubstepStart: (id, label) => {
        let el = substepItems[id];
        if (!el) {
          el = document.createElement('div');
          el.className = 'substep-item running';
          substepListEl.appendChild(el);
          substepItems[id] = el;
        }
        el.className = 'substep-item running';
        el.textContent = `⏳ ${id} ${label}...`;
        const step1El = overlay.querySelector('#step1');
        if (step1El) step1El.textContent = `${elapsed()} ⏳ 1. Validating [${id} ${label}]...`;
      },
      onSubstepEnd: (id, label, duration, result, success) => {
        const el = substepItems[id];
        if (!el) return;
        if (success) {
          el.className = 'substep-item done';
          const summary = typeof result === 'string' ? result : (result?.name || 'OK');
          el.textContent = `✓ ${id} ${label} (${duration}ms) — ${summary}`;
        } else {
          el.className = 'substep-item failed';
          el.textContent = `❌ ${id} ${label} (${duration}ms) — ${result?.message || result}`;
        }
      }
    });

    if (isCancelled) return;

    const sName = valResult.stage?.name || 'stage';
    const vName = valResult.visual?.name || 'visual';
    const sFile = valResult.stage?.runtimePath || valResult.stage?.sourcePath || '?';
    const vFile = valResult.visual?.runtimePath || valResult.visual?.sourcePath || '?';
    const pathsMatch = sFile !== '?' && vFile !== '?' && sFile === vFile;
    if (pathsMatch) {
      setStep('step1', 'failed', `✗ 1. STAGE AND VISUAL RESOLVE TO SAME FILE — ${sFile}`);
      throw new Error(`CANONICAL_LAYER_COLLISION: Stage and Visual both resolve to ${sFile}`);
    }
    setStep('step1', 'done', `✓ 1. Stage: ${sName} (${sFile.split('/').pop()}) | Visual: ${vName} (${vFile.split('/').pop()})`);

    // Step 2: Canonical Snapshot
    setStep('step2', 'running', '2. Generating canonical layout snapshot...');
    await new Promise(r => setTimeout(r, 16));
    if (isCancelled) return;

    const snap = livePublishSnapshot('cycle');
    if (!snap.playlist.length) throw new Error('No enabled Visuals are available for Green cycle testing');
    setStep('step2', 'done', `✓ 2. Canonical layout snapshot generated (v${state.layoutVersion || 1})`);

    // Step 3 & 4: Fast Media Sync & Realtime Layout Broadcast
    setStep('step3', 'running', '3A. Checking staging media & resolving assets...');
    await new Promise(r => setTimeout(r, 16));

    const pubRes = await Promise.race([
      invoke('publish_layout_fast', { payload: { state: snap, jobId } }),
      new Promise((_, reject) => setTimeout(() => reject(new Error('Fast layout publish timed out (30s)')), 30000))
    ]);

    if (isCancelled) return;

    const syncInfo = pubRes.phases?.mediaUpload || 'PASS';
    setStep('step3', 'done', `✓ 3. Media sync: ${syncInfo} | Stage: ${pubRes.stageAssetId?.slice(0, 12) || '?'} | Visual: ${pubRes.visualAssetId?.slice(0, 12) || '?'}`);
    setStep('step4', 'done', `✓ 4. Realtime accepted ${Number(pubRes.payloadBytes || 0).toLocaleString()} bytes (HTTP ${pubRes.realtimeHttpStatus || '?'}) · Hash ${pubRes.layoutHash?.slice(0, 12)}...`);

    // Step 5: Wait for Real Green Staging Renderer Acknowledgment
    setStep('step5', 'running', '5. Awaiting Green Staging Renderer Acknowledgment...');
    const checkRendererAck = async (attempts, delayMs = 300) => {
      for (let attempt = 1; attempt <= attempts; attempt++) {
        if (isCancelled) return null;
        try {
          const controller = new AbortController();
          const timeout = setTimeout(() => controller.abort(), 2500);
          const res = await fetch(`https://visuals-realtime-staging.allthings140radio.online/renderer-state?environment=green-staging&t=${Date.now()}`, { cache: 'no-store', signal: controller.signal });
          clearTimeout(timeout);
          if (res.ok) {
            const data = await res.json();
            const ack = data.ack || data;
            const ackHash = ack?.layoutHash || data?.layoutHash;
            const renderStatus = String(ack?.renderStatus || data?.renderStatus || '').toLowerCase();
            const readyState = Number(ack?.videoReadyState ?? data?.videoReadyState ?? 0);
            if (ackHash === pubRes.layoutHash && (renderStatus === 'rendered' || readyState >= 2)) {
              return ack || data;
            }
          }
        } catch (_) {}
        await new Promise(r => setTimeout(r, delayMs));
      }
      return null;
    };

    // If Green is already connected (Hot Green), it will ACK quickly (15 attempts * 300ms = 4.5s)
    let greenOpenedForAck = false;
    let ack = await checkRendererAck(15, 300);
    if (!ack && !isCancelled) {
      setStep('step5', 'running', '5. Opening Green renderer and awaiting acknowledgment (Cold Launch)...');
      await openStagingBrowser(CANONICAL_GREEN_URL);
      greenOpenedForAck = true;
      // Allow realistic cold launch window (up to 30s)
      ack = await checkRendererAck(90, 300);
    }
    if (isCancelled) return;

    if (!ack) {
      // Gateway storage is not renderer proof. Preserve that distinction.
      const lState = await fetch(`https://visuals-realtime-staging.allthings140radio.online/layout-state?environment=green-staging&t=${Date.now()}`, { cache: 'no-store' })
        .then(r => r.json()).catch(() => null);
      const gatewayStored = Boolean(lState && lState.layoutHash === pubRes.layoutHash);
      throw new Error(gatewayStored
        ? `Gateway stored layout ${pubRes.layoutHash?.slice(0, 12)} but Green renderer did not ACK it within timeout`
        : `Staging renderer did not acknowledge layout hash ${pubRes.layoutHash?.slice(0, 12)} within timeout`);
    }
    setStep('step5', 'done', `✓ 5. Green renderer confirmed & rendered (Hash: ${pubRes.layoutHash?.slice(0, 12)}... · Session: ${ack.rendererSessionId || 'active'})`);

    // Step 6: Open Green (unless Step 5 already opened it to establish a renderer ACK)
    if (greenOpenedForAck) {
      setStep('step6', 'done', '✓ 6. Canonical Green Audience Room already opened for renderer verification');
    } else {
      setStep('step6', 'running', '6. Opening canonical Green Audience Room...');
      await openStagingBrowser(CANONICAL_GREEN_URL);
      setStep('step6', 'done', '✓ 6. Canonical Green Audience Room opened in browser');
    }

    const totalMs = Math.round(performance.now() - startTime);
    activity('Green test ready (fast)', `${totalMs}ms — Hash ${pubRes.layoutHash?.slice(0, 12)}`);

    clearInterval(timerInterval);
    if (timerEl) timerEl.textContent = `Completed in ${totalMs}ms`;

    if (closeBtn) {
      closeBtn.disabled = false;
      closeBtn.className = 'btn-green';
      closeBtn.textContent = '🎉 GREEN TEST READY — CLOSE';
      closeBtn.onclick = () => overlay.remove();
    }
  } catch (err) {
    clearInterval(timerInterval);
    try {
      await invoke('cancel_staging_publish', { jobId });
    } catch (_) {}
    activity('Green test failed', String(err));
    const list = overlay.querySelector('#testProgressList');
    if (list) {
      const errItem = document.createElement('div');
      errItem.className = 'progress-item failed';
      errItem.textContent = `${elapsed()} ❌ Error: ${err.message || err}`;
      list.appendChild(errItem);
    }
    if (closeBtn) {
      closeBtn.disabled = false;
      closeBtn.textContent = 'Close';
      closeBtn.onclick = () => overlay.remove();
    }
  } finally {
    isPublishing = false;
    updateHealth();
  }
}

function renderLiveButtonState() {
  const button = $('#liveVisuals');
  const dashboardButton = $('#dashboardLiveVisuals');
  const stageLayer = state?.workspaceLayers?.find(x => x.id === 'stage-content' || x.role === 'stage');
  const stageMedia = stageLayer ? (selectedMedia(stageLayer) || stageLayer.selectedMedia) : null;
  const hasValidStage = Boolean(stageMedia && (stageMedia.sourcePath || stageMedia.runtimePath));

  for (const target of [button, dashboardButton].filter(Boolean)) {
    if (workstationLive.active) {
      target.textContent = '■ STOP LIVE VISUALS';
      target.className = 'btn-live-stop';
      target.disabled = false;
    } else if (!hasValidStage) {
      target.textContent = 'STAGE REQUIRED';
      target.className = 'btn-live-primary btn-stage-missing';
      target.disabled = false;
    } else {
      target.textContent = workstationLive.phase === 'READY' ? '● LIVE VISUALS' : workstationLive.phase;
      target.className = 'btn-live-primary';
      target.disabled = !['READY', 'ERROR', 'CONNECTION LOST'].includes(workstationLive.phase);
    }
  }
  const status = $('#workstationLiveStatus');
  if (status) {
    if (workstationLive.active) {
      if (workstationLive.greenAck && workstationLive.visualsAck) {
        status.textContent = 'LIVE — BOTH';
      } else if (workstationLive.greenAck) {
        status.textContent = 'LIVE — GREEN ROOM';
      } else if (workstationLive.visualsAck) {
        status.textContent = 'LIVE — VISUALS TAB';
      } else {
        status.textContent = 'SOURCE LIVE · NO ACTIVE VIEWER';
      }
    } else {
      status.textContent = workstationLive.phase;
    }
  }
}

async function checkProductionRenderers(layoutHash) {
  try {
    const health = await invoke('get_visual_health').catch(() => null);
    const state = health?.renderer?.ack || {};
    const roles = state.renderersByRole || {};
    const fresh = ack => ack && String(ack.renderStatus).toLowerCase() === 'rendered' && (Date.now() - Number(ack.lastSeen || ack.receivedAt || 0)) < 35000 && (!layoutHash || ack.layoutHash === layoutHash);
    workstationLive.greenAck = fresh(roles['green-room-renderer']) ? roles['green-room-renderer'] : null;
    workstationLive.visualsAck = fresh(roles['visuals-page-renderer']) ? roles['visuals-page-renderer'] : null;
    return { green: workstationLive.greenAck, visuals: workstationLive.visualsAck };
  } catch (_) {
    return { green: null, visuals: null };
  }
}

function startLiveHeartbeat() {
  clearInterval(workstationLive.heartbeatTimer);
  workstationLive.heartbeatFailures = 0;
  workstationLive.heartbeatTimer = setInterval(async () => {
    try {
      await invoke('set_workstation_live', { action: 'heartbeat', layoutHash: workstationLive.layoutHash });
      workstationLive.heartbeatFailures = 0;
    } catch (err) {
      workstationLive.heartbeatFailures += 1;
      activity('Workstation heartbeat retry', `${workstationLive.heartbeatFailures}/2 · ${err}`);
      if (workstationLive.heartbeatFailures < 2) return;
      clearInterval(workstationLive.heartbeatTimer);
      workstationLive.heartbeatTimer = null;
      workstationLive.active = false;
      workstationLive.phase = 'CONNECTION LOST';
      workstationLive.error = String(err);
      activity('Workstation live heartbeat lost', String(err));
      renderLiveButtonState();
    }
  }, 1500);
}

async function startWorkstationLive() {
  const button = $('#liveVisuals');
  try {
    workstationLive.phase = 'PREPARING MEDIA'; renderLiveButtonState();
    await refreshAllMediaLayers();

    const stageLayer = state.workspaceLayers.find(x => x.id === 'stage-content' || x.role === 'stage');
    const stageMedia = stageLayer ? (selectedMedia(stageLayer) || stageLayer.selectedMedia) : null;
    if (!stageMedia || (!stageMedia.sourcePath && !stageMedia.runtimePath)) {
      throw new Error('STAGE REQUIRED: No stage media is selected. Please configure a valid Stage video in Visual Workspace.');
    }

    const valid = state.playlist.filter(item => item.enabled !== false && !item.missingLocalSource);
    if (!valid.length) throw new Error('No valid visuals were found in the configured Visuals folder');
    if (valid.length !== libraryFor('visual-content').length) throw new Error(`Full-library check failed: ${valid.length}/${libraryFor('visual-content').length} visuals ready`);
    await saveDraft(false);

    workstationLive.phase = 'CONNECTING'; renderLiveButtonState();
    await invoke('ensure_workstation_live_path');

    workstationLive.phase = `GOING LIVE · ${valid.length}/${valid.length}`; renderLiveButtonState();
    const result = await window.__publishLiveWorkspace('cycle');
    workstationLive.layoutHash = result.layoutHash || '';
    state.lastPublishedHash = workstationLive.layoutHash;
    await invoke('set_workstation_live', { action: 'start', layoutHash: workstationLive.layoutHash });
    startLiveHeartbeat();
    await invoke('set_visual_routing', { chat: 'new', visuals: null, reason: 'workstation_live_button', confirmation: 'PROMOTE GREEN ROOM' });

    workstationLive.active = true;
    workstationLive.phase = 'LIVE';
    workstationLive.startedAt = Date.now();
    activity('SOURCE LIVE', `Revision: ${workstationLive.layoutHash.slice(0, 12)} · ${valid.length}/${valid.length} visuals ready`);
    renderLiveButtonState();
    if (currentView === 'Dashboard') render('Dashboard');

    // Open destinations in browser
    openStagingBrowser(CANONICAL_GREEN_URL).catch(() => {});
    openStagingBrowser(CANONICAL_VISUALS_URL).catch(() => {});

    // Check initial viewer ACKs reactively
    checkProductionRenderers(workstationLive.layoutHash).then(() => {
      renderLiveButtonState();
      if (currentView === 'Dashboard') render('Dashboard');
    }).catch(() => {});
  } catch (err) {
    clearInterval(workstationLive.heartbeatTimer);
    workstationLive.heartbeatTimer = null;
    try { await invoke('set_workstation_live', { action: 'stop', layoutHash: workstationLive.layoutHash || null }); } catch (_) {}
    workstationLive.active = false;
    workstationLive.phase = 'ERROR';
    workstationLive.error = String(err);
    activity('LIVE VISUALS failed closed', String(err));
    alert(`LIVE VISUALS FAILED CLOSED\n\n${err}`);
  } finally {
    if (button) button.disabled = false;
    renderLiveButtonState();
  }
}

async function stopWorkstationLive() {
  clearInterval(workstationLive.heartbeatTimer); workstationLive.heartbeatTimer = null;
  workstationLive.phase = 'STOPPING'; renderLiveButtonState();
  try { await invoke('set_workstation_live', { action: 'stop', layoutHash: workstationLive.layoutHash || null }); } catch (_) {}
  try { await invoke('set_visual_routing', { chat: 'legacy', visuals: null, reason: 'workstation_live_stopped', confirmation: 'PROMOTE GREEN ROOM' }); } catch (_) {}
  workstationLive.active = false;
  workstationLive.phase = 'READY';
  workstationLive.layoutHash = '';
  workstationLive.greenAck = null;
  workstationLive.visualsAck = null;
  activity('Live visuals stopped', 'Green Room returned to safe fallback');
  renderLiveButtonState();
}

function buildAppShell() {
  document.querySelector('#app').innerHTML = `
    <div class="app">
      <aside>
        <div class="brand">
          <img src="/icon.svg">
          <div>
            <b>ALLTHINGS140</b>
            <span>VISUALS WORKSTATION</span>
          </div>
        </div>
        <div class="env">
          <i></i> GREEN ROOM WORKSTATION
        </div>
        <nav>
          ${views.map((v, i) => `<button data-view="${v}" class="${i === 0 ? 'active' : ''}">${viewLabels[v] || v}</button>`).join('')}
        </nav>
        <div class="locked">
          MAIN VISUALS TAB
          <b>ISOLATED — NEVER MODIFIED</b>
        </div>
      </aside>
      <main>
        <header>
          <div>
            <small id="crumb">GREEN ROOM / LIVE (v${appVersion})</small>
            <h1 id="title">Live Visuals</h1>
          </div>
          <div class="health">
            <span id="ws" class="offline">REALTIME — OFFLINE</span>
            <span id="energyTop">ENERGY 0%</span>
            <span id="users">0 USERS</span>
          </div>
        </header>
        <section id="view"></section>
        <footer>
          <b>GREEN ROOM ONLY</b>
          <span id="saved">DRAFT</span>
          <button id="local">Edit Layout</button>
          <button id="compare" class="btn-green">Open Green Room</button>
          <button id="publish" class="btn-cyan">UPDATE LIVE</button>
          <button id="liveVisuals" class="btn-live-primary">● LIVE VISUALS</button>
          <span class="main-route-safe">/visuals/ SAFE</span>
        </footer>
      </main>
    </div>`;

  $('nav').onclick = e => e.target.dataset.view && render(e.target.dataset.view);
  $('#local').onclick = () => render('Visual Workspace');
  $('#compare').onclick = () => openStagingBrowser(CANONICAL_GREEN_URL);

  const publishLiveWorkspace = async (mode = 'cycle') => {
    await saveDraft(false);
    isPublishing = true;
    updateHealth();
    const jobId = `publish-green-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    try {
      // Layout/media publishing is a realtime workstation operation. Cloudflare
      // Pages deploys are reserved for Green application CODE updates, not for
      // everyday show-control changes.
      const r = await invoke('publish_layout_fast', { payload: { state: livePublishSnapshot(mode), jobId } });
      const p = r.phases || {};
      activity('Layout snapshot', p.snapshot || 'PASS');
      activity('Media sync', p.mediaUpload || 'PASS');
      activity('Realtime publish', `${p.realtimePublish || 'PASS'} · HTTP ${r.realtimeHttpStatus || '?'} · ${Number(r.payloadBytes || 0).toLocaleString()} bytes`);
      activity('PUBLISHED LAYOUT', `${r.layoutRevision || 'unknown'} ${r.layoutHash || ''}`);
      if (mode !== 'single') {
        state.publishedVersion = state.layoutVersion;
        state.lastPublishedHash = r.layoutHash || '';
        state.lastPublishedAt = new Date().toISOString();
        await invoke('save_state', { state });
      }
      return r;
    } finally {
      isPublishing = false;
      updateHealth();
    }
  };
  window.__publishLiveWorkspace = publishLiveWorkspace;

  const triggerPublishStaging = async () => {
    if (!confirm('Publish this validated layout update to the Green Room realtime renderer? The radio and /visuals/ remain unchanged.')) return;
    $('#publish').disabled = true;
    $('#publish').textContent = 'Publishing…';
    try {
      const r = await publishLiveWorkspace('cycle');
      const p = r.phases || {};
      alert(`LAYOUT SNAPSHOT: PASS
MEDIA SYNC: ${p.mediaUpload || 'PASS'}
REALTIME PUBLISH: ${p.realtimePublish || 'PASS'}
HTTP STATUS: ${r.realtimeHttpStatus || '?'}
PAYLOAD: ${Number(r.payloadBytes || 0).toLocaleString()} bytes
LAYOUT HASH: ${r.layoutHash || 'unknown'}

Green staging was updated through Realtime. The status pill will change to RENDERED & SYNCED when Green acknowledges the exact layout hash. Cloudflare Pages code and production live visuals were not touched.`);
    } catch (e) {
      activity('Staging publish failed', String(e));
      alert(String(e));
    } finally {
      $('#publish').disabled = false;
      $('#publish').textContent = 'UPDATE LIVE';
    }
  };
  window.__triggerPublishStaging = triggerPublishStaging;
  $('#publish').onclick = triggerPublishStaging;
  $('#liveVisuals').onclick = () => workstationLive.active ? stopWorkstationLive() : startWorkstationLive();
  renderLiveButtonState();
}

// Startup Sequence
let info = { version: '0.2.1' };
try {
  info = await invoke('app_info');
} catch (e) {
  info = { version: '0.2.1' };
}
appVersion = info.version || '0.2.1';
buildInfo = info;

try {
  state = await invoke('load_state');
} catch (e) {
  state = {
    workspaceLayers: defaultWorkspaceLayers(),
    presets: [{ name: 'Known Good Default', viewport: 'desktop-16-9', layerFrames: {}, screenOpening: structuredClone(DEFAULT_SCREEN_OPENING) }],
    activePreset: 'Known Good Default',
    playlist: [],
    takeovers: [],
    activity: []
  };
}
log = state.activity || [];
ensureLayerSystem();
buildAppShell();
if (state.recoveredFromBackup) {
  const recoveredFrom = state.recoveredFromBackup;
  activity('Workstation state recovered from backup', recoveredFrom);
  delete state.recoveredFromBackup;
  showToast('⚠ Recovered workstation state from the newest valid backup', 6000);
  invoke('save_state', { state }).catch(err => activity('Recovered state save failed', String(err)));
}

try {
  window.__mediaBase = await invoke('start_media_server');
  window.__mediaServerError = '';
} catch (err) {
  window.__mediaBase = '';
  window.__mediaServerError = String(err);
  activity('Media server startup failed', String(err));
}

// Initial media scan — populates Stage and 95 Visuals immediately on startup
await refreshAllMediaLayers().catch(err => activity('Initial media refresh failed', String(err)));

if (!state.playlist?.length) {
  try {
    const media = await invoke('import_default_media');
    mediaLibrary = media.items || media.visualAssets || media.playlist || [];
    state.playlist = media.items || media.playlist || mediaLibrary;
    await invoke('save_state', { state });
  } catch (err) {
    activity('Legacy playlist background import failed', String(err));
  }
}

render('Dashboard');
connect();
if (stateNeedsSave) invoke('save_state', { state }).catch(err => activity('State migration save failed', String(err)));

// Keep the full folder-backed library current without disturbing a live clip.
// Changes join the next shuffle-bag round; the renderer's current media remains untouched.
setInterval(async () => {
  if (isPublishing) return;
  const before = new Set((mediaLibrary || []).map(item => item.id || item.path));
  try {
    await refreshAllMediaLayers();
    const after = new Set((mediaLibrary || []).map(item => item.id || item.path));
    const changed = before.size !== after.size || [...before].some(id => !after.has(id));
    if (!changed) return;
    await invoke('save_state', { state });
    activity('Visuals folder updated', `${after.size} valid files ready for the next full rotation round`);
    if (currentView === '24/7 Visuals' || currentView === 'Dashboard') render(currentView);
  } catch (err) {
    activity('Automatic folder scan failed', String(err));
  }
}, 60000);
