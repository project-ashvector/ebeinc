(() => {
  "use strict";
  window.AT140InitialAccountMode = new URLSearchParams(location.search).get("account");

  const STREAM_FALLBACK = "https://stream.ebeinc.online/live.mp3";
  const ROUTE_PARAM = "at140_route";
  const routes = new Set(["/", "/live/", "/submit-audio/", "/takeovers/", "/community/", "/visuals/", "/room/", "/roadmap/"]);
  const frame = document.getElementById("routeFrame");
  const status = document.getElementById("routeStatus");
  const audio = document.getElementById("siteRadio");
  const accountShell = document.getElementById("accountShell");
  const savedVolumeRaw = localStorage.getItem("allthings140-volume");
  const savedVolume = Number(savedVolumeRaw);
  if (savedVolumeRaw !== null && Number.isFinite(savedVolume) && savedVolume >= 0 && savedVolume <= 1) audio.volume = savedVolume;
  let listenerVolume = audio.volume;
  let alertDuckFactor = 1;
  function applyListenerVolume(value) {
    listenerVolume = Math.max(0, Math.min(1, Number(value) || 0));
    audio.volume = listenerVolume * alertDuckFactor;
  }
  const clients = new Map();
  let currentClient = null;
  let desiredPlay = false;
  let generation = 0;
  const shellRoute = new URL(location.href).searchParams.get("route") || "/";
  const initialRoute = new URL(shellRoute, location.origin);
  document.body.dataset.route = canonicalPath(initialRoute);

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
        get volume() { return listenerVolume; },
        set volume(value) { applyListenerVolume(value); },
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
        volume: listenerVolume,
        effectiveVolume: audio.volume,
        muted: audio.muted,
        generation,
        src: audio.currentSrc || audio.src,
        route: publicUrl(location.href).pathname + publicUrl(location.href).search + publicUrl(location.href).hash,
      };
    },
  };
  window.AT140Radio = authority;
  window.AT140Navigate = (url) => navigate(url);

  class AccountAlertScheduler {
    constructor() {
      this.catalog = null;
      this.identity = Object.freeze({ signedIn: false });
      this.alertPlayer = new Audio();
      this.alertPlayer.preload = "auto";
      this.timer = 0;
      this.playing = false;
      this.tabId = crypto.randomUUID?.() || `${Date.now()}-${Math.random()}`;
      this.peers = new Map();
      this.channel = typeof BroadcastChannel === "function" ? new BroadcastChannel("at140-radio-owner-v1") : null;
      this.channel?.addEventListener("message", (event) => this.onPeer(event.data));
      this.heartbeat = setInterval(() => this.announce(), 3000);
      this.alertPlayer.addEventListener("ended", () => this.finish());
      this.alertPlayer.addEventListener("error", () => this.finish("media_failed"));
      audio.addEventListener("playing", () => { this.announce(); this.schedule(); });
      audio.addEventListener("pause", () => { this.announce(); this.cancel(); });
      addEventListener("pagehide", () => this.destroy(), { once: true });
      this.bootstrap();
    }

    async bootstrap() {
      try {
        const response = await fetch("/api/public/alert-catalog", { cache: "no-store" });
        if (!response.ok) throw new Error(`catalog_${response.status}`);
        const catalog = await response.json();
        if (!Array.isArray(catalog.alerts) || !Number.isFinite(Number(catalog.interval_seconds))) throw new Error("catalog_invalid");
        this.catalog = catalog;
      } catch (error) {
        console.warn("AT140 alert catalog unavailable; radio continues.", String(error));
        this.catalog = null;
      }
      const connectAuth = () => {
        if (!window.AT140Auth?.subscribe) return false;
        this.unsubscribeAuth = window.AT140Auth.subscribe((identity) => {
          const switched = this.identity.signedIn && identity.signedIn && this.identity.userId !== identity.userId;
          this.identity = identity;
          if (!identity.signedIn || switched) this.cancelActive();
          this.schedule();
        });
        return true;
      };
      if (!connectAuth()) this.authWait = setInterval(() => { if (connectAuth()) clearInterval(this.authWait); }, 100);
      this.announce();
      this.schedule();
    }

    enabledForAccount() {
      return !this.identity.signedIn || this.identity.alertAdsEnabled === true;
    }

    clientFeatureEnabled() {
      if (this.catalog?.client_account_alerts_enabled === true) return true;
      const preview = !["allthings140radio.online", "www.allthings140radio.online"].includes(location.hostname);
      return preview && new URL(location.href).searchParams.get("alert_qa") === "1";
    }

    isOwner() {
      if (audio.paused || !desiredPlay) return false;
      const cutoff = Date.now() - 8000;
      const active = [this.tabId];
      for (const [id, peer] of this.peers) if (peer.playing && peer.at >= cutoff) active.push(id); else if (peer.at < cutoff) this.peers.delete(id);
      return active.sort()[0] === this.tabId;
    }

    announce() {
      this.channel?.postMessage({ id: this.tabId, playing: desiredPlay && !audio.paused, at: Date.now() });
    }

    onPeer(message) {
      if (!message || message.id === this.tabId) return;
      this.peers.set(String(message.id), { playing: Boolean(message.playing), at: Number(message.at) || 0 });
      if (!this.isOwner()) this.cancel();
    }

    intervalMs() {
      const qa = !["allthings140radio.online", "www.allthings140radio.online"].includes(location.hostname)
        && new URL(location.href).searchParams.get("alert_qa") === "1";
      return (qa ? 60 : Math.max(60, Number(this.catalog?.interval_seconds) || 900)) * 1000;
    }

    schedule() {
      this.cancel();
      if (!this.catalog || !this.clientFeatureEnabled() || !this.enabledForAccount() || !this.isOwner() || !this.catalog.alerts.length) return;
      let last = Number(localStorage.getItem("at140-alert-last-played-v1") || 0);
      if (!last) {
        last = Date.now();
        localStorage.setItem("at140-alert-last-played-v1", String(last));
      }
      const delay = Math.max(1000, this.intervalMs() - Math.max(0, Date.now() - last));
      this.timer = setTimeout(() => this.playDue(), delay);
    }

    async playDue() {
      this.timer = 0;
      if (this.playing || !this.clientFeatureEnabled() || !this.enabledForAccount() || !this.isOwner() || audio.paused) return this.schedule();
      const alerts = this.catalog?.alerts || [];
      if (!alerts.length) return;
      const previous = localStorage.getItem("at140-alert-last-id-v1");
      const choices = alerts.filter((item) => item.id !== previous);
      const selected = (choices.length ? choices : alerts)[Math.floor(Math.random() * (choices.length || alerts.length))];
      this.playing = true;
      alertDuckFactor = 0.34;
      applyListenerVolume(listenerVolume);
      this.alertPlayer.src = new URL(selected.url, location.origin).href;
      try {
        await this.alertPlayer.play();
        localStorage.setItem("at140-alert-last-played-v1", String(Date.now()));
        localStorage.setItem("at140-alert-last-id-v1", selected.id);
      } catch (error) {
        console.warn("AT140 alert playback failed; radio continues.", String(error));
        this.finish("play_rejected");
      }
    }

    finish(reason = "complete") {
      if (!this.playing) return;
      this.playing = false;
      this.alertPlayer.removeAttribute("src");
      this.alertPlayer.load();
      alertDuckFactor = 1;
      applyListenerVolume(listenerVolume);
      if (reason !== "complete") console.warn("AT140 alert ended early; next retry remains on normal cadence.", reason);
      this.schedule();
    }

    cancelActive() {
      if (!this.playing) return;
      this.alertPlayer.pause();
      this.finish("entitlement_changed");
    }

    cancel() { if (this.timer) clearTimeout(this.timer); this.timer = 0; }

    inspect() {
      return Object.freeze({
        catalogLoaded: Boolean(this.catalog),
        clientEnabled: this.clientFeatureEnabled(),
        accountEligible: this.enabledForAccount(),
        owner: this.isOwner(),
        playing: this.playing,
        intervalSeconds: this.intervalMs() / 1000,
        serverInjectionEnabled: this.catalog?.server_stream_alert_injection_enabled !== false,
      });
    }

    destroy() {
      this.cancelActive();
      this.cancel();
      clearInterval(this.heartbeat);
      clearInterval(this.authWait);
      this.unsubscribeAuth?.();
      this.channel?.close();
    }
  }

  const alertScheduler = new AccountAlertScheduler();
  window.AT140Alerts = Object.freeze({ inspect: () => alertScheduler.inspect() });

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
    document.body.dataset.route = url.pathname;
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
