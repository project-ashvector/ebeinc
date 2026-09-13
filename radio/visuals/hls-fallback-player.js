/**
 * Singleton HLS fallback for /visuals/.
 * Starts immediately, never depends on workstation/realtime, never pauses
 * because the tab is hidden, and destroys on navigation so instances do not leak.
 */
(() => {
  const nativeHls = (video) => video.canPlayType('application/vnd.apple.mpegurl') || video.canPlayType('application/x-mpegURL');
  const useHlsJs = () => Boolean(window.Hls && Hls.isSupported());

  const state = {
    video: null,
    hls: null,
    url: '',
    startedAt: 0,
    firstFrameAt: 0,
    retries: 0,
    errors: [],
    stallTimer: 0,
    lastTime: 0,
    lastProgressAt: 0,
    listeners: [],
    destroyed: false
  };

  function log(event, data = {}) {
    console.info('[AT140 HLS]', event, data);
  }

  function recordError(kind, detail) {
    state.errors.push({ t: Date.now(), kind, detail: String(detail || '') });
    if (state.errors.length > 50) state.errors.splice(0, state.errors.length - 50);
    state.retries += 1;
    log('error', { kind, detail, retries: state.retries });
  }

  function hasDecodedFrame(video = state.video) {
    if (!video) return false;
    return video.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA && video.videoWidth > 0 && !video.paused;
  }

  function add(target, type, fn, opts) {
    target.addEventListener(type, fn, opts);
    state.listeners.push([target, type, fn, opts]);
  }

  function clearListeners() {
    for (const [target, type, fn, opts] of state.listeners) {
      try { target.removeEventListener(type, fn, opts); } catch (_) {}
    }
    state.listeners = [];
  }

  function play() {
    const video = state.video;
    if (!video || state.destroyed) return Promise.resolve();
    const p = video.play();
    if (p && typeof p.then === 'function') {
      return p.catch(() => {
        const unlock = () => {
          video.play().catch(() => {});
          document.removeEventListener('pointerdown', unlock);
          document.removeEventListener('keydown', unlock);
        };
        document.addEventListener('pointerdown', unlock, { once: true });
        document.addEventListener('keydown', unlock, { once: true });
      });
    }
    return Promise.resolve();
  }

  function loopToStart() {
    const video = state.video;
    if (!video || state.destroyed) return;
    try { video.currentTime = 0; } catch (_) {}
    if (state.hls) {
      try { state.hls.startLoad(0); } catch (_) {}
    }
    play();
  }

  function recover(kind) {
    recordError(kind, kind);
    if (state.hls) {
      try {
        if (kind === 'media') state.hls.recoverMediaError();
        else state.hls.startLoad();
      } catch (_) {
        try { state.hls.startLoad(); } catch (__) {}
      }
    } else {
      loopToStart();
    }
    play();
  }

  function attachHlsJs(url) {
    state.hls = new Hls({
      enableWorker: true,
      lowLatencyMode: false,
      backBufferLength: 30,
      maxBufferLength: 30,
      maxMaxBufferLength: 60,
      startLevel: 0,
      capLevelToPlayerSize: true,
      abrEwmaDefaultEstimate: 3e6,
      manifestLoadingMaxRetry: 6,
      levelLoadingMaxRetry: 6,
      fragLoadingMaxRetry: 8,
      fragLoadingRetryDelay: 500
    });
    state.hls.loadSource(url);
    state.hls.attachMedia(state.video);
    state.hls.on(Hls.Events.MANIFEST_PARSED, () => { play(); });
    state.hls.on(Hls.Events.FRAG_CHANGED, () => {
      if (!state.firstFrameAt && hasDecodedFrame()) state.firstFrameAt = Date.now();
    });
    state.hls.on(Hls.Events.ERROR, (_event, data) => {
      if (!data) return;
      if (!data.fatal) {
        if (data.details === 'fragLoadError' || data.details === 'fragLoadTimeOut') recover('frag');
        return;
      }
      if (data.type === Hls.ErrorTypes.NETWORK_ERROR) recover('network');
      else if (data.type === Hls.ErrorTypes.MEDIA_ERROR) recover('media');
      else recover('fatal');
    });
  }

  function attachNative(url) {
    state.video.src = url;
    state.video.load();
    play();
  }

  function watchStalls() {
    clearInterval(state.stallTimer);
    state.lastTime = 0;
    state.lastProgressAt = Date.now();
    state.stallTimer = setInterval(() => {
      const video = state.video;
      if (!video || state.destroyed) return;
      if (document.hidden) {
        play();
        return;
      }
      const t = video.currentTime || 0;
      if (t !== state.lastTime && !video.paused) {
        state.lastTime = t;
        state.lastProgressAt = Date.now();
        if (!state.firstFrameAt && hasDecodedFrame()) state.firstFrameAt = Date.now();
        return;
      }
      if (Date.now() - state.lastProgressAt > 4000) {
        state.lastProgressAt = Date.now();
        recover('stall');
      }
    }, 1000);
  }

  function start(video) {
    if (!video) return;
    const url = video.dataset.desktopSrc || video.getAttribute('data-desktop-src') || '';
    if (!url) return;
    if (state.video === video && state.url === url && !state.destroyed && (state.hls || video.src)) {
      play();
      return;
    }
    destroy({ keepVideo: true });
    state.destroyed = false;
    state.video = video;
    state.url = url;
    state.startedAt = Date.now();
    state.firstFrameAt = 0;
    video.muted = true;
    video.defaultMuted = true;
    video.playsInline = true;
    video.loop = true;
    if (video.dataset.desktopPoster) video.poster = video.dataset.desktopPoster;

    add(video, 'ended', loopToStart);
    add(video, 'pause', () => { play(); });
    add(video, 'stalled', () => recover('stalled'));
    add(video, 'error', () => recover('element'));
    add(video, 'playing', () => {
      if (!state.firstFrameAt && hasDecodedFrame()) state.firstFrameAt = Date.now();
    });
    add(document, 'visibilitychange', () => { play(); });
    add(window, 'online', () => recover('online'));
    add(window, 'pagehide', () => destroy());
    add(window, 'pageshow', (event) => {
      if (event.persisted) {
        state.destroyed = false;
        start(video);
      } else play();
    });

    if (nativeHls(video) && !useHlsJs()) attachNative(url);
    else if (useHlsJs()) attachHlsJs(url);
    else if (nativeHls(video)) attachNative(url);
    else attachNative(url);

    watchStalls();
    play();
    log('start', { url, engine: state.hls ? 'hls.js' : 'native' });
  }

  function destroy(opts = {}) {
    clearInterval(state.stallTimer);
    state.stallTimer = 0;
    clearListeners();
    if (state.hls) {
      try { state.hls.destroy(); } catch (_) {}
      state.hls = null;
    }
    if (state.video && !opts.keepVideo) {
      try { state.video.pause(); } catch (_) {}
      try {
        state.video.removeAttribute('src');
        state.video.load();
      } catch (_) {}
    }
    state.destroyed = true;
  }

  function waitForFrame(timeoutMs = 8000) {
    const startAt = Date.now();
    return new Promise((resolve) => {
      const tick = () => {
        if (hasDecodedFrame()) return resolve(true);
        if (Date.now() - startAt >= timeoutMs) return resolve(false);
        setTimeout(tick, 80);
      };
      tick();
    });
  }

  window.AT140HlsFallback = {
    start,
    play,
    destroy,
    hasDecodedFrame,
    waitForFrame,
    stats() {
      return {
        url: state.url,
        engine: state.hls ? 'hls.js' : (state.video ? 'native' : 'idle'),
        retries: state.retries,
        errors: state.errors.slice(),
        startupMs: state.firstFrameAt && state.startedAt ? state.firstFrameAt - state.startedAt : null,
        levels: state.hls && state.hls.levels ? state.hls.levels.map((l) => ({
          bitrate: l.bitrate, width: l.width, height: l.height
        })) : [],
        currentLevel: state.hls ? state.hls.currentLevel : null
      };
    }
  };
})();
