/**
 * ALLTHINGS140 Radio — Live Chat Audience Renderer (live-chat environment)
 *
 * Forked from visuals-green/stage.js with:
 *   environment = "live-chat" (distinct from "green-staging")
 *   Clean audience presentation (no staging diagnostics, no approval UI, no debug overlay)
 *   Automatic fallback to legacy on renderer health failure
 *   Resource management (lazy init, unload on fallback)
 *   Reduced motion respect
 *
 * This renderer renders behind the Chat drawer. It is NOT a full-page takeover.
 * When chatVisualMode === "legacy", this renderer is never loaded.
 */
(() => {
  const C = Object.assign({
    environment: "live-chat",
    wsUrl: "wss://visuals-realtime-staging.allthings140radio.online/ws",
    manifestUrl: "https://allthings140-visuals-green.pages.dev/layout.json",
    mediaOrigin: "https://visuals-media-staging.allthings140radio.online",
    heartbeatIntervalMs: 5000,
    autoFallbackTimeoutMs: 15000,
    autoFallbackCooldownMs: 45000
  }, window.AT140_CHAT_CONFIG || {});
  const ENVIRONMENT = C.environment || "live-chat";
  const $ = selector => document.querySelector(selector);

  // ── Element references ──────────────────────────────────────────────
  const container = $("#chatVisualRenderer");
  if (!container) return;

  const bgMedia = $(".bg-media");
  const bgOverlay = $(".bg-overlay");
  const backgroundVideo = $("#backgroundVideo");

  // ── Renderer state ──────────────────────────────────────────────────
  let rendererSessionId = (() => {
    const key = `at140-chat-renderer-session`;
    let sid = sessionStorage.getItem(key);
    if (!sid) { sid = crypto.randomUUID(); sessionStorage.setItem(key, sid); }
    return sid;
  })();

  let layout = null;
  let lastAppliedLayoutHash = "";
  let lastRendererAckKey = "";
  let playlist = [];
  let activeIndex = 0;
  let playlistIndex = 0;
  let recentPlayed = [];
  const RECENT_HISTORY_SIZE = 5;
  let consecutiveFailures = 0;
  let ws = null;
  let retryCount = 0;
  let retryTimer = null;
  let activeTakeover = null;
  let activeMusicVideo = null;
  let currentStationStatus = null;
  let visualTransitionInFlight = false;
  let queuedCustomVisual = null;
  let stationPollInFlight = false;
  let takeoverPollInFlight = false;
  let profile = { name: "Listener", avatar: "orb-purple" };
  let isRendererActive = false;
  let isLegacyVisible = false;
  let fallbackReason = null;
  let fallbackSetAt = 0;
  let recoveryAttemptAt = 0;
  let userForcedLegacy = false;

  // Health model
  const health = {
    vm2: { status: "unknown", lastSeen: 0 },
    realtime: { status: "unknown", lastSeen: 0, connected: false },
    renderer: { status: "unknown", lastHeartbeat: 0, lastAck: 0 },
    layout: { status: "unknown", hash: "" },
    media: { status: "unknown", source: "" },
  };

  const REDUCED = document.body.classList.contains("reduced-motion") || window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // ── Logging ─────────────────────────────────────────────────────────
  function log(event, data = {}) {
    console.info("[AT140 CHAT RENDERER]", new Date().toISOString(), event, data);
  }

  // ── Layout DOM ──────────────────────────────────────────────────────
  // The chat renderer injects a compact layered structure behind the chat drawer.
  // It mirrors the Green staging layer model but is constrained to fit the
  // home-page context (no full-page takeover takeover room sidebar).
  function initLayout() {
    container.hidden = false;
    container.innerHTML = `
      <div class="chat-screens" id="chatScreens"><video class="active" muted playsinline preload="auto"></video><video muted playsinline preload="auto"></video></div>
      <div class="chat-stage-overlay stage-layer-compositor" id="chatStage">
        <video id="chatStageVideo" class="chat-stage-single-video" muted loop autoplay playsinline preload="auto"></video>
      </div>
      <div class="chat-stage-frame debug-frame" aria-hidden="true"></div>
      <aside class="chat-mode-logo"><img id="chatModeLogo" src="https://allthings140radio.online/assets/takeover-fallback-logo.webp" alt="ALLTHINGS140Radio logo"></aside>
      <div class="chat-reactions" id="chatReactions"></div>
      <section class="chat-audience" id="chatAudience" aria-label="Audience"></section>
      <section class="chat-energy"><small>ROOM ENERGY</small><div><i id="chatEnergyBar"></i></div><b id="chatEnergyLabel">0%</b></section>
      <section class="chat-now" data-mode="autodj"><small id="chatMode">24/7 PLAYLIST</small><b id="chatTrack">STAGING UPLINK</b><span id="chatArtist">ALLTHINGS140</span></section>
    `;
  }

  // ── Legacy fallback control ─────────────────────────────────────────
  function showLegacy() {
    if (isLegacyVisible) return;
    isLegacyVisible = true;
    isRendererActive = false;

    // Stop the new renderer
    if (ws) { ws.close(); ws = null; }
    window.removeEventListener("resize", onResize);

    // Hide the chat renderer container
    if (container) {
      container.hidden = true;
      container.setAttribute("hidden", "");
      container.classList.remove("active");
    }

    // Show legacy background video
    if (backgroundVideo) {
      backgroundVideo.hidden = false;
      backgroundVideo.removeAttribute("hidden");
      backgroundVideo.style.display = "";
      if (!REDUCED) backgroundVideo.play().catch(() => {});
    }
    if (bgMedia) bgMedia.classList.remove("new-chat-visual");
    if (bgOverlay) {
      bgOverlay.hidden = false;
      bgOverlay.removeAttribute("hidden");
    }

    log("fallback_to_legacy", { reason: fallbackReason, rendererSessionId: rendererSessionId });
  }

  function hideLegacy() {
    isLegacyVisible = false;
    if (backgroundVideo) {
      backgroundVideo.pause();
      backgroundVideo.hidden = true;
      backgroundVideo.setAttribute("hidden", "");
      backgroundVideo.style.display = "none";
    }
    if (bgOverlay) {
      bgOverlay.hidden = true;
      bgOverlay.setAttribute("hidden", "");
    }
    if (bgMedia) bgMedia.classList.add("new-chat-visual");
    if (container) {
      container.hidden = false;
      container.removeAttribute("hidden");
      container.classList.add("active");
    }
  }

  function triggerFallback(reason) {
    if (userForcedLegacy) return; // Manual fallback stays until user changes mode
    const now = Date.now();
    if (now - fallbackSetAt < C.autoFallbackCooldownMs) {
      log("fallback_suppressed_cooldown", { reason });
      return;
    }
    fallbackReason = reason;
    fallbackSetAt = now;
    log("auto_fallback_triggered", { reason });
    showLegacy();
  }

  // ── Media URL resolution ────────────────────────────────────────────
  function mediaUrl(url) {
    if (!url) return url;
    const base = String(C.mediaBaseUrl || "").replace(/\/$/, "");
    let out = url;
    if (!/^https?:\/\//i.test(out) && base) {
      if (out.startsWith("/media/playlist/")) out = base + "/visuals/" + out.slice("/media/playlist/".length);
      else if (out.startsWith("/media/stage/")) out = base + "/stage/" + out.slice("/media/stage/".length);
    }
    if (base && out.startsWith(base + "/") && C.mediaVersion) {
      const u = new URL(out);
      u.searchParams.set("v", C.mediaVersion);
      out = u.href;
    }
    return out;
  }

  // ── Fetch with timeout ─────────────────────────────────────────────
  async function fetchWithTimeout(url, options = {}, timeoutMs = 5000) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try { return await fetch(url, { ...options, signal: controller.signal }); }
    finally { clearTimeout(timer); }
  }

  // ── Layout application ───────────────────────────────────────────────
  function applyLayout(data) {
    if (!data) return;
    const incomingHash = String(data.layoutHash || "");
    if (incomingHash && incomingHash === lastAppliedLayoutHash) {
      layout = data;
      reportRendererAck();
      return;
    }
    layout = data;
    health.layout.hash = incomingHash;
    if (incomingHash) {
      lastAppliedLayoutHash = incomingHash;
      health.layout.status = "received";
    }
    if (layout.safePlaybackMode === true) resetAudioReactiveFx();

    const layers = Array.isArray(data.layers) ? data.layers : [];
    const visual = layers.find(x => x.id === "visual-content") || layers.find(x => x.role === "visual") || { z: 10, x: 0, y: 0, width: 100, height: 100 };
    const stage = layers.find(x => x.id === "stage-content") || layers.find(x => x.role === "stage") || { z: 20, x: 0, y: 0, width: 100, height: 100 };
    const logo = layers.find(x => x.id === "station-logo") || layers.find(x => x.kind === "logo") || { z: 30, x: 10.5, y: 77, width: 8.5, height: 9 };
    const alertLayer = layers.find(x => x.id === "now-playing") || layers.find(x => x.kind === "alert") || { z: 40, x: 31, y: 82, width: 38, height: 12 };
    const presence = layers.find(x => x.id === "presence-bubbles") || layers.find(x => x.kind === "presence") || { z: 50, x: 4, y: 86, width: 28, height: 8 };
    const reactions = layers.find(x => x.id === "reactions") || layers.find(x => x.kind === "reactions") || { z: 60, x: 79, y: 88, width: 17, height: 8 };
    const energyLayer = layers.find(x => x.id === "room-energy") || layers.find(x => x.kind === "energy") || { z: 70, x: 83, y: 7, width: 13, height: 10 };

    const screensEl = $("#chatScreens");
    if (screensEl) {
      screensEl.style.zIndex = String(visual.z ?? 10);
    }

    const stageOverlay = $("#chatStage");
    if (stageOverlay) {
      stageOverlay.style.zIndex = String(stage.z ?? 20);
      const stageVideo = $("#chatStageVideo");
      const stageUrl = stage.media?.url || data.activeStageUrl;
      if (stageVideo && stageUrl) {
        const resolved = mediaUrl(stageUrl);
        if (stageVideo.getAttribute("src") !== resolved) {
          stageVideo.src = resolved;
          stageVideo.load();
          stageVideo.play().catch(() => {});
          health.media.source = resolved;
          health.media.status = "loading";
        }
      }
    }

    const logoEl = $(".chat-mode-logo");
    if (logoEl) { logoEl.style.zIndex = String(logo.z ?? 30); }

    const nowEl = $(".chat-now");
    if (nowEl) { nowEl.style.zIndex = String(alertLayer.z ?? 40); }

    const audienceEl = $("#chatAudience");
    if (audienceEl) { audienceEl.style.zIndex = String(presence.z ?? 50); }

    const reactionEl = $("#chatReactions");
    if (reactionEl) { reactionEl.style.zIndex = String(reactions.z ?? 60); }

    const energyEl = $(".chat-energy");
    if (energyEl) { energyEl.style.zIndex = String(energyLayer.z ?? 70); }

    const explicitVisual = (data.previewMode && data.previewVisual)
      ? data.previewVisual
      : (visual.media?.url ? { id: visual.media.id || visual.media.fingerprint || "visual", url: visual.media.url, fit: visual.fit || "cover" } : null);

    if (explicitVisual) {
      playNextVisual(explicitVisual);
    } else {
      ensureRenderedAndAck();
    }
  }

  // ── Render readiness + ACK ──────────────────────────────────────────
  const videos = [];
  function getVideos() {
    if (!videos.length) {
      const v1 = $("#chatScreens video:nth-child(1)");
      const v2 = $("#chatScreens video:nth-child(2)");
      if (v1) videos.push(v1);
      if (v2) videos.push(v2);
    }
    return videos;
  }

  async function ensureRenderedAndAck() {
    const vs = getVideos();
    const activeVideo = vs[activeIndex];
    const stageVideo = $("#chatStageVideo");
    try {
      if (activeVideo && activeVideo.readyState < 2) {
        await waitForDecodedFrame(activeVideo, 3000).catch(() => {});
      }
      if (stageVideo && stageVideo.getAttribute("src") && stageVideo.readyState < 2) {
        await waitForDecodedFrame(stageVideo, 3000).catch(() => {});
      }
    } catch (_) {}
    reportRendererAck();
  }

  async function reportRendererAck() {
    if (!layout || !layout.layoutHash) return;
    const vs = getVideos();
    const activeVideo = vs[activeIndex];
    const isRendered = Boolean(activeVideo && activeVideo.readyState >= 2);

    const layers = Array.isArray(layout?.layers) ? layout.layers : [];
    const visual = layers.find(x => x.role === "visual" || x.id === "visual-content");
    const stage = layers.find(x => x.role === "stage" || x.id === "stage-content");

    const ackData = {
      rendererSessionId: rendererSessionId,
      environment: ENVIRONMENT,
      layoutId: layout.layoutId || layout.revision || "layout",
      layoutHash: layout.layoutHash,
      stageAssetId: stage?.media?.id || stage?.media?.fingerprint || "stage",
      visualAssetId: (layout.previewMode && layout.previewVisual?.assetId) || visual?.media?.id || visual?.media?.fingerprint || activeVideo?.dataset.id || "visual",
      renderedAt: Date.now(),
      renderAppliedAt: Date.now(),
      videoReadyState: activeVideo?.readyState || 0,
      renderStatus: isRendered ? "rendered" : "pending",
    };

    if (!isRendered) return;

    const ackKey = `${ackData.layoutHash}:${ackData.visualAssetId}:${ackData.renderStatus}:${ackData.videoReadyState}`;
    if (ackKey === lastRendererAckKey) return;
    lastRendererAckKey = ackKey;

    health.renderer.status = "rendered";
    health.renderer.lastAck = Date.now();

    const transport = (ws && ws.readyState === WebSocket.OPEN) ? "WebSocket" : "HTTP";

    if (ws && ws.readyState === WebSocket.OPEN) {
      try {
        ws.send(JSON.stringify({ type: "renderer_ack", ...ackData }));
        log("renderer_ack_sent", { transport: "WebSocket", layoutHash: ackData.layoutHash });
      } catch (err) {
        log("renderer_ack_ws_error", { error: err.message });
      }
    } else {
      try {
        const res = await fetchWithTimeout(C.rendererAckUrl, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(ackData),
        }, 4000);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        health.renderer.status = "acked";
        log("renderer_ack_sent", { transport: "HTTP", layoutHash: ackData.layoutHash });
      } catch (err) {
        log("renderer_ack_http_error", { error: err.message });
      }
    }
  }

  // ── Playlist & visual scheduling ─────────────────────────────────────
  async function loadPlaylist() {
    try {
      const stateUrl = C.realtimeLayoutUrl || "https://visuals-realtime-staging.allthings140radio.online/layout-state";
      const stateRes = await fetchWithTimeout(stateUrl, { cache: "no-store" }, 5000).catch(() => null);
      if (stateRes && stateRes.ok) {
        const d = await stateRes.json();
        const incoming = d.layout || (d.layers ? d : null);
        if (incoming) {
          layout = incoming;
          if (!layout.layoutHash && d.layoutHash) layout.layoutHash = d.layoutHash;
          applyLayout(layout);
          if (Array.isArray(layout.playlist) && layout.playlist.length) {
            playlist = layout.playlist;
          }
        }
      }
    } catch (_) {}

    if (!layout) {
      try {
        const url = `${C.layoutUrl}${C.layoutUrl.includes("?") ? "&" : "?"}rev=${Date.now()}`;
        const res = await fetchWithTimeout(url, { cache: "no-store" }, 5000);
        if (res.ok) {
          layout = await res.json();
          applyLayout(layout);
          if (Array.isArray(layout.playlist) && layout.playlist.length) {
            playlist = layout.playlist;
          }
        }
      } catch (e) {
        log("layout_fetch_failed", { error: e.message });
      }
    }

    if (!playlist.length) {
      try {
        const r = await fetchWithTimeout(C.playlistUrl, { cache: "no-store" }, 5000);
        if (r.ok) {
          const p = await r.json();
          playlist = Array.isArray(p) ? p : Array.isArray(p.items) ? p.items : [];
        }
      } catch (e) {
        log("playlist_fetch_failed", { error: e.message });
      }
    }

    const fallback = layout?.fallback || {
      id: "known-good-fallback",
      url: "https://allthings140radio.online/assets/visuals-phone.mp4?v=1.1.0",
      fit: "cover",
    };

    if (!playlist.length) {
      playlist = [fallback];
    } else {
      playlist = playlist.filter(x => x?.url);
      if (!playlist.length) playlist = [fallback];
    }

    const vs = getVideos();
    if (vs.length >= 2) {
      vs.forEach(v => {
        v.addEventListener("ended", onVideoEnded);
        v.addEventListener("error", () => onVideoError(v));
        v.addEventListener("loadeddata", () => reportRendererAck());
        v.addEventListener("canplay", () => reportRendererAck());
        v.addEventListener("playing", () => reportRendererAck());
      });
    }
    await playNextVisual();
  }

  function getNextPlaylistItem() {
    if (!playlist.length) return null;
    if (activeTakeover && activeTakeover.visual_url) {
      const mixRatio = typeof activeTakeover.mix_ratio === "number" ? activeTakeover.mix_ratio : 1.0;
      if (Math.random() < mixRatio) {
        return {
          id: `takeover-${activeTakeover.id || "live"}`,
          url: activeTakeover.visual_url,
          fit: activeTakeover.fit || "cover",
          isTakeover: true,
        };
      }
    }
    const available = playlist.filter(item => !recentPlayed.includes(item.id));
    const pool = available.length ? available : playlist;
    const item = pool[Math.floor(Math.random() * pool.length)] || pool[0];
    if (item && item.id) {
      recentPlayed.push(item.id);
      if (recentPlayed.length > RECENT_HISTORY_SIZE) {
        recentPlayed.shift();
      }
    }
    return item;
  }

  function waitForDecodedFrame(video, timeoutMs = 4000) {
    if (!video) return Promise.reject(new Error("missing video buffer"));
    return new Promise((resolve, reject) => {
      let settled = false;
      const finish = (ok, value) => {
        if (settled) return;
        settled = true;
        clearTimeout(timer);
        video.removeEventListener("loadeddata", onReady);
        video.removeEventListener("canplay", onReady);
        video.removeEventListener("error", onError);
        ok ? resolve(value) : reject(value);
      };
      const confirmFrame = () => {
        if (typeof video.requestVideoFrameCallback === "function") {
          video.requestVideoFrameCallback(() => finish(true));
        } else if (video.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA) {
          requestAnimationFrame(() => finish(true));
        }
      };
      const onReady = () => confirmFrame();
      const onError = () => finish(false, new Error("video decode error"));
      const timer = setTimeout(() => finish(false, new Error("video first-frame timeout")), timeoutMs);
      video.addEventListener("loadeddata", onReady);
      video.addEventListener("canplay", onReady);
     video.addEventListener("error", onError, { once: true });
      if (video.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA) confirmFrame();
    });
  }

  async function activateVisualBuffer(targetIdx, item) {
    const vs = getVideos();
    const targetVideo = vs[targetIdx];
    const prevIdx = 1 - targetIdx;
    const prevVideo = vs[prevIdx];
    const targetUrl = mediaUrl(item.url);

    if (!targetVideo) {
      handleVisualFailure(item, "no_buffer");
      return;
    }

    if (targetVideo.src !== targetUrl) {
      targetVideo.src = targetUrl;
      targetVideo.dataset.id = item.id || item.assetId || "visual";
      targetVideo.style.objectFit = item.fit || "cover";
      targetVideo.load();
    } else {
      targetVideo.currentTime = 0;
    }

    try {
      await targetVideo.play();
      await waitForDecodedFrame(targetVideo);
    } catch (e) {
      log("play_error", { error: e.message, id: item.id || item.assetId });
      handleVisualFailure(item, "first_frame_failed");
      return;
    }

    targetVideo.classList.add("active");
    if (prevVideo && prevVideo !== targetVideo) {
      setTimeout(() => {
        prevVideo.classList.remove("active");
        prevVideo.pause();
      }, 120);
    }
    activeIndex = targetIdx;
    consecutiveFailures = 0;
    health.media.status = "playing";
    reportRendererAck();
  }

  async function playNextVisual(customItem = null) {
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
          id: pv.assetId || pv.id || "preview",
          url: pv.url,
          fit: pv.fit || "cover",
          fingerprint: pv.fingerprint,
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

  function onVideoEnded(event) {
    if (event?.currentTarget !== getVideos()[activeIndex]) return;
    playNextVisual();
  }

  function onVideoError(video) {
    if (video.classList.contains("active")) {
      handleVisualFailure({ id: video.dataset.id }, "media_error");
    }
  }

  function handleVisualFailure(item, reason) {
    consecutiveFailures++;
    log("visual_failed", { id: item?.id, reason, consecutiveFailures });

    if (consecutiveFailures >= C.maxConsecutiveFailures) {
      const fallback = layout?.fallback || {
        id: "fallback-emergency",
        url: "https://allthings140radio.online/assets/visuals-phone.mp4?v=1.1.0",
        fit: "cover",
      };
      log("fallback_engaged", { fallback });
      setTimeout(() => playNextVisual(fallback), 500);
      return;
    }

    setTimeout(() => playNextVisual(), 800);
  }

  // ── Audio-reactive FX (scoped, disabled for reduced motion) ─────────
  function resetAudioReactiveFx() {
    if (container) {
      container.style.setProperty("--visual-pulse", "1");
      container.style.setProperty("--visual-bloom", "1");
      container.style.setProperty("--visual-shake-x", "0px");
      container.style.setProperty("--visual-shake-y", "0px");
    }
  }

  function applyAudioReactiveFx(energyValue) {
    if (REDUCED || C.audioReactiveFx === false || layout?.safePlaybackMode === true) {
      resetAudioReactiveFx();
      return;
    }
    const energy = Math.max(0, Math.min(100, energyValue || 0));
    const pulse = 1 + (energy / 100) * 0.03;
    const bloom = 1 + (energy / 100) * 0.12;
    const shakeX = energy > 80 ? (Math.random() - 0.5) * 2 : 0;
    const shakeY = energy > 80 ? (Math.random() - 0.5) * 2 : 0;
    container.style.setProperty("--visual-pulse", pulse.toFixed(4));
    container.style.setProperty("--visual-bloom", bloom.toFixed(4));
    container.style.setProperty("--visual-shake-x", `${shakeX.toFixed(1)}px`);
    container.style.setProperty("--visual-shake-y", `${shakeY.toFixed(1)}px`);
  }

  // ── Realtime WebSocket ──────────────────────────────────────────────
  function connect() {
    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) return;
    clearTimeout(retryTimer);
    ws = new WebSocket(C.realtimeUrl);

    ws.onopen = () => {
      retryCount = 0;
      health.realtime.connected = true;
      health.realtime.status = "online";
      health.realtime.lastSeen = Date.now();
      log("realtime_connected");
      ws.send(JSON.stringify({
        type: "join",
        ...profile,
        environment: ENVIRONMENT,
        rendererSessionId: rendererSessionId,
        event_id: crypto.randomUUID(),
      }));
    };

    ws.onclose = () => {
      ws = null;
      health.realtime.connected = false;
      health.realtime.status = "offline";
      log("realtime_disconnected");
      const delay = Math.min(30000, 1000 * 2 ** Math.min(retryCount++, 5)) * (0.8 + Math.random() * 0.4);
      retryTimer = setTimeout(connect, delay);
    };

    ws.onerror = () => {
      if (ws) ws.close();
    };

    ws.onmessage = e => {
      let d;
      try { d = JSON.parse(e.data); } catch { return; }
      handleRealtimeEvent(d);
    };
  }

  function handleRealtimeEvent(d) {
    if (!d || !d.type) return;
    health.realtime.lastSeen = Date.now();

    if (d.type === "welcome") {
      if (d.active_layout) applyLayout(d.active_layout);
    } else if (d.type === "layout_update" && d.layout) {
      applyLayout(d.layout);
      if (Array.isArray(d.layout.playlist) && d.layout.playlist.length) {
        playlist = d.layout.playlist;
      }
    } else if (d.type === "room_state") {
      renderPresence(d.profiles || []);
      updateEnergy(d);
    } else if (d.type === "message") {
      addChatMessage(d.message);
    } else if (d.type === "reaction") {
      floatReaction(d.reaction);
      updateEnergy(d);
    } else if (d.type === "renderer_heartbeat_ack") {
      health.renderer.status = "heartbeat_ok";
      health.renderer.lastHeartbeat = Date.now();
    }
  }

  function renderPresence(items) {
    const audienceEl = $("#chatAudience");
    if (!audienceEl) return;
    audienceEl.replaceChildren(
      ...items.slice(0, 18).map((p, i) => {
        const a = document.createElement("div");
        a.className = "chat-avatar " + (p.avatar || "orb-purple");
        a.dataset.sid = p.session_id;
        a.style.setProperty("--phase", `${-(i % 7) * 0.17}s`);
        const n = document.createElement("small");
        n.textContent = p.name || "Listener";
        a.append(n);
        return a;
      }),
    );
  }

  function floatReaction(r) {
    const layer = $("#chatReactions");
    if (!layer) return;
    const x = document.createElement("span");
    x.className = "chat-float";
    x.textContent = { fire: "🔥", skull: "💀", heart: "💜", bolt: "⚡", bass: "🔊" }[r] || "⚡";
    x.style.left = `${5 + Math.random() * 85}%`;
    layer.append(x);
    setTimeout(() => x.remove(), 2200);
  }

  const emojiMap = { fire: "🔥", skull: "💀", heart: "💜", bolt: "⚡", bass: "🔊" };

  function updateEnergy(d) {
    if (d.energy != null) {
      const e = Math.max(0, Math.min(100, Number(d.energy) || 0));
      const bar = $("#chatEnergyBar");
      const label = $("#chatEnergyLabel");
      if (bar) bar.style.width = e + "%";
      if (label) label.textContent = Math.round(e) + "%";
      applyAudioReactiveFx(e);
    }
  }

  function addChatMessage(msg) {
    // Chat messages rendered by the main chat.js; this renderer does not
    // duplicate the chat messaging logic. It only shows presence/reactions/energy.
  }

  // ── Station status polling ──────────────────────────────────────────
  async function pollStationStatus() {
    if (stationPollInFlight) return;
    stationPollInFlight = true;
    try {
      const res = await fetchWithTimeout(`${C.radioStatusUrl}?t=${Date.now()}`, { cache: "no-store" }, 5000);
      if (!res.ok) return;
      const d = await res.json();
      currentStationStatus = d;
      health.vm2.status = d.online ? "online" : "offline";
      health.vm2.lastSeen = Date.now();

      const isLive = d.mode === "live" || d.live === true;
      const take = d.active_takeover || null;
      const host = take?.artist || d.live_host || "GUEST DJ";

      const nowEl = $(".chat-now");
      if (nowEl) nowEl.dataset.mode = isLive ? "live" : "autodj";
      const modeEl = $("#chatMode");
      if (modeEl) modeEl.textContent = isLive ? "NOW LIVE" : "24/7 PLAYLIST";
      const trackEl = $("#chatTrack");
      if (trackEl) trackEl.textContent = isLive ? "" : (d.current_title || "LIVE RADIO");
      const artistEl = $("#chatArtist");
      if (artistEl) artistEl.textContent = isLive ? host : (d.current_artist || "ALLTHINGS140");
      const logo = $("#chatModeLogo");
      if (logo) {
        logo.src = take?.logo_url || "https://allthings140radio.online/assets/takeover-fallback-logo.webp";
        logo.alt = (isLive ? host : "ALLTHINGS140Radio") + " logo";
      }
    } catch (err) {
      log("station_poll_error", { error: err.message });
      health.vm2.status = "error";
    } finally {
      stationPollInFlight = false;
    }
  }

  async function pollTakeoverState() {
    if (takeoverPollInFlight) return;
    takeoverPollInFlight = true;
    try {
      const res = await fetchWithTimeout(`${C.realtimeStateUrl}?t=${Date.now()}`, { cache: "no-store" }, 5000);
      if (!res.ok) return;
      const d = await res.json();
      const takeover = d.takeover || null;
      if (takeover && (!activeTakeover || activeTakeover.id !== takeover.id)) {
        activeTakeover = takeover;
        log("takeover_activated", { takeover });
        playNextVisual({
          id: `takeover-${takeover.id}`,
          url: takeover.visual_url,
          fit: "cover",
          isTakeover: true,
        });
        const modeEl = $("#chatMode");
        if (modeEl) modeEl.textContent = "ARTIST TAKEOVER";
      } else if (!takeover && activeTakeover) {
        log("takeover_deactivated", { previousTakeover: activeTakeover });
        activeTakeover = null;
        const modeEl = $("#chatMode");
        if (modeEl) modeEl.textContent = "24/7 VISUALS";
        playNextVisual();
      }
    } catch (err) {
      log("takeover_poll_error", { error: err.message });
    } finally {
      takeoverPollInFlight = false;
    }
  }

  // ── Renderer heartbeat ──────────────────────────────────────────────
  function startHeartbeat() {
    setInterval(() => {
      if (ws && ws.readyState === WebSocket.OPEN && layout && layout.layoutHash) {
        const vs = getVideos();
        const activeVideo = vs[activeIndex];
        try {
          ws.send(JSON.stringify({
            type: "renderer_heartbeat",
            environment: ENVIRONMENT,
            rendererSessionId: rendererSessionId,
            layoutHash: layout.layoutHash,
            videoReadyState: activeVideo?.readyState || 0,
            renderStatus: health.renderer.status,
          }));
          health.renderer.lastHeartbeat = Date.now();
        } catch (_) {}
      }
    }, C.rendererHeartbeatIntervalMs || 5000);
  }

  // ── Health monitoring & automatic fallback ──────────────────────────
  const initStartTime = Date.now();
  function checkRendererHealth() {
    const now = Date.now();
    if (now - initStartTime < 15000) {
      return { healthy: true, reason: "startup_grace" };
    }
    const heartbeatAge = now - (health.renderer.lastHeartbeat || 0);
    const ackAge = now - (health.renderer.lastAck || 0);
    const realtimeAge = now - (health.realtime.lastSeen || 0);

    // Renderer considered healthy only if:
    // - Has a valid layout with hash
    // - Has received a recent ACK (within stale threshold)
    // - WebSocket is connected (or HTTP ack is recent)
    // - Not in error state
    const hasValidLayout = layout && layout.layoutHash && layout.layoutHash !== "";
    const hasRecentAck = ackAge < (C.rendererStaleThresholdMs || 15000);
    const hasRecentHeartbeat = health.renderer.lastHeartbeat > 0 && heartbeatAge < (C.rendererStaleThresholdMs || 15000);
    const realtimeOk = health.realtime.connected || realtimeAge < (C.rendererStaleThresholdMs || 15000);

    if (!hasValidLayout) {
      return { healthy: false, reason: "no_valid_layout" };
    }
    if (!hasRecentAck && !hasRecentHeartbeat) {
      return { healthy: false, reason: "renderer_ack_stale" };
    }
    if (!realtimeOk) {
      return { healthy: false, reason: "realtime_unavailable" };
    }
    if (consecutiveFailures >= C.maxConsecutiveFailures) {
      return { healthy: false, reason: "excessive_media_failures" };
    }
    return { healthy: true, reason: "ok" };
  }

  function startHealthMonitoring() {
    setInterval(() => {
      if (!isRendererActive || userForcedLegacy) return;
      const result = checkRendererHealth();
      if (!result.healthy) {
        log("renderer_health_failed", { reason: result.reason, health });
        triggerFallback(result.reason);
      }
    }, 5000);
  }

  // ── Resize handling ─────────────────────────────────────────────────
  function onResize() {
    // Adjust chat-audience and HUD elements for responsive layout
    const screensEl = $("#chatScreens");
    if (screensEl) {
      const w = window.innerWidth;
      const h = window.innerHeight;
      const aspect = 16 / 9;
    }
  }

  function removeEventListeners() {
    window.removeEventListener("resize", onResize);
  }

  // ── Initialization ──────────────────────────────────────────────────
  async function init() {
    if (!container) return;

    // Check reduced motion
    if (REDUCED) {
      container.classList.add("reduced-motion");
    }
    window.matchMedia("(prefers-reduced-motion: reduce)").addEventListener("change", e => {
      if (container) container.classList.toggle("reduced-motion", e.matches);
    });

    // Initialize the layout DOM
    initLayout();

    // Check if user has manually forced legacy (persisted in localStorage)
    const forcedLegacy = localStorage.getItem("at140-chat-legacy-fallback") === "true";
    if (forcedLegacy) {
      userForcedLegacy = true;
      log("manual_legacy_active", { rendererSessionId });
      showLegacy();
      return;
    }

    // Hide legacy, show renderer
    hideLegacy();
    isRendererActive = true;
    isLegacyVisible = false;

    window.addEventListener("resize", onResize);

    // Load playlist/layout, connect realtime, start monitoring
    await loadPlaylist();
    connect();
    pollStationStatus();
    pollTakeoverState();
    startHeartbeat();
    startHealthMonitoring();

    setInterval(pollStationStatus, 10000);
    setInterval(pollTakeoverState, 5000);

    document.addEventListener("visibilitychange", () => {
      if (!document.hidden && (!ws || ws.readyState > 1)) {
        connect();
      }
    });

    window.addEventListener("online", connect);

    log("renderer_initialized", { rendererSessionId, environment: ENVIRONMENT });

    // Check for simulated failure query parameter in canary mode
    const params = new URLSearchParams(location.search);
    const simFail = params.get("fail");
    if (simFail) {
      log("canary_failure_simulated", { failParam: simFail });
      setTimeout(() => {
        triggerFallback("canary_simulated_failure: " + simFail);
      }, 600);
    }
  }

  // Expose public API for the host page
  window.AT140ChatRenderer = {
    init,
    showLegacy,
    triggerFallback,
    simulateFailure: (reason = "user_simulated_failure") => triggerFallback(reason),
    recover: () => {
      userForcedLegacy = false;
      fallbackReason = null;
      fallbackSetAt = 0;
      hideLegacy();
      isRendererActive = true;
      isLegacyVisible = false;
      log("renderer_recovered", { rendererSessionId });
    },
    getHealth: () => ({ ...health, rendererSessionId, environment: ENVIRONMENT, isRendererActive, isLegacyVisible, userForcedLegacy, fallbackReason, fallbackSetAt }),
    getMode: () => isLegacyVisible ? "legacy" : "new",
    setManualLegacy: (forced) => {
      userForcedLegacy = forced;
      if (forced) {
        localStorage.setItem("at140-chat-legacy-fallback", "true");
        showLegacy();
      } else {
        localStorage.removeItem("at140-chat-legacy-fallback");
        userForcedLegacy = false;
        if (container) {
          container.hidden = false;
          hideLegacy();
        }
        isRendererActive = true;
        isLegacyVisible = false;
      }
      log("manual_legacy_set", { forced, rendererSessionId });
    },
  };

  // Auto-init if the page hasn't disabled it
  if (!window.AT140_CHAT_AUTO_INIT_DISABLE) {
    init();
  }
})();
