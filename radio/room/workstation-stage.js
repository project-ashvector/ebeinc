/**
 * ALLTHINGS140 Radio — Green Visuals Broadcast & Staging Engine
 * Authoritative Compositor, 24/7 Resilient Rotation, Takeover Packs,
 * Licensed Music Video Sync & Scoped Audio-Reactive Effects.
 */
(() => {
  const C = window.AT140_GREEN_CONFIG || {};
  // The public Visuals route shares the compositor core but not the Green Room
  // audience chrome. Keep these presentation surfaces route-scoped.
  document.documentElement.classList.toggle('visuals-only', Boolean(C.visualsOnly));
  const $ = selector => document.querySelector(selector);
  const $$ = selector => [...document.querySelectorAll(selector)];
  const numberOr = (value, fallback) => { const n = Number(value); return Number.isFinite(n) ? n : fallback; };
  const videos = [$('#screens video:nth-child(1)'), $('#screens video:nth-child(2)')];
  const stageOverlay = $('.stage-overlay');
  const chat = $('#chat');
  function loadStoredProfile() {
    try {
      const parsed = JSON.parse(localStorage.getItem('at140-green-profile') || 'null');
      if (parsed && typeof parsed === 'object') {
        return {
          name: String(parsed.name || 'Listener').slice(0, 24),
          avatar: String(parsed.avatar || 'orb-purple')
        };
      }
    } catch (_) {
      try { localStorage.removeItem('at140-green-profile'); } catch (_) {}
    }
    // Preserve identity from the original public chat when a listener enters
    // the Green Room for the first time.
    try {
      const legacyName = String(localStorage.getItem('allthings140-chat-name') || '').trim().slice(0, 24);
      const legacyColor = String(localStorage.getItem('allthings140-chat-color') || 'purple');
      const avatarMap = { purple: 'orb-purple', cyan: 'orb-cyan', pink: 'orb-pink', green: 'orb-green' };
      if (legacyName) return { name: legacyName, avatar: avatarMap[legacyColor] || 'orb-purple' };
    } catch (_) {}
    return { name: 'Listener', avatar: 'orb-purple' };
  }
  const profile = loadStoredProfile();

  // State
  let activeIndex = 0;
  let playlist = [];
  let playlistIndex = 0;
  let cycleBag = [];
  let cycleCursor = 0;
  let cycleRound = 0;
  let lastPlayedVisualId = '';
  let failedVisualIds = new Set();
  let consecutiveFailures = 0;
  let layout = null;
  let ws = null;
  let retryCount = 0;
  let retryTimer = null;
  let sessionId = '';
  let activeTakeover = null;
  let activeMusicVideo = null;
  let currentStationStatus = null;
  let visualTransitionInFlight = false;
  let queuedCustomVisual = null;
  let transitionTriggeredForCurrent = false;
  let visualSwapGeneration = 0;
  const CROSSFADE_MS = Math.max(500, Math.min(800, Number(C.crossfadeMs) || 700));
  let stationPollInFlight = false;

  let takeoverPollInFlight = false;
  let lastRendererAckKey = '';
  let lastAppliedLayoutHash = '';
  let roomVisualMode = C.legacyFallbackEnabled ? 'unknown' : 'new';
  let roomVisualModeReason = C.legacyFallbackEnabled ? 'startup_safe_default' : 'not_applicable';
  let autoFallbackUntil = 0;
  let realtimeOutageTimer = null;
  let rendererReadyTimer = null;
  let routingPollInFlight = false;
  let workstationLive = false;
  let workstationLivePollInFlight = false;
  let workstationLeaseStartedAt = 0;
  let workstationServerOffset = 0;
  let scheduledVisualId = '';
  let realtimeTelemetry = {
    connected: false,
    statusText: 'CONNECTING',
    sequence: 0,
    serverTime: 0,
    energy: 0,
    totalReactions: 0
  };

  function log(event, data = {}) {
    console.info('[AT140 GREEN]', new Date().toISOString(), event, data);
  }

  async function fetchWithTimeout(url, options = {}, timeoutMs = 5000) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
      return await fetch(url, { ...options, signal: controller.signal });
    } finally {
      clearTimeout(timer);
    }
  }

  let fallbackHls = null;

  function chooseLegacyFallbackUrl() {
    const mobile = window.matchMedia && window.matchMedia('(max-width: 680px)').matches;
    return mobile ? (C.legacyFallbackMobile || C.legacyFallbackDesktop) : (C.legacyFallbackDesktop || C.legacyFallbackMobile);
  }

  async function ensureFallbackReady() {
    const fallbackVideo = $('#legacyFallbackVideo');
    const fallback = $('#legacyFallback');
    if (!fallbackVideo) return false;
    if (fallback) fallback.hidden = false;
    fallbackVideo.muted = true;
    fallbackVideo.defaultMuted = true;
    fallbackVideo.playsInline = true;
    fallbackVideo.loop = true;

    const visualsHlsOnly = !!C.visualsOnly;
    const mp4Url = visualsHlsOnly ? '' : chooseLegacyFallbackUrl();
    const isMobile = window.matchMedia && window.matchMedia('(max-width: 680px)').matches;
    const hlsUrl = (visualsHlsOnly || !isMobile) && C.legacyFallbackHls;
    const playing = !fallbackVideo.paused && fallbackVideo.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA && fallbackVideo.videoWidth > 0;
    if (playing) return true;

    const playMp4 = () => {
      if (!mp4Url) return fallbackVideo.play().catch(() => {});
      if (fallbackVideo.getAttribute('src') !== mp4Url) {
        fallbackVideo.src = mp4Url;
        fallbackVideo.load();
      }
      return fallbackVideo.play().catch(() => {});
    };

    if (hlsUrl && window.Hls && Hls.isSupported()) {
      if (!fallbackHls) {
        fallbackHls = new Hls({
          enableWorker: true,
          maxBufferLength: 30,
          maxMaxBufferLength: 60
        });
        fallbackHls.loadSource(hlsUrl);
        fallbackHls.attachMedia(fallbackVideo);
        fallbackHls.on(Hls.Events.MANIFEST_PARSED, () => { fallbackVideo.play().catch(() => {}); });
        fallbackHls.on(Hls.Events.ERROR, (_event, data) => {
          if (!data.fatal || !fallbackHls) return;
          if (data.type === Hls.ErrorTypes.NETWORK_ERROR) fallbackHls.startLoad();
          else if (data.type === Hls.ErrorTypes.MEDIA_ERROR) fallbackHls.recoverMediaError();
          else if (visualsHlsOnly) fallbackHls.startLoad();
          else {
            fallbackHls.destroy();
            fallbackHls = null;
            playMp4();
          }
        });
      } else {
        try { await fallbackVideo.play(); } catch (_) {}
      }
    } else if (hlsUrl && fallbackVideo.canPlayType('application/vnd.apple.mpegurl')) {
      if (fallbackVideo.src !== hlsUrl) {
        fallbackVideo.src = hlsUrl;
        fallbackVideo.load();
      }
      try { await fallbackVideo.play(); } catch (_) {}
    } else if (hlsUrl) {
      if (fallbackVideo.src !== hlsUrl) {
        fallbackVideo.src = hlsUrl;
        fallbackVideo.load();
      }
      try { await fallbackVideo.play(); } catch (_) {}
    } else {
      await playMp4();
    }

    if (fallbackVideo.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA && fallbackVideo.videoWidth > 0) return true;
    try {
      await waitForDecodedFrame(fallbackVideo, 8000);
      return true;
    } catch (_) {
      try { await fallbackVideo.play(); } catch (__) {}
      return fallbackVideo.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA;
    }
  }

  function clearRendererSafetyTimers() {
    clearTimeout(realtimeOutageTimer);
    clearTimeout(rendererReadyTimer);
    realtimeOutageTimer = null;
    rendererReadyTimer = null;
  }

  function armRealtimeOutageFallback() {
    if (!C.legacyFallbackEnabled || roomVisualMode !== 'new' || realtimeOutageTimer) return;
    realtimeOutageTimer = setTimeout(() => {
      realtimeOutageTimer = null;
      if ((!ws || ws.readyState !== WebSocket.OPEN) && roomVisualMode === 'new') {
        engageAutomaticLegacyFallback('realtime_unavailable');
      }
    }, 15000);
  }

  function armRendererReadinessFallback() {
    clearTimeout(rendererReadyTimer);
    rendererReadyTimer = null;
    if (!C.legacyFallbackEnabled || roomVisualMode !== 'new') return;
    // Cold immutable source MP4s may legitimately consume the full 15-second
    // first-frame budget. Keep the safety timer above that bounded decoder
    // window so valid media cannot be preempted by its own fallback watchdog.
    rendererReadyTimer = setTimeout(() => {
      rendererReadyTimer = null;
      if (roomVisualMode === 'new' && !rendererMediaReady().ready) {
        engageAutomaticLegacyFallback('renderer_not_ready');
      }
    }, 25000);
  }

  function pauseCompositorMedia() {
    videos.forEach(v => {
      try { v.pause(); } catch (_) {}
    });
    const stageVideo = document.getElementById('stageVideo');
    try { stageVideo?.pause(); } catch (_) {}
  }

  function resumeCompositorMedia() {
    const stageVideo = document.getElementById('stageVideo');
    if (stageVideo?.src) stageVideo.play().catch(() => {});
    if (queuedCustomVisual) {
      const queued = queuedCustomVisual;
      queuedCustomVisual = null;
      playNextVisual(queued).catch(() => {});
      return;
    }
    const activeVideo = videos[activeIndex];
    if (activeVideo?.src) activeVideo.play().catch(() => {});
    else if (playlist.length) playNextVisual().catch(() => {});
  }

  async function setRoomVisualMode(mode, reason = 'routing') {
    if (!C.legacyFallbackEnabled) return;
    const next = mode === 'new' ? 'new' : 'legacy';
    if (next === 'new' && autoFallbackUntil > Date.now()) return;
    if (roomVisualMode === next) return;

    roomVisualMode = next;
    roomVisualModeReason = reason;
    document.documentElement.classList.toggle('workstation-live', next === 'new');
    const composition = $('#stageComposition');
    const fallback = $('#legacyFallback');
    const fallbackVideo = $('#legacyFallbackVideo');
    const label = $('#legacyFallbackLabel');
    if (label) label.hidden = new URLSearchParams(location.search).get('approval') !== '1';

    if (next === 'legacy') {
      clearRendererSafetyTimers();
      if (fallback) fallback.hidden = false;
      if (label) label.textContent = reason === 'manual_routing'
        ? 'LEGACY VISUAL SAFETY MODE'
        : 'VISUAL SAFETY FALLBACK';
      await ensureFallbackReady();
      if (composition) {
        composition.classList.remove('live-armed');
        composition.classList.remove('live-pending');
        composition.hidden = true;
      }
      pauseCompositorMedia();
      log('room_visual_mode', { mode: next, reason });
      return;
    }

    // Keep fallback visible and covering until a live visual frame exists.
    if (fallback) fallback.hidden = false;
    await ensureFallbackReady();
    if (composition) {
      composition.hidden = false;
      composition.classList.add('live-pending');
      composition.classList.remove('live-armed');
    }
    resumeCompositorMedia();
    log('room_visual_mode', { mode: next, reason });
    armRendererReadinessFallback();
    if (!ws || ws.readyState !== WebSocket.OPEN) armRealtimeOutageFallback();
    ensureRenderedAndAck();
    const deadline = Date.now() + 15000;
    while (!rendererMediaReady().ready && Date.now() < deadline && roomVisualMode === 'new') {
      await new Promise(resolve => setTimeout(resolve, 120));
    }
    if (roomVisualMode === 'new' && rendererMediaReady().ready) {
      if (composition) {
        composition.classList.remove('live-pending');
        composition.classList.add('live-armed');
      }
      await new Promise(resolve => setTimeout(resolve, CROSSFADE_MS));
      if (roomVisualMode === 'new' && rendererMediaReady().ready) {
        if (fallback) fallback.hidden = true;
        if (fallbackVideo) { try { fallbackVideo.pause(); } catch (_) {} }
      }
    } else if (roomVisualMode === 'new') {
      engageAutomaticLegacyFallback('live_first_frame_missing');
    }
  }

  async function pollVisualRouting() {
    if (!C.legacyFallbackEnabled || !C.routingUrl || routingPollInFlight) return;
    routingPollInFlight = true;
    try {
      const res = await fetchWithTimeout(`${C.routingUrl}?t=${Date.now()}`, { cache: 'no-store' }, 4000);
      if (!res.ok) return;
      const state = await res.json();
      const requested = state?.chat === 'new' ? 'new' : 'legacy';
      if (requested === 'legacy') {
        autoFallbackUntil = 0;
        await setRoomVisualMode('legacy', 'manual_routing');
      } else if (workstationLive) {
        await setRoomVisualMode('new', 'manual_routing');
      }
    } catch (err) {
      log('routing_poll_error', { error: err.message });
    } finally {
      routingPollInFlight = false;
    }
  }

  async function pollWorkstationLive() {
    if (!C.workstationLiveUrl || workstationLivePollInFlight) return;
    workstationLivePollInFlight = true;
    try {
      const res = await fetchWithTimeout(`${C.workstationLiveUrl}&t=${Date.now()}`, { cache: 'no-store' }, 4000);
      const data = res.ok ? await res.json() : null;
      const active = Boolean(data?.active);
      if (active !== workstationLive) log('workstation_live_changed', { active, ageMs: data?.ageMs, layoutHash: data?.layoutHash });
      workstationLive = active;
      workstationLeaseStartedAt = Number(data?.startedAt || 0);
      workstationServerOffset = Number(data?.serverTime || Date.now()) - Date.now();
      if (!active) await setRoomVisualMode('legacy', 'workstation_offline');
      else if (data?.layoutHash) {
        // The workstation publishes a new scene immediately before acquiring
        // its live lease. A renderer that missed that websocket update must
        // refresh scene state instead of remaining trapped in legacy fallback.
        if (!layout || data.layoutHash !== layout.layoutHash) {
          await loadPlaylist();
        }
        if (layout && data.layoutHash === layout.layoutHash) {
          await setRoomVisualMode('new', 'workstation_live');
          await synchronizeVisualToLease();
        } else {
          log('workstation_layout_pending', { leaseHash: data.layoutHash, rendererHash: layout?.layoutHash || '' });
        }
      }
    } catch (err) {
      workstationLive = false;
      await setRoomVisualMode('legacy', 'workstation_unreachable');
    } finally {
      workstationLivePollInFlight = false;
    }
  }

  function engageAutomaticLegacyFallback(reason) {
    if (!C.legacyFallbackEnabled) return false;
    autoFallbackUntil = Date.now() + 45000;
    setRoomVisualMode('legacy', reason).catch(() => {});
    return true;
  }

  function mediaUrl(url) {
    if (!url) return url;
    const base = String(C.mediaBaseUrl || '').replace(/\/$/, '');
    const optimizedBase = String(C.optimizedMediaBaseUrl || '').replace(/\/$/, '');
    let out = url;
    if (optimizedBase) {
      try {
        const parsed = new URL(out, location.href);
        if ((base && parsed.origin === new URL(base).origin) || parsed.pathname.startsWith('/media/')) {
          if (parsed.pathname.startsWith('/visuals/')) out = `${optimizedBase}/visuals/${parsed.pathname.slice('/visuals/'.length)}`;
          else if (parsed.pathname.startsWith('/stage/')) out = `${optimizedBase}/stage/${parsed.pathname.slice('/stage/'.length)}`;
          else if (parsed.pathname.startsWith('/media/playlist/')) out = `${optimizedBase}/visuals/${parsed.pathname.slice('/media/playlist/'.length)}`;
          else if (parsed.pathname.startsWith('/media/stage/')) out = `${optimizedBase}/stage/${parsed.pathname.slice('/media/stage/'.length)}`;
        }
      } catch (_) {}
    }
    if (!/^https?:\/\//i.test(out) && base) {
      if (out.startsWith('/media/playlist/')) out = base + '/visuals/' + out.slice('/media/playlist/'.length);
      else if (out.startsWith('/media/stage/')) out = base + '/stage/' + out.slice('/media/stage/'.length);
    }
    if (base && out.startsWith(base + '/') && C.mediaVersion) {
      const u = new URL(out);
      u.searchParams.set('v', C.mediaVersion);
      out = u.href;
    }
    return out;
  }

  function resolvedRect(layer, el) {
    if (!el) return { x: 0, y: 0, width: 0, height: 0 };
    const host = ($('#stageComposition') || $('#stage')).getBoundingClientRect();
    const r = el.getBoundingClientRect();
    return {
      x: host.width ? (r.left - host.left) / host.width : 0,
      y: host.height ? (r.top - host.top) / host.height : 0,
      width: host.width ? r.width / host.width : 0,
      height: host.height ? r.height / host.height : 0
    };
  }

  function applyLayerFrame(el, frame) {
    if (!el || !frame) return;
    el.style.position = 'absolute';
    el.style.inset = 'auto';
    el.style.left = (Number(frame.x) || 0) + '%';
    el.style.top = (Number(frame.y) || 0) + '%';
    el.style.width = (Number(frame.width) || 100) + '%';
    el.style.height = (Number(frame.height) || 100) + '%';
    el.style.opacity = frame.opacity != null ? frame.opacity : 1;
    el.style.objectFit = frame.fit || 'cover';
    el.style.transform = `scale(${frame.scale || 1}) scaleX(${frame.flipX ? -1 : 1}) scaleY(${frame.flipY ? -1 : 1})`;
    el.style.transformOrigin = 'center center';
    el.style.display = frame.visible === false ? 'none' : '';
    if (frame.z !== undefined) el.style.zIndex = String(frame.z);
  }

  function applyLayout(data) {
    if (!data) return;
    const incomingHash = String(data.layoutHash || '');
    if (incomingHash && incomingHash === lastAppliedLayoutHash) {
      layout = data;
      reportRendererAck();
      return;
    }
    layout = data;
    if (Array.isArray(data.playlist)) {
      playlist = data.playlist.filter(item => item && item.url && item.enabled !== false);
      playlistIndex = 0;
      cycleBag = [];
      cycleCursor = 0;
      cycleRound = 0;
      failedVisualIds = new Set();
    }
    if (incomingHash) lastAppliedLayoutHash = incomingHash;
    fitCompositionCanvas();
    if (layout.safePlaybackMode === true) resetAudioReactiveFx();
    const layers = Array.isArray(data.layers) ? data.layers : [];
    const visual = layers.find(x => x.id === 'visual-content') || layers.find(x => x.role === 'visual') || { z: 10, x: 0, y: 0, width: 100, height: 100 };
    const stage = layers.find(x => x.id === 'stage-content') || layers.find(x => x.role === 'stage') || { z: 20, x: 0, y: 0, width: 100, height: 100 };
    const logo = layers.find(x => x.id === 'station-logo') || layers.find(x => x.kind === 'logo') || { z: 30, x: 10.5, y: 77, width: 8.5, height: 9 };
    const alertLayer = layers.find(x => x.id === 'now-playing') || layers.find(x => x.kind === 'alert') || { z: 40, x: 31, y: 82, width: 38, height: 12 };
    const presence = layers.find(x => x.id === 'presence-bubbles') || layers.find(x => x.kind === 'presence') || { z: 50, x: 4, y: 86, width: 28, height: 8 };
    const reactions = layers.find(x => x.id === 'reactions') || layers.find(x => x.kind === 'reactions') || { z: 60, x: 79, y: 88, width: 17, height: 8 };
    const energyLayer = layers.find(x => x.id === 'room-energy') || layers.find(x => x.kind === 'energy') || { z: 70, x: 83, y: 7, width: 13, height: 10 };

    // Authoritative stacking order (Back to Front: Visual 10, Stage 20, Logo 30, Alert 40, Presence 50, Reactions 60, Energy 70)
    const screensEl = $('#screens');
    if (screensEl) {
      screensEl.style.zIndex = String(visual.z ?? 10);
      applyLayerFrame(screensEl, visual);
      videos.forEach(v => {
        v.style.width = '100%';
        v.style.height = '100%';
        v.style.objectFit = visual.fit || 'cover';
      });
    }

    if (stageOverlay) {
      stageOverlay.style.zIndex = String(stage.z ?? 20);
      stageOverlay.style.mixBlendMode = 'normal';
      applyLayerFrame(stageOverlay, stage);

      // Update SVG screen aperture mask
      const screenOpening = data.screenOpening || {
        x: 23.0,
        y: 33.5,
        width: 53.6,
        height: 48.5,
        rx: 1.5,
        enabled: true
      };

      const maskHole = document.getElementById('maskScreenHole');
      if (maskHole) {
        if (screenOpening.enabled === false) {
          maskHole.setAttribute('width', '0');
          maskHole.setAttribute('height', '0');
        } else {
          maskHole.setAttribute('x', String(numberOr(screenOpening.x, 23) / 100));
          maskHole.setAttribute('y', String(numberOr(screenOpening.y, 33.5) / 100));
          maskHole.setAttribute('width', String(numberOr(screenOpening.width, 53.6) / 100));
          maskHole.setAttribute('height', String(numberOr(screenOpening.height, 48.5) / 100));
          maskHole.setAttribute('rx', String(numberOr(screenOpening.rx, 1.5) / 100));
        }
      }

      // Single Stage Video Decoder
      const stageVideo = document.getElementById('stageVideo');
      const stageUrl = stage.media?.url || data.activeStageUrl;
      if (stageVideo && stageUrl) {
        const resolved = mediaUrl(stageUrl);
        if (stageVideo.getAttribute('src') !== resolved) {
          stageVideo.src = resolved;
          stageVideo.load();
          if (!C.legacyFallbackEnabled || roomVisualMode === 'new') {
            stageVideo.play().catch(() => {});
          } else {
            stageVideo.pause();
          }
        }
      }
    }

    const logoEl = $('.mode-logo');
    if (logoEl) {
      logoEl.style.zIndex = String(logo.z ?? 30);
      applyLayerFrame(logoEl, logo);
    }

    const nowEl = $('.now');
    if (nowEl) {
      nowEl.style.zIndex = String(alertLayer.z ?? 40);
      applyLayerFrame(nowEl, alertLayer);
    }

    const audienceEl = $('#audience');
    if (audienceEl) {
      audienceEl.style.zIndex = String(presence.z ?? 50);
      applyLayerFrame(audienceEl, presence);
    }

    const reactionEl = $('#reactionLayer');
    if (reactionEl) {
      reactionEl.style.zIndex = String(reactions.z ?? 60);
      applyLayerFrame(reactionEl, reactions);
    }

    const energyEl = $('.energy');
    if (energyEl) {
      energyEl.style.zIndex = String(energyLayer.z ?? 70);
      applyLayerFrame(energyEl, energyLayer);
    }

    updateDebugOverlay();
    const explicitVisual = (data.previewMode && data.previewVisual)
      ? data.previewVisual
      : (visual.media?.url ? { id: visual.media.id || visual.media.fingerprint || 'visual', url: visual.media.url, fit: visual.fit || 'cover' } : null);

    if (explicitVisual) {
      playNextVisual(explicitVisual);
    } else {
      ensureRenderedAndAck();
    }
  }

  function fitCompositionCanvas() {
    const host = $('#stage');
    const composition = $('#stageComposition');
    if (!host || !composition) return;
    composition.style.width = '100%';
    composition.style.height = '100%';
  }


  function rendererMediaReady() {
    const activeVideo = videos[activeIndex];
    const stageVideo = document.getElementById('stageVideo');
    const layers = Array.isArray(layout?.layers) ? layout.layers : [];
    const stageLayer = layers.find(x => x.id === 'stage-content') || layers.find(x => x.role === 'stage');
    const stageRequired = Boolean(stageLayer?.media?.url || layout?.activeStageUrl || stageVideo?.getAttribute('src'));
    const visualReady = Boolean(activeVideo && !activeVideo.error && activeVideo.readyState >= 2);
    const stageReady = !stageRequired || Boolean(stageVideo && !stageVideo.error && stageVideo.readyState >= 2);
    const compositionVisible = !C.legacyFallbackEnabled || (roomVisualMode === 'new' && !$('#stageComposition')?.hidden);
    return { ready: visualReady && stageReady && compositionVisible, visualReady, stageReady, stageRequired };
  }

  async function ensureRenderedAndAck() {
    const activeVideo = videos[activeIndex];
    const stageVideo = document.getElementById('stageVideo');
    try {
      if (activeVideo && activeVideo.readyState < 2) {
        await waitForDecodedFrame(activeVideo, 3000).catch(() => {});
      }
      if (stageVideo && stageVideo.getAttribute('src') && stageVideo.readyState < 2) {
        await waitForDecodedFrame(stageVideo, 3000).catch(() => {});
      }
    } catch (_) {}
    const readiness = rendererMediaReady();
    if (!readiness.ready) {
      log('renderer_ack_deferred', readiness);
      return;
    }
    clearTimeout(rendererReadyTimer);
    rendererReadyTimer = null;
    reportRendererAck();
  }

  function updateDebugOverlay() {
    if (new URLSearchParams(location.search).get('approval') !== '1') return;
    let debug = $('#layout-debug');
    if (!debug) {
      debug = document.createElement('div');
      debug.id = 'layout-debug';
      document.body.append(debug);
    }
    const layers = Array.isArray(layout?.layers) ? layout.layers : [];
    const visual = layers.find(x => x.role === 'visual' || x.id === 'visual-content');
    const stage = layers.find(x => x.role === 'stage' || x.id === 'stage-content');
    const sr = resolvedRect(stage, stageOverlay);
    const vr = resolvedRect(visual, $('#screens'));
    const activeVideo = videos[activeIndex];
    const readyStateMap = ['HAVE_NOTHING', 'HAVE_METADATA', 'HAVE_CURRENT_DATA', 'HAVE_FUTURE_DATA', 'HAVE_ENOUGH_DATA'];
    const videoState = readyStateMap[activeVideo?.readyState] || 'UNKNOWN';

    debug.hidden = false;
    debug.innerHTML = `LAYOUT ${layout?.layoutRevision || layout?.revision || 'default-v2'}
HASH ${(layout?.layoutHash || 'canonical').slice(0, 16)}…
Stage z: ${stage?.z ?? 20} source: ${stage?.media?.name || 'stage-0001.mp4'}
Visual z: ${visual?.z ?? 10} source: ${activeVideo?.dataset.id || 'playlist'} (State: ${videoState})
Stage Rect: x:${(sr.x * 100).toFixed(1)}% y:${(sr.y * 100).toFixed(1)}% w:${(sr.width * 100).toFixed(1)}% h:${(sr.height * 100).toFixed(1)}%
Visual Rect: x:${(vr.x * 100).toFixed(1)}% y:${(vr.y * 100).toFixed(1)}% w:${(vr.width * 100).toFixed(1)}% h:${(vr.height * 100).toFixed(1)}%
Cutout: x:${layout?.screenOpening?.x ?? 23}% y:${layout?.screenOpening?.y ?? 33.5}% w:${layout?.screenOpening?.width ?? 53.6}% h:${layout?.screenOpening?.height ?? 48.5}%
Realtime: ${realtimeTelemetry.statusText} (Seq: ${realtimeTelemetry.sequence}, Energy: ${Math.round(realtimeTelemetry.energy)}%)
Track: ${currentStationStatus?.current_title || 'LIVE RADIO'} (Seq: ${currentStationStatus?.station_sequence || 0})`;
  }

  // --- 24/7 Playlist & Anti-Repeat Visual Scheduler ---

  async function loadPlaylist() {
    try {
      const stateUrl = C.realtimeLayoutUrl || 'https://visuals-realtime-staging.allthings140radio.online/layout-state';
      const stateRes = await fetchWithTimeout(stateUrl, { cache: 'no-store' }, 5000).catch(() => null);
      if (stateRes && stateRes.ok) {
        const d = await stateRes.json();
        if (d.layout) {
          layout = d.layout;
          applyLayout(layout);
          if (Array.isArray(layout.playlist) && layout.playlist.length) {
            playlist = layout.playlist;
          }
        }
      }
    } catch (_) {}

    if (!layout) {
      try {
        const url = `${C.layoutUrl}${C.layoutUrl.includes('?') ? '&' : '?'}rev=${Date.now()}`;
        const res = await fetchWithTimeout(url, { cache: 'no-store' }, 5000);
        if (res.ok) {
          layout = await res.json();
          applyLayout(layout);
          if (Array.isArray(layout.playlist) && layout.playlist.length) {
            playlist = layout.playlist;
          }
        }
      } catch (e) {
        log('layout_fetch_failed', { error: e.message });
      }
    }

    if (!playlist.length) {
      try {
        const r = await fetchWithTimeout(C.playlistUrl, { cache: 'no-store' }, 5000);
        if (r.ok) {
          const p = await r.json();
          playlist = Array.isArray(p) ? p : Array.isArray(p.items) ? p.items : [];
        }
      } catch (e) {
        log('playlist_fetch_failed', { error: e.message });
      }
    }

    const fallback = layout?.fallback || {
      id: 'known-good-fallback',
      url: 'https://allthings140radio.online/assets/visuals-phone.mp4?v=1.1.0',
      fit: 'cover'
    };

    if (!playlist.length) {
      playlist = [fallback];
    } else {
      // Emergency fallback is not a normal rotation item. Keep the intended
      // playlist clean and engage fallback only after actual playback failures.
      playlist = playlist.filter(x => x?.url);
      if (!playlist.length) playlist = [fallback];
    }

    videos[0].addEventListener('timeupdate', onVideoTimeUpdate);
    videos[1].addEventListener('timeupdate', onVideoTimeUpdate);
    videos[0].addEventListener('ended', onVideoEnded);
    videos[1].addEventListener('ended', onVideoEnded);
    videos.forEach(v => {
      v.addEventListener('error', () => onVideoError(v));
      v.addEventListener('loadeddata', () => reportRendererAck());
      v.addEventListener('canplay', () => reportRendererAck());
      v.addEventListener('playing', () => reportRendererAck());
    });
    await playNextVisual();

  }

  function seededNumber(seedText) {
    let value = 2166136261;
    for (let i = 0; i < seedText.length; i++) {
      value ^= seedText.charCodeAt(i);
      value = Math.imul(value, 16777619);
    }
    return value >>> 0;
  }

  function deterministicBag(round) {
    const bag = playlist.filter(item => !failedVisualIds.has(item.id || item.assetId));
    let seed = seededNumber(`${layout?.layoutHash || 'layout'}:${round}`) || 1;
    const random = () => {
      seed ^= seed << 13; seed ^= seed >>> 17; seed ^= seed << 5;
      return (seed >>> 0) / 4294967296;
    };
    for (let i = bag.length - 1; i > 0; i--) {
      const j = Math.floor(random() * (i + 1));
      [bag[i], bag[j]] = [bag[j], bag[i]];
    }
    return bag;
  }

  function scheduledVisualAt(serverNow) {
    if (!playlist.length || !workstationLeaseStartedAt) return null;
    let elapsed = Math.max(0, serverNow - workstationLeaseStartedAt);
    let round = 1;
    // Media duration is part of the published scene. Cap pathological metadata
    // while retaining the masters' intended complete-loop duration.
    for (let guard = 0; guard < 10000; guard++) {
      const bag = deterministicBag(round);
      const qaParams = new URLSearchParams(location.search);
      const qaRequested = Number(qaParams.get('qaIntervalMs'));
      const qaInterval = location.hostname.endsWith('.pages.dev') && qaParams.has('qaIntervalMs') && Number.isFinite(qaRequested)
        ? Math.max(250, Math.min(5000, qaRequested))
        : 0;
      const durations = bag.map(item => qaInterval || Math.max(1000, Math.min(120000, numberOr(item.duration, 8) * 1000)));
      const roundDuration = durations.reduce((sum, value) => sum + value, 0) || 8000;
      if (elapsed >= roundDuration) { elapsed -= roundDuration; round += 1; continue; }
      for (let index = 0; index < bag.length; index++) {
        if (elapsed < durations[index]) return { item: bag[index], round, position: index + 1, offsetSeconds: elapsed / 1000 };
        elapsed -= durations[index];
      }
    }
    return null;
  }

  async function synchronizeVisualToLease() {
    if (!workstationLive || roomVisualMode !== 'new' || !layout) return;
    const scheduled = scheduledVisualAt(Date.now() + workstationServerOffset);
    if (!scheduled?.item) return;
    cycleRound = scheduled.round;
    cycleCursor = scheduled.position;
    const id = scheduled.item.id || scheduled.item.assetId || '';
    if (id === scheduledVisualId && videos[activeIndex]?.dataset.id === id && !transitionTriggeredForCurrent) return;
    scheduledVisualId = id;
    let itemToPlay = scheduled.item;
    if (id === videos[activeIndex]?.dataset.id) {
      itemToPlay = getNextPlaylistItem() || scheduled.item;
      scheduledVisualId = itemToPlay.id || itemToPlay.assetId || '';
    }
    await playNextVisual({ ...itemToPlay, syncOffsetSeconds: scheduled.offsetSeconds });
  }


  function currentPlaylistPosition() {
    const id = videos[activeIndex]?.dataset.id;
    return playlist.findIndex(item => (item.id || item.assetId) === id);
  }

  function getNextPlaylistItem(mode = layout?.cycle?.mode || 'ordered') {
    if (!playlist.length) return null;
    if (activeTakeover && activeTakeover.visual_url) {
      // Mixed Takeover Mode: Weight selection between takeover visuals and station playlist
      const mixRatio = typeof activeTakeover.mix_ratio === 'number' ? activeTakeover.mix_ratio : 1.0;
      if (Math.random() < mixRatio) {
        return {
          id: `takeover-${activeTakeover.id || 'live'}`,
          url: activeTakeover.visual_url,
          fit: activeTakeover.fit || 'cover',
          isTakeover: true
        };
      }
    }

    if (mode === 'shuffle-bag' || mode === 'random') {
      if (!cycleBag.length || cycleCursor >= cycleBag.length) {
        cycleBag = playlist.filter(item => !failedVisualIds.has(item.id || item.assetId));
        for (let i = cycleBag.length - 1; i > 0; i--) {
          const j = Math.floor(Math.random() * (i + 1));
          [cycleBag[i], cycleBag[j]] = [cycleBag[j], cycleBag[i]];
        }
        if (cycleBag.length > 1 && (cycleBag[0].id || cycleBag[0].assetId) === lastPlayedVisualId) {
          [cycleBag[0], cycleBag[1]] = [cycleBag[1], cycleBag[0]];
        }
        cycleCursor = 0;
        cycleRound += 1;
        log('rotation_round_started', { round: cycleRound, count: cycleBag.length });
      }
      const item = cycleBag[cycleCursor++] || null;
      if (item) lastPlayedVisualId = item.id || item.assetId || '';
      return item;
    }
    if (mode === 'random-unbounded') {
      const current=currentPlaylistPosition();
      const candidates=playlist.map((item,index)=>({item,index})).filter(x=>playlist.length<2 || x.index!==current);
      const choice=candidates[Math.floor(Math.random()*candidates.length)] || candidates[0];
      if (!choice) return null;
      playlistIndex=(choice.index+1)%playlist.length;
      return choice.item;
    }
    const current=currentPlaylistPosition();
    const index=current>=0 ? (current+1)%playlist.length : playlistIndex%playlist.length;
    playlistIndex=(index+1)%playlist.length;
    return playlist[index];
  }

  function peekNextPlaylistItem() {
    const mode = layout?.cycle?.mode || 'ordered';
    if (mode === 'shuffle-bag' || mode === 'random') {
      if (!cycleBag.length || cycleCursor >= cycleBag.length) return null;
      return cycleBag[cycleCursor] || null;
    }
    if (!playlist.length) return null;
    const current = currentPlaylistPosition();
    const index = current >= 0 ? (current + 1) % playlist.length : playlistIndex % playlist.length;
    return playlist[index] || null;
  }


  function prefetchNextVisual() {
    const item = peekNextPlaylistItem();
    const standby = videos[1 - activeIndex];
    if (!item || !standby) return;
    const url = mediaUrl(item.url);
    if (standby.getAttribute('src') !== url) {
      standby.preload = 'auto';
      standby.src = url;
      standby.dataset.id = item.id || item.assetId || 'visual';
      standby.load();
    }
  }

  function getPreviousPlaylistItem() {
    if (!playlist.length) return null;
    const current=currentPlaylistPosition();
    const index=((current>=0?current:playlistIndex)-1+playlist.length)%playlist.length;
    playlistIndex=(index+1)%playlist.length;
    return playlist[index];
  }

  // Hosted source MP4s are immutable originals and some keep their `moov`
  // metadata at EOF. A four-second budget falsely classified valid 25-45 MB
  // files as broken on a cold CDN path. Keep the wait bounded, but allow the
  // browser enough time to range-fetch metadata and decode the first frame.
  function waitForDecodedFrame(video, timeoutMs = 15000) {
    if (!video) return Promise.reject(new Error('missing video buffer'));
    return new Promise((resolve, reject) => {
      let settled = false;
      const finish = (ok, value) => {
        if (settled) return;
        settled = true;
        clearTimeout(timer);
        video.removeEventListener('loadeddata', onReady);
        video.removeEventListener('canplay', onReady);
        video.removeEventListener('error', onError);
        ok ? resolve(value) : reject(value);
      };
      const confirmFrame = () => {
        if (typeof video.requestVideoFrameCallback === 'function') {
          video.requestVideoFrameCallback(() => finish(true));
        } else if (video.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA) {
          requestAnimationFrame(() => finish(true));
        }
      };
      const onReady = () => confirmFrame();
      const onError = () => finish(false, new Error('video decode error'));
      const timer = setTimeout(() => finish(false, new Error('video first-frame timeout')), timeoutMs);
      video.addEventListener('loadeddata', onReady);
      video.addEventListener('canplay', onReady);
      video.addEventListener('error', onError, { once: true });
      if (video.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA) confirmFrame();
    });
  }

  async function activateVisualBuffer(targetIdx, item) {
    const generation = ++visualSwapGeneration;
    const targetVideo = videos[targetIdx];
    const prevIdx = 1 - targetIdx;
    const prevVideo = videos[prevIdx];
    const targetUrl = mediaUrl(item.url);
    const prevWasActive = prevVideo?.classList.contains('active');

    if (targetVideo.getAttribute('src') !== targetUrl) {
      targetVideo.src = targetUrl;
      targetVideo.dataset.id = item.id || item.assetId || 'visual';
      targetVideo.style.objectFit = item.fit || 'cover';
      targetVideo.load();
    }

    try {
      if (Number.isFinite(item.syncOffsetSeconds) && item.syncOffsetSeconds > 0) {
        if (targetVideo.readyState < HTMLMediaElement.HAVE_METADATA) {
          await new Promise(resolve => {
            const timer = setTimeout(resolve, 2500);
            targetVideo.addEventListener('loadedmetadata', () => { clearTimeout(timer); resolve(); }, { once: true });
          });
        }
        if (generation !== visualSwapGeneration) return;
        const duration = Number.isFinite(targetVideo.duration) ? targetVideo.duration : 0;
        targetVideo.currentTime = duration > 0 ? Math.min(item.syncOffsetSeconds, Math.max(0, duration - 0.1)) : item.syncOffsetSeconds;
      }
      await targetVideo.play();
      await waitForDecodedFrame(targetVideo);
      if (targetVideo.videoWidth < 2) throw new Error('empty visual frame');
    } catch (e) {
      if (generation !== visualSwapGeneration) return;
      const message = String(e?.message || e || '');
      if (e?.name === 'AbortError' || /play\(\) request was interrupted/i.test(message)) {
        log('play_cancelled', { id: item.id || item.assetId });
        return;
      }
      log('play_error', { error: e.message, id: item.id || item.assetId });
      handleVisualFailure(item, 'first_frame_failed');
      return;
    }
    if (generation !== visualSwapGeneration) return;

    // Current remains visible until B has a decoded frame; then GPU opacity crossfade.
    targetVideo.classList.add('active');
    activeIndex = targetIdx;
    consecutiveFailures = 0;
    transitionTriggeredForCurrent = false;
    updateDebugOverlay();
    reportRendererAck();
    prefetchNextVisual();
    if (prevVideo && prevVideo !== targetVideo && prevWasActive) {
      const retire = () => {
        if (generation !== visualSwapGeneration) return;
        if (prevVideo.classList.contains('active') && videos[activeIndex] !== prevVideo) {
          prevVideo.classList.remove('active');
        }
      };
      prevVideo.addEventListener('transitionend', retire, { once: true });
      setTimeout(() => {
        retire();
      }, CROSSFADE_MS + 80);
    }
  }


  async function reportRendererAck() {
    if (C.legacyFallbackEnabled && roomVisualMode !== 'new') return;
    if (!layout || !layout.layoutHash) return;
    const activeVideo = videos[activeIndex];
    const stageVideo = document.getElementById('stageVideo');
    const readiness = rendererMediaReady();
    if (!readiness.ready) return;

    const layers = Array.isArray(layout?.layers) ? layout.layers : [];
    const visual = layers.find(x => x.role === 'visual' || x.id === 'visual-content');
    const stage = layers.find(x => x.role === 'stage' || x.id === 'stage-content');

    const ackData = {
      rendererSessionId: sessionId || '',
      environment: C.environment || 'green-staging',
      rendererRole: C.rendererRole || 'unknown-renderer',
      layoutId: layout.layoutId || layout.revision || 'layout',
      layoutHash: layout.layoutHash,
      stageAssetId: stage?.media?.id || stage?.media?.fingerprint || 'stage',
      visualAssetId: layout.previewMode
        ? (layout.previewVisual?.assetId || activeVideo?.dataset.id || visual?.media?.id || visual?.media?.fingerprint || 'visual')
        : (activeVideo?.dataset.id || visual?.media?.id || visual?.media?.fingerprint || 'visual'),
      renderedAt: Date.now(),
      renderAppliedAt: Date.now(),
      videoReadyState: activeVideo.readyState,
      stageReadyState: stageVideo?.readyState || 0,
      renderStatus: 'rendered'
      ,rotationRound: cycleRound
      ,rotationPosition: cycleCursor
      ,libraryCount: playlist.length
    };

    const ackKey = `${ackData.layoutHash}:${ackData.visualAssetId}:${ackData.renderStatus}:${ackData.videoReadyState}:${ackData.stageReadyState}`;
    if (ackKey === lastRendererAckKey) return;

    const transport = (ws && ws.readyState === WebSocket.OPEN) ? 'WebSocket' : 'HTTP';
    console.log('[RENDER ACK START]', {
      layoutId: ackData.layoutId,
      layoutHash: ackData.layoutHash,
      rendererSessionId: ackData.rendererSessionId,
      transport,
      renderStatus: ackData.renderStatus,
      videoReadyState: ackData.videoReadyState
    });

    const startAck = performance.now();
    let sentOverWebSocket = false;
    if (ws && ws.readyState === WebSocket.OPEN) {
      try {
        ws.send(JSON.stringify({ type: 'renderer_ack', ...ackData }));
        sentOverWebSocket = true;
        lastRendererAckKey = ackKey;
        console.log('[RENDER ACK SENT WS]', {
          layoutHash: ackData.layoutHash,
          durationMs: Math.round(performance.now() - startAck),
          renderStatus: ackData.renderStatus
        });
      } catch (err) {
        console.error('[RENDER ACK WS ERROR]', err);
      }
    }

    if (!sentOverWebSocket) {
      try {
        const ackUrl = C.rendererAckUrl || 'https://visuals-realtime-staging.allthings140radio.online/renderer-ack';
        const res = await fetchWithTimeout(ackUrl, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(ackData)
        }, 4000);
        if (!res.ok) {
          const detail = await res.text().catch(() => '');
          throw new Error(`renderer ACK HTTP ${res.status}${detail ? `: ${detail.slice(0, 160)}` : ''}`);
        }
        lastRendererAckKey = ackKey;
        console.log('[RENDER ACK SENT HTTP]', {
          layoutHash: ackData.layoutHash,
          status: res.status,
          durationMs: Math.round(performance.now() - startAck),
          renderStatus: ackData.renderStatus
        });
      } catch (err) {
        console.error('[RENDER ACK HTTP ERROR]', err);
      }
    }
  }

  async function playNextVisual(customItem = null) {
    // In public Green Room legacy safety mode, keep the compositor cold. Preserve
    // the latest explicit visual so it can start immediately when NEW is re-enabled.
    if (C.legacyFallbackEnabled && roomVisualMode !== 'new') {
      if (customItem) queuedCustomVisual = customItem;
      return;
    }
    // Serialize buffer swaps. Layout updates, track-video events, takeover events,
    // and media ended events can arrive close together; overlapping swaps can
    // otherwise fight over the same standby <video> and briefly expose an empty
    // buffer. Keep only the latest explicit custom request while one swap runs.
    if (visualTransitionInFlight) {
      if (customItem) queuedCustomVisual = customItem;
      return;
    }
    visualTransitionInFlight = true;
    try {
      if (layout?.previewMode && layout?.previewVisual) {
        const pv = layout.previewVisual;
        const targetIdx = 1 - activeIndex;
        await activateVisualBuffer(targetIdx, {
          id: pv.assetId || pv.id || 'preview',
          url: pv.url,
          fit: pv.fit || 'cover',
          fingerprint: pv.fingerprint
        });
        return;
      }

      const item = customItem || getNextPlaylistItem();
      if (!item) return;
      const targetIdx = 1 - activeIndex;
      await activateVisualBuffer(targetIdx, item);
    } finally {
      visualTransitionInFlight = false;
      if (queuedCustomVisual) {
        const queued = queuedCustomVisual;
        queuedCustomVisual = null;
        queueMicrotask(() => playNextVisual(queued));
      }
    }
  }

  function onVideoTimeUpdate(event) {
    const v = event.currentTarget;
    if (v !== videos[activeIndex] || transitionTriggeredForCurrent) return;
    if (Number.isFinite(v.duration) && v.duration > 1 && v.currentTime >= Math.max(0.5, v.duration - 0.5)) {
      transitionTriggeredForCurrent = true;
      if (workstationLeaseStartedAt) synchronizeVisualToLease();
      else playNextVisual();
    }
  }

  function onVideoEnded(event) {
    // Ignore ended events from the inactive/retired buffer.
    if (event?.currentTarget !== videos[activeIndex]) return;
    if (!transitionTriggeredForCurrent) {
      transitionTriggeredForCurrent = true;
      if (workstationLeaseStartedAt) synchronizeVisualToLease();
      else playNextVisual();
    }
  }


  function onVideoError(video) {
    if (video.classList.contains('active')) {
      handleVisualFailure({ id: video.dataset.id }, 'media_error');
    }
  }

  function handleVisualFailure(item, reason) {
    const failedId = item?.id || item?.assetId;
    if (failedId && failedVisualIds.has(failedId)) return;
    if (failedId) {
      failedVisualIds.add(failedId);
      // Quarantine the unusable asset for this layout revision. This makes the
      // next ordered lookup advance beyond it and also collapses duplicate
      // HTMLMediaElement error + rejected play() notifications into one retry.
      playlist = playlist.filter(candidate => (candidate.id || candidate.assetId) !== failedId);
    }
    consecutiveFailures++;
    log('visual_failed', { id: item?.id, reason, consecutiveFailures });

    if (consecutiveFailures >= 3) {
      if (engageAutomaticLegacyFallback('media_failure')) {
        log('fallback_engaged', { mode: 'legacy_room_video', reason });
        return;
      }
      // Green staging keeps its isolated media fallback behavior.
      const fallback = layout?.fallback || {
        id: 'fallback-emergency',
        url: 'https://allthings140radio.online/assets/visuals-phone.mp4?v=1.1.0',
        fit: 'cover'
      };
      log('fallback_engaged', { fallback });
      setTimeout(() => playNextVisual(fallback), 500);
      return;
    }

    setTimeout(() => playNextVisual(), 800);
  }

  window.AT140_VISUAL_TRANSPORT = Object.freeze({
    next: () => playNextVisual(getNextPlaylistItem('ordered')),
    previous: () => playNextVisual(getPreviousPlaylistItem()),
    random: () => playNextVisual(getNextPlaylistItem('random')),
    state: () => ({ playlistCount: playlist.length, currentIndex: currentPlaylistPosition(), nextIndex: playlistIndex, round: cycleRound, roundPosition: cycleCursor, bagCount: cycleBag.length }),
    qaDraw: count => Array.from({ length: Math.max(0, Math.min(1000, Number(count) || 0)) }, () => {
      const item = getNextPlaylistItem('shuffle-bag');
      return item?.id || item?.assetId || null;
    }),
    // Deterministic test entrypoint: exercise complete shuffle-bag boundaries
    // without disturbing the live renderer's current round.
    qaDrawFresh: count => {
      const saved = { bag: cycleBag, cursor: cycleCursor, round: cycleRound, last: lastPlayedVisualId };
      cycleBag = []; cycleCursor = 0; cycleRound = 0; lastPlayedVisualId = '';
      const ids = Array.from({ length: Math.max(0, Math.min(1000, Number(count) || 0)) }, () => {
        const item = getNextPlaylistItem('shuffle-bag');
        return item?.id || item?.assetId || null;
      });
      cycleBag = saved.bag; cycleCursor = saved.cursor; cycleRound = saved.round; lastPlayedVisualId = saved.last;
      return ids;
    }
  });

  // --- Audio-Reactive Visual Effects (Scoped strictly to .screens) ---

  function resetAudioReactiveFx() {
    document.documentElement.style.setProperty('--visual-pulse', '1');
    document.documentElement.style.setProperty('--visual-bloom', '1');
    document.documentElement.style.setProperty('--visual-shake-x', '0px');
    document.documentElement.style.setProperty('--visual-shake-y', '0px');
  }

  function applyAudioReactiveFx(energyValue) {
    if (C.audioReactiveFx === false || layout?.safePlaybackMode === true) {
      resetAudioReactiveFx();
      return;
    }
    const energy = Math.max(0, Math.min(100, energyValue || 0));
    const pulse = 1 + (energy / 100) * 0.03; // Max 3% subtle zoom pulse
    const bloom = 1 + (energy / 100) * 0.12; // Max 12% brightness bloom
    const shakeX = energy > 80 ? (Math.random() - 0.5) * 2 : 0;
    const shakeY = energy > 80 ? (Math.random() - 0.5) * 2 : 0;

    document.documentElement.style.setProperty('--visual-pulse', pulse.toFixed(4));
    document.documentElement.style.setProperty('--visual-bloom', bloom.toFixed(4));
    document.documentElement.style.setProperty('--visual-shake-x', `${shakeX.toFixed(1)}px`);
    document.documentElement.style.setProperty('--visual-shake-y', `${shakeY.toFixed(1)}px`);
  }

  // --- Realtime WebSocket & Community HUD ---

  function connect() {
    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) return;
    clearTimeout(retryTimer);
    realtimeTelemetry.statusText = 'CONNECTING';
    $('#connection').textContent = 'CONNECTING';
    updateDebugOverlay();

    ws = new WebSocket(C.realtimeUrl);

    ws.onopen = () => {
      clearTimeout(realtimeOutageTimer);
      realtimeOutageTimer = null;
      retryCount = 0;
      realtimeTelemetry.connected = true;
      realtimeTelemetry.statusText = 'LIVE (CONNECTED)';
      $('#connection').textContent = 'LIVE';
      ws.send(JSON.stringify({
        type: 'join',
        ...profile,
        environment: C.environment,
        audience: C.environment === 'live',
        event_id: crypto.randomUUID()
      }));
      updateDebugOverlay();
    };

    ws.onclose = () => {
      ws = null;
      realtimeTelemetry.connected = false;
      realtimeTelemetry.statusText = 'OFFLINE (RETRYING)';
      $('#connection').textContent = 'OFFLINE — VISUALS CONTINUE';
      updateDebugOverlay();
      armRealtimeOutageFallback();
      const delay = Math.min(30000, 1000 * 2 ** Math.min(retryCount++, 5)) * (0.8 + Math.random() * 0.4);
      retryTimer = setTimeout(connect, delay);
    };

    ws.onerror = () => {
      if (ws) ws.close();
    };

    ws.onmessage = e => {
      try {
        const d = JSON.parse(e.data);
        handleRealtimeEvent(d);
      } catch (err) {
        log('realtime_parse_error', { error: err.message });
      }
    };
  }

  function handleRealtimeEvent(d) {
    if (!d || !d.type) return;
    if (d.sequence != null) realtimeTelemetry.sequence = d.sequence;
    if (d.server_time != null) realtimeTelemetry.serverTime = d.server_time;

    if (d.type === 'welcome') {
      if (d.environment !== C.environment) {
        log('environment_mismatch', { expected: C.environment, received: d.environment });
        try { ws?.close(1008, 'environment mismatch'); } catch (_) {}
        return;
      }
      sessionId = d.session_id;
      if (d.active_layout) applyLayout(d.active_layout);
      // Green staging uses realtime chat. The public Green Room can opt into
      // the existing moderated listener-chat service via C.chatUrl instead.
      if (!C.chatUrl) (d.history || []).forEach(addMessage);
      renderPresence(d.profiles || []);
      updateEnergy(d);
    } else if (d.type === 'layout_update' && d.layout && d.environment === C.environment) {
      applyLayout(d.layout);
    } else if (d.type === 'room_state') {
      renderPresence(d.profiles || []);
      updateEnergy(d);
    } else if (d.type === 'message') {
      if (!C.chatUrl) {
        addMessage(d.message);
        bubbleMessage(d.message);
      }
    } else if (d.type === 'reaction') {
      floatReaction(d.reaction);
      updateEnergy(d);
    } else if (d.type === 'takeover_schedule_changed') {
      pollTakeoverState();
    }
    updateDebugOverlay();
  }

  function addMessage(m) {
    if (!m || !m.text) return;
    const li = document.createElement('li');
    const b = document.createElement('b');
    b.textContent = (m.name || 'Listener') + ' ';
    li.append(b, document.createTextNode(m.text));
    chat.append(li);
    while (chat.children.length > 50) chat.firstChild.remove();
    chat.scrollTop = chat.scrollHeight;
  }

  function renderPresence(items) {
    const audienceEl = $('#audience');
    if (!audienceEl) return;
    audienceEl.replaceChildren(
      ...items.slice(0, 18).map((p, i) => {
        const a = document.createElement('div');
        a.className = 'avatar ' + (p.avatar || 'orb-purple');
        a.dataset.sid = p.session_id;
        a.style.setProperty('--phase', `${-(i % 7) * 0.17}s`);
        a.style.setProperty('--lean', `${((i % 3) - 1) * 1.2}deg`);
        const n = document.createElement('small');
        n.textContent = p.name || 'Listener';
        a.append(n);
        return a;
      })
    );
  }

  function bubbleMessage(m) {
    if (!m || !m.text) return;
    const avatar = [...document.querySelectorAll('.avatar')].find(x => x.dataset.sid === m.session_id) || document.querySelector('.avatar');
    if (!avatar) return;
    const b = document.createElement('span');
    b.className = 'bubble';
    b.textContent = m.text;
    avatar.append(b);
    setTimeout(() => b.remove(), 6500);
  }

  const emojiMap = { fire: '🔥', skull: '💀', heart: '💜', bolt: '⚡', bass: '🔊' };

  function floatReaction(r) {
    const layer = $('#reactionLayer');
    if (!layer) return;
    const x = document.createElement('span');
    x.className = 'float';
    x.textContent = emojiMap[r] || '⚡';
    x.style.left = `${5 + Math.random() * 85}%`;
    layer.append(x);
    setTimeout(() => x.remove(), 2200);
  }

  function updateEnergy(d) {
    if (d.energy != null) {
      const e = Math.max(0, Math.min(100, Number(d.energy) || 0));
      realtimeTelemetry.energy = e;
      $('#energyBar').style.width = e + '%';
      $('#energyLabel').textContent = Math.round(e) + '%';
      document.documentElement.style.setProperty('--room-energy', e);
      document.documentElement.style.setProperty('--dance-distance', `${2 + e * 0.045}px`);
      document.documentElement.style.setProperty('--dance-speed', `${1.9 - e * 0.009}s`);
      applyAudioReactiveFx(e);
    }
    if (d.total_reactions != null) {
      realtimeTelemetry.totalReactions = d.total_reactions;
      $('#reactionTotal').textContent = `Tonight's Reactions: ${Number(d.total_reactions).toLocaleString()}`;
    }
  }

  // --- Station Status, Music Video Sync & Takeover Integration ---

  async function pollStationStatus() {
    if (stationPollInFlight) return;
    stationPollInFlight = true;
    try {
      const res = await fetchWithTimeout(`${C.radioStatusUrl}?t=${Date.now()}`, { cache: 'no-store' }, 5000);
      if (!res.ok) return;
      const d = await res.json();
      currentStationStatus = d;

      const isLive = d.mode === 'live' || d.live === true;
      const take = d.active_takeover || null;
      const host = take?.artist || d.live_host || 'GUEST DJ';

      $('.now').dataset.mode = isLive ? 'live' : 'autodj';
      $('#mode').textContent = isLive ? 'NOW LIVE' : '24/7 PLAYLIST';
      $('#track').textContent = isLive ? '' : (d.current_title || 'LIVE RADIO');
      $('#artist').textContent = isLive ? host : (d.current_artist || 'ALLTHINGS140');
      if ($('#modeLogo')) {
        $('#modeLogo').src = take?.logo_url || 'https://allthings140radio.online/assets/takeover-fallback-logo.webp';
        $('#modeLogo').alt = (isLive ? host : 'ALLTHINGS140Radio') + ' logo';
      }
      if ($('#visualsTopLogo')) {
        $('#visualsTopLogo').src = take?.logo_url || 'https://allthings140radio.online/assets/takeover-fallback-logo.webp';
        $('#visualsTopLogo').alt = (isLive ? host : 'ALLTHINGS140Radio') + ' logo';
      }

      // Check for licensed track music video mapping
      checkTrackMusicVideoSync(d);
      updateDebugOverlay();
    } catch (err) {
      log('station_poll_error', { error: err.message });
    } finally {
      stationPollInFlight = false;
    }
  }

  function checkTrackMusicVideoSync(stationData) {
    if (!stationData || !layout) return;
    const trackId = stationData.current_track_id;
    const musicVideos = layout.musicVideos || C.musicVideos || {};
    const mapped = trackId ? musicVideos[String(trackId)] : null;

    if (mapped && mapped.enabled && mapped.video_url) {
      if (activeMusicVideo?.trackId !== trackId) {
        activeMusicVideo = { trackId, ...mapped };
        log('music_video_activated', { trackId, url: mapped.video_url });
        playNextVisual({
          id: `mv-${trackId}`,
          url: mapped.video_url,
          fit: mapped.fit || 'cover',
          isMusicVideo: true
        });
      } else {
        // Synchronize playback position with station timing
        const startedAt = stationData.started_at || (Date.now() / 1000);
        const serverTime = stationData.server_time || (Date.now() / 1000);
        const targetPos = Math.max(0, (serverTime - startedAt) + (mapped.sync_offset || 0));
        const activeVideo = videos[activeIndex];
        if (activeVideo && activeVideo.dataset.id === `mv-${trackId}` && Math.abs(activeVideo.currentTime - targetPos) > 1.5) {
          activeVideo.currentTime = targetPos;
        }
      }
    } else if (activeMusicVideo) {
      // Track ended or unmapped; return to normal playlist
      log('music_video_deactivated', { previousTrack: activeMusicVideo.trackId });
      activeMusicVideo = null;
      playNextVisual();
    }
  }

  async function pollTakeoverState() {
    if (takeoverPollInFlight) return;
    takeoverPollInFlight = true;
    try {
      const separator = C.realtimeStateUrl.includes('?') ? '&' : '?';
      const res = await fetchWithTimeout(`${C.realtimeStateUrl}${separator}t=${Date.now()}`, { cache: 'no-store' }, 5000);
      if (!res.ok) return;
      const d = await res.json();
      const takeover = d.takeover || null;

      if (takeover && (!activeTakeover || activeTakeover.id !== takeover.id)) {
        activeTakeover = takeover;
        log('takeover_activated', { takeover });
        playNextVisual({
          id: `takeover-${takeover.id}`,
          url: takeover.visual_url,
          fit: 'cover',
          isTakeover: true
        });
        $('#mode').textContent = 'ARTIST TAKEOVER';
      } else if (!takeover && activeTakeover) {
        log('takeover_deactivated', { previousTakeover: activeTakeover });
        activeTakeover = null;
        $('#mode').textContent = '24/7 VISUALS';
        playNextVisual();
      }
      updateDebugOverlay();
    } catch (err) {
      log('takeover_poll_error', { error: err.message });
    } finally {
      takeoverPollInFlight = false;
    }
  }

  // --- UI Bindings ---

  $('#profile').onsubmit = e => {
    e.preventDefault();
    profile.name = $('#name').value.trim().slice(0, 24) || 'Listener';
    profile.avatar = $('#avatar').value;
    localStorage.setItem('at140-green-profile', JSON.stringify(profile));
    if (ws?.readyState === 1) {
      ws.send(JSON.stringify({
        type: 'join',
        ...profile,
        environment: C.environment,
        event_id: crypto.randomUUID()
      }));
    }
  };
  $('#name').value = profile.name;
  $('#avatar').value = profile.avatar;

  $('#message').onsubmit = e => {
    e.preventDefault();
    // The public Green Room keeps the station's existing moderated chat
    // community. chat-bridge.js owns message transport when C.chatUrl is set.
    if (C.chatUrl) return;
    const input = $('#messageText');
    const text = input.value.trim();
    if (text && ws?.readyState === 1) {
      ws.send(JSON.stringify({
        type: 'message',
        text,
        event_id: crypto.randomUUID()
      }));
      input.value = '';
    }
  };

  document.querySelectorAll('[data-reaction]').forEach(b => {
    b.onclick = () => {
      if (ws?.readyState === 1) {
        ws.send(JSON.stringify({
          type: 'reaction',
          reaction: b.dataset.reaction,
          event_id: crypto.randomUUID()
        }));
      }
    };
  });

  const audio = $('#audio');
  const listen = $('#listen');
  if (!C.visualsOnly && listen && audio) {
    listen.onclick = async () => {
      if (!audio.paused) {
        audio.pause();
        listen.textContent = '▶ LISTEN LIVE';
        return;
      }
      audio.src = C.streamUrl || 'https://stream.ebeinc.online/live.mp3';
      try {
        await audio.play();
        listen.textContent = '❚❚ PAUSE LIVE';
      } catch {
        listen.textContent = '▶ TAP TO LISTEN';
      }
    };
  }

  // --- Initialization ---

  fitCompositionCanvas();
  if ('ResizeObserver' in window) {
    const stageHost = $('#stage');
    if (stageHost) new ResizeObserver(() => fitCompositionCanvas()).observe(stageHost);
  } else {
    window.addEventListener('resize', fitCompositionCanvas);
  }

  if (C.legacyFallbackEnabled) {
    setRoomVisualMode('legacy', 'startup_safe_default').catch(() => {});
    pollVisualRouting();
  }
  loadPlaylist().catch(e => log('playlist_init_failed', { error: e.message }));
  connect();
  pollStationStatus();
  pollTakeoverState();

  setInterval(pollStationStatus, 10000);
  setInterval(pollTakeoverState, 5000);
  if (C.legacyFallbackEnabled && C.routingUrl) setInterval(pollVisualRouting, 4000);
  if (C.workstationLiveUrl) {
    pollWorkstationLive();
    setInterval(pollWorkstationLive, 2000);
  }
  setInterval(() => {
    if (ws && ws.readyState === WebSocket.OPEN && layout && layout.layoutHash) {
      const activeVideo = videos[activeIndex];
      try {
        ws.send(JSON.stringify({
          type: 'renderer_heartbeat',
          environment: C.environment || 'green-staging',
          rendererRole: C.rendererRole || 'unknown-renderer',
          layoutHash: layout.layoutHash,
          videoReadyState: activeVideo?.readyState || 0,
          visualMode: roomVisualMode
        }));
      } catch (_) {}
    }
  }, 5000);

  document.addEventListener('visibilitychange', () => {
    if (!document.hidden && (!ws || ws.readyState > 1)) {
      connect();
    }
  });
  window.addEventListener('online', connect);
})();
