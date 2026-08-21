(() => {
  "use strict";

  const STREAM_FALLBACK = "https://stream.ebeinc.online/live.mp3";
  const ROUTE_PARAM = "at140_route";
  const routes = new Set(["/", "/visuals/", "/room/", "/roadmap/"]);
  const frame = document.getElementById("routeFrame");
  const status = document.getElementById("routeStatus");
  const audio = document.getElementById("siteRadio");
  const accountShell = document.getElementById("accountShell");
  const savedVolumeRaw = localStorage.getItem("allthings140-volume");
  const savedVolume = Number(savedVolumeRaw);
  if (savedVolumeRaw !== null && Number.isFinite(savedVolume) && savedVolume >= 0 && savedVolume <= 1) audio.volume = savedVolume;
  const clients = new Map();
  let currentClient = null;
  let desiredPlay = false;
  let generation = 0;
  const shellRoute = new URL(location.href).searchParams.get("route") || "/";
  const initialRoute = new URL(shellRoute, location.origin);

  function canonicalPath(url) {
    let path = url.pathname.replace(/\/index\.html$/, "/");
    if (!path.endsWith("/") && routes.has(path + "/")) path += "/";
    return path;
  }

  function isEligible(url) {
    return url.origin === location.origin && routes.has(canonicalPath(url));
  }

  function publicUrl(input) {
    const url = new URL(input, location.href);
    url.searchParams.delete(ROUTE_PARAM);
    url.pathname = canonicalPath(url);
    return url;
  }

  function frameUrl(input) {
    const url = publicUrl(input);
    url.searchParams.set(ROUTE_PARAM, "1");
    return url.href;
  }

  function dispatch(type) {
    for (const client of clients.values()) client.dispatch(type);
  }

  for (const type of ["playing", "pause", "waiting", "error", "stalled", "ended", "volumechange", "loadedmetadata"]) {
    audio.addEventListener(type, () => dispatch(type));
  }

  const authority = {
    get desiredPlay() { return desiredPlay; },
    get generation() { return generation; },
    get audioElement() { return audio; },
    play() {
      desiredPlay = true;
      if (!audio.src) {
        audio.src = STREAM_FALLBACK;
        audio.load();
        generation += 1;
      }
      return audio.play();
    },
    pause() {
      desiredPlay = false;
      audio.pause();
    },
    client(owner) {
      if (clients.has(owner)) return clients.get(owner).proxy;
      const listeners = new Map();
      const client = {
        dispatch(type) {
          for (const listener of listeners.get(type) || []) {
            try { typeof listener === "function" ? listener.call(proxy, new Event(type)) : listener.handleEvent(new Event(type)); } catch (error) { console.error(error); }
          }
        },
        destroy() { listeners.clear(); clients.delete(owner); },
      };
      const proxy = {
        get paused() { return audio.paused; },
        get ended() { return audio.ended; },
        get error() { return audio.error; },
        get readyState() { return audio.readyState; },
        get networkState() { return audio.networkState; },
        get currentTime() { return audio.currentTime; },
        set currentTime(value) { audio.currentTime = value; },
        get duration() { return audio.duration; },
        get src() { return audio.src; },
        set src(value) {
          const next = new URL(value || STREAM_FALLBACK, location.href).href;
          if (audio.src !== next) { audio.src = next; generation += 1; }
        },
        get volume() { return audio.volume; },
        set volume(value) { audio.volume = value; },
        get muted() { return audio.muted; },
        set muted(value) { audio.muted = Boolean(value); },
        play: () => authority.play(),
        pause: () => authority.pause(),
        load: () => { if (!audio.src) audio.load(); },
        addEventListener(type, listener) {
          if (!listeners.has(type)) listeners.set(type, new Set());
          listeners.get(type).add(listener);
        },
        removeEventListener(type, listener) { listeners.get(type)?.delete(listener); },
      };
      client.proxy = proxy;
      clients.set(owner, client);
      return proxy;
    },
    inspect() {
      return {
        audioElements: document.querySelectorAll("audio").length,
        clients: clients.size,
        desiredPlay,
        paused: audio.paused,
        volume: audio.volume,
        muted: audio.muted,
        generation,
        src: audio.currentSrc || audio.src,
        route: publicUrl(location.href).pathname + publicUrl(location.href).search + publicUrl(location.href).hash,
      };
    },
  };
  window.AT140Radio = authority;
  window.AT140Navigate = (url) => navigate(url);

  function releaseRoute() {
    if (currentClient) {
      clients.get(currentClient)?.destroy();
      currentClient = null;
    }
    try {
      if (frame.contentWindow) frame.contentWindow.dispatchEvent(new PageTransitionEvent("pagehide"));
    } catch {}
  }

  function showError(url) {
    status.hidden = false;
    status.innerHTML = `<div><b>THIS PAGE COULD NOT BE LOADED.</b><br>The radio session is still available.<br><button type="button" id="routeRetry">RETRY</button><a id="routeFallback">OPEN PAGE NORMALLY</a></div>`;
    status.querySelector("#routeRetry").addEventListener("click", () => navigate(url, { replace: true }));
    const fallback = status.querySelector("#routeFallback");
    fallback.href = publicUrl(url).href;
    fallback.addEventListener("click", () => sessionStorage.setItem("at140_shell_bypass", "1"));
  }

  function bindFrame() {
    const win = frame.contentWindow;
    const doc = frame.contentDocument;
    if (!win || !doc) return showError(location.href);
    currentClient = win;
    authority.client(win);
    syncRouteLayout();
    window.AT140Auth?.syncRoute(win);
    status.hidden = true;
    document.title = doc.title || "AllThings140Radio";
    dispatch(audio.paused ? "pause" : "playing");
    if ("mediaSession" in navigator) {
      navigator.mediaSession.setActionHandler("play", () => authority.play());
      navigator.mediaSession.setActionHandler("pause", () => authority.pause());
      navigator.mediaSession.setActionHandler("stop", () => authority.pause());
      navigator.mediaSession.playbackState = audio.paused ? "paused" : "playing";
    }
    doc.addEventListener("click", (event) => {
      if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      const anchor = event.target.closest("a[href]");
      if (!anchor || anchor.target || anchor.hasAttribute("download") || anchor.dataset.noPersistentNav !== undefined) return;
      const url = new URL(anchor.href, frame.contentWindow.location.href);
      if (!isEligible(url)) return;
      event.preventDefault();
      navigate(url);
    }, true);
    win.addEventListener("beforeunload", () => clients.get(win)?.destroy(), { once: true });
    const url = publicUrl(location.href);
    if (url.hash) requestAnimationFrame(() => doc.getElementById(url.hash.slice(1))?.scrollIntoView());
    else win.scrollTo(0, 0);
  }

  function syncRouteLayout() {
    const doc = frame.contentDocument;
    if (!doc?.documentElement) return;
    const wide = window.innerWidth > 680;
    const accountWidth = accountShell?.getBoundingClientRect().width || 0;
    doc.documentElement.style.setProperty("--persistent-account-clearance", wide ? `${Math.ceil(accountWidth + 24)}px` : "12px");
  }

  const accountResizeObserver = typeof ResizeObserver === "function" && accountShell
    ? new ResizeObserver(syncRouteLayout)
    : null;
  accountResizeObserver?.observe(accountShell);
  addEventListener("resize", syncRouteLayout, { passive: true });

  function navigate(input, options = {}) {
    const url = publicUrl(input);
    if (!isEligible(url)) { location.href = url.href; return; }
    const current = publicUrl(location.href);
    if (current.pathname === url.pathname && current.search === url.search && current.hash !== url.hash) {
      if (options.replace) history.replaceState({ at140: true }, "", url.href);
      else if (!options.pop) history.pushState({ at140: true }, "", url.href);
      const target = url.hash && frame.contentDocument?.getElementById(url.hash.slice(1));
      if (target) target.scrollIntoView();
      else frame.contentWindow?.scrollTo(0, 0);
      return;
    }
    releaseRoute();
    status.hidden = false;
    status.textContent = "LOADING TRANSMISSION…";
    if (options.replace) history.replaceState({ at140: true }, "", url.href);
    else if (!options.pop) history.pushState({ at140: true }, "", url.href);
    if (frame.contentWindow?.location) frame.contentWindow.location.replace(frameUrl(url));
    else frame.src = frameUrl(url);
  }

  frame.addEventListener("load", bindFrame);
  frame.addEventListener("error", () => showError(location.href));
  addEventListener("popstate", () => navigate(location.href, { pop: true }));
  if ("scrollRestoration" in history) history.scrollRestoration = "manual";
  history.replaceState({ at140: true }, "", publicUrl(initialRoute).href);
  frame.src = frameUrl(initialRoute);
})();
