(() => {
  "use strict";

  const STATUS_URLS = ["/api/public/status", "https://status.ebeinc.online/api/public/status"];
  const SCHEDULE_URLS = ["/api/public/schedule", "https://status.ebeinc.online/api/public/schedule"];
  const ALERTS_URL = "/api/public/alerts";

  const $ = s => document.querySelector(s);
  const audio = window.top !== window && window.top.AT140Radio
    ? window.top.AT140Radio.client(window)
    : $("#audio");
  const heroPlay = $("#heroPlay");
  const miniPlay = $("#miniPlay");
  const miniPlayer = $("#miniPlayer");
  const message = $("#message");
  const mode = $("#mode");
  const header = $("#headerStatus");
  const title = $("#trackTitle");
  const artist = $("#trackArtist");
  const listeners = $("#listeners");
  const timeline = $("#timeline");
  const elapsed = $("#elapsed");
  const duration = $("#duration");
  const next = $("#nextTrack");
  const footer = $("#footerStatus");
  const miniTitle = $("#miniTitle");
  const miniArtist = $("#miniArtist");
  const miniListeners = $("#miniListeners");
  const historyEl = $("#trackHistory");
  const backgroundVideo = $("#backgroundVideo");
  const liveTakeover = $("#liveTakeover");
  const liveHostName = $("#liveHostName");
  const volumeControl = $("#volumeControl");
  const muteControl = $("#muteControl");
  const miniMute = $("#miniMute");
  const sleepTimer = $("#sleepTimer");
  const sleepStatus = $("#sleepStatus");
  const motionToggle = $("#motionToggle");

  let latest = null;
  let desiredPlay = window.top !== window && window.top.AT140Radio
    ? window.top.AT140Radio.desiredPlay
    : false;
  let streamUrl = "";
  let reconnectTimer = null;
  let reconnectAttempts = 0;
  let isResolving = false;
  let lastAudioTime = 0;
  let lastAudioProgressAt = Date.now();
  let sleepUntil = Number(localStorage.getItem("allthings140-sleep-until")) || 0;
  let lastVolume = Number(localStorage.getItem("allthings140-volume") || 0.78);
  let statusPending = false;
  let lastAlertAt = 0;
  let alertQueue = [];
  let alertActive = false;

  const pageStartedAt = Date.now();
  const clientId = sessionStorage.getItem("allthings140-client-id") || (crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).slice(2));
  sessionStorage.setItem("allthings140-client-id", clientId);

  const fmt = s => {
    s = Math.max(0, Math.floor(Number(s) || 0));
    return Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0");
  };

  const clean = v => String(v ?? "")
    .replace(/â€”/g, "—")
    .replace(/â€“/g, "–")
    .replace(/â€™|â€˜/g, "'")
    .replace(/â€œ|â€ /g, '"')
    .replace(/Â/g, " ")
    .replace(/\s+/g, " ")
    .trim();

  function trackLabel(s) {
    return clean([s.current_artist, s.current_title].filter(Boolean).join(" — ") || s.current_title || "AllThings140Radio");
  }

  function setPlayingState(playing) {
    document.body.classList.toggle("playing", playing);
    heroPlay.textContent = playing ? "❚❚ PAUSE FEED" : "▶ CONNECT TO FEED";
    heroPlay.removeAttribute("aria-busy");
    heroPlay.disabled = false;
    miniPlay.textContent = playing ? "❚❚" : "▶";
    miniPlay.setAttribute("aria-label", playing ? "Pause station" : "Play station");
    miniPlay.disabled = false;
    if ("mediaSession" in navigator) {
      navigator.mediaSession.playbackState = playing ? "playing" : "paused";
    }
  }

  function setConnectingState(connecting) {
    heroPlay.disabled = connecting;
    miniPlay.disabled = connecting;
    heroPlay.setAttribute("aria-busy", String(connecting));
    if (connecting) {
      heroPlay.textContent = "◌ CONNECTING…";
      setMsg("Connecting to the live feed…");
    }
  }

  function setBufferingState() {
    if (!desiredPlay) return;
    heroPlay.textContent = "◌ BUFFERING…";
    heroPlay.setAttribute("aria-busy", "true");
    setMsg("Buffering the live feed…");
  }

  function pill(text, state) {
    mode.dataset.state = state;
    header.dataset.state = state;
    const dot1 = document.createElement("i");
    const dot2 = document.createElement("i");
    mode.replaceChildren(dot1, document.createTextNode(" " + text));
    header.replaceChildren(dot2, document.createTextNode(" " + text));
    document.body.dataset.broadcast = state;
  }

  function setMsg(text, kind = "") {
    message.textContent = text;
    message.className = "message " + kind;
  }

  function updateClock() {
    if (latest) {
      const dur = Number(latest.duration_seconds) || 0;
      const base = Number(latest._position_at_received ?? latest.position_seconds) || 0;
      const receivedAt = Number(latest._received_at) || Date.now() / 1000;
      const pos = Math.min(dur || Infinity, base + Math.max(0, Date.now() / 1000 - receivedAt));
      elapsed.textContent = fmt(pos);
      duration.textContent = fmt(dur);
      timeline.style.width = (dur ? Math.min(100, (pos / dur) * 100) : 0) + "%";
    }

    document.querySelectorAll(".countdown[data-start]").forEach(count => {
      const now = Date.now();
      const start = Number(count.dataset.start);
      const end = Number(count.dataset.end);
      if (now < start) {
        const total = Math.max(0, Math.floor((start - now) / 1000));
        const days = Math.floor(total / 86400);
        const hours = Math.floor((total % 86400) / 3600);
        const mins = Math.floor((total % 3600) / 60);
        count.textContent = `LIVE IN ${days ? days + "D " : ""}${String(hours).padStart(2, "0")}H ${String(mins).padStart(2, "0")}M`;
      } else if (now < end) {
        count.textContent = "● LIVE NOW";
      } else {
        count.textContent = "TAKEOVER ENDED";
      }
    });
  }

  function setVolume(value) {
    const level = Math.max(0, Math.min(1, Number(value)));
    audio.volume = level;
    audio.muted = level === 0;
    volumeControl.value = String(Math.round(level * 100));
    if (level > 0) {
      lastVolume = level;
      localStorage.setItem("allthings140-volume", String(level));
    }
    const muted = audio.muted;
    muteControl.textContent = muted ? "UNMUTE" : "MUTE";
    miniMute.textContent = muted ? "MUTED" : "VOL";
    miniMute.setAttribute("aria-label", muted ? "Unmute station" : "Mute station");
  }

  function toggleMute() {
    if (audio.muted || audio.volume === 0) {
      setVolume(lastVolume > 0 ? lastVolume : 0.78);
    } else {
      setVolume(0);
    }
  }

  function setSleep(minutes) {
    sleepUntil = minutes ? Date.now() + Number(minutes) * 60000 : 0;
    localStorage.setItem("allthings140-sleep-until", String(sleepUntil));
    updateSleep();
  }

  function updateSleep() {
    if (!sleepUntil) {
      sleepStatus.textContent = "";
      sleepTimer.value = "0";
      return;
    }
    const remaining = sleepUntil - Date.now();
    if (remaining <= 0) {
      sleepUntil = 0;
      localStorage.removeItem("allthings140-sleep-until");
      sleepTimer.value = "0";
      sleepStatus.textContent = "SLEEP TIMER ENDED";
      desiredPlay = false;
      audio.pause();
      setPlayingState(false);
      setMsg("Sleep timer ended. The station is paused.", "good");
      return;
    }
    sleepStatus.textContent = `${Math.ceil(remaining / 60000)} MIN LEFT`;
  }

  function updateMediaSession(label, host) {
    if (!("mediaSession" in navigator)) return;
    navigator.mediaSession.metadata = new MediaMetadata({
      title: label,
      artist: host || "AllThings140Radio",
      album: "AllThings140Radio Live",
      artwork: [
        { src: new URL("assets/allthings140-logo-512.png", location.href).href, sizes: "512x512", type: "image/png" }
      ]
    });
  }

  function renderHistory(s) {
    if (!historyEl) return;
    const incoming = Array.isArray(s.recent_tracks) ? s.recent_tracks : Array.isArray(s.recent_history) ? s.recent_history : [];
    let history = incoming;
    try {
      if (!history.length) history = JSON.parse(localStorage.getItem("allthings140-track-history") || "[]");
    } catch {
      history = [];
    }
    if (!Array.isArray(history)) history = [];

    const current = {
      id: s.current_track_id,
      title: clean(s.current_title),
      artist: clean(s.current_artist),
      started_at: s.started_at
    };

    if (current.title && current.id && (!history[0] || String(history[0].id) !== String(current.id))) {
      history = [current, ...history.filter(item => String(item.id) !== String(current.id))].slice(0, 10);
      localStorage.setItem("allthings140-track-history", JSON.stringify(history));
    }

    historyEl.replaceChildren();
    if (!history.length) {
      const li = document.createElement("li");
      const sp = document.createElement("span");
      sp.textContent = "Waiting for the next track update…";
      li.append(sp);
      historyEl.append(li);
      return;
    }

    history.forEach((item, index) => {
      const li = document.createElement("li");
      const num = document.createElement("b");
      const label = document.createElement("span");
      const time = document.createElement("time");
      num.textContent = String(index + 1);
      label.textContent = clean([item.artist, item.title].filter(Boolean).join(" — ") || "Unknown transmission");
      time.textContent = item.started_at ? new Date(Number(item.started_at) * 1000).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }) : "RECENT";
      li.append(num, label, time);
      historyEl.append(li);
    });
  }

  function attachStream(url) {
    if (!url) return;
    if (streamUrl !== url) {
      streamUrl = url;
      audio.src = streamUrl;
      audio.load();
    }
  }

  function apply(s) {
    const receivedAt = Date.now() / 1000;
    const durationSeconds = Math.max(0, Number(s.duration_seconds) || 0);
    const serverTime = Number(s.server_time);
    const startedAt = Number(s.started_at);
    let positionAtReceived = Math.max(0, Number(s.position_seconds) || 0);
    // Anchor the counter to the station clock, not to when a delayed HTTP
    // response happened to reach the browser. This corrects request latency
    // and resets cleanly on every server-reported track transition.
    if (Number.isFinite(serverTime) && serverTime > 0) {
      if (Number.isFinite(startedAt) && startedAt > 0) {
        positionAtReceived = Math.max(0, serverTime - startedAt);
      }
      positionAtReceived += Math.max(0, receivedAt - serverTime);
    }
    if (durationSeconds > 0) positionAtReceived = Math.min(durationSeconds, positionAtReceived);
    latest = { ...s, _received_at: receivedAt, _position_at_received: positionAtReceived };

    const takeover = s.active_takeover || null;
    const isLive = s.mode === "live" || s.live === true;
    const sourceTitle = clean(s.current_title || "");
    const inferredHost = sourceTitle.match(/(?:Guest|Live).*?([A-Za-z0-9][A-Za-z0-9 _.'-]*)$/i)?.[1];
    const liveHost = clean(takeover?.artist || s.live_host || inferredHost || "GUEST DJ");
    const liveLabel = `NOW LIVE: ${liveHost}`;

    const label = isLive ? liveLabel : clean(s.current_title || "AllThings140Radio");
    const host = isLive ? "" : clean(s.current_artist || "24/7 heavy dubstep");

    listeners.textContent = miniListeners.textContent = String(s.listeners || 0);
    title.textContent = miniTitle.textContent = label;
    artist.textContent = miniArtist.textContent = host;
    next.textContent = clean([s.next_artist, s.next_title].filter(Boolean).join(" — ") || "—");

    renderHistory(s);
    attachStream(s.stream_url || s.hls_url);
    updateMediaSession(label, host);
    pill(isLive ? liveLabel : "24/7 DUBSTEP", isLive ? "live" : "autodj");

    liveTakeover.hidden = !isLive;
    if (isLive && liveHostName) liveHostName.textContent = liveHost;

    const takeoverBox = $("#homeTakeoverLogo");
    if (takeoverBox) {
      takeoverBox.hidden = !takeover;
      if (takeover) {
        $("#homeTakeoverImage").src = takeover.logo_url || "assets/takeover-fallback-logo.webp";
        $("#homeTakeoverArtist").textContent = clean(takeover.artist, "GUEST DJ");
      }
    }

    footer.textContent = `SYSTEM STATUS: ${isLive ? liveLabel : "24/7 HEAVY DUBSTEP"} // ${s.listeners || 0} CONNECTED`;
    setMsg(
      audio.paused && desiredPlay
        ? "Rejoining the live feed…"
        : audio.paused
        ? "Station uplink established. Press play to join the shared transmission."
        : "Connected to the live feed.",
      "good"
    );
    updateClock();
    return true;
  }

  async function poll(reason = "interval", force = false) {
    if (statusPending && !force) return false;
    statusPending = true;
    let ok = false;
    try {
      for (const endpoint of STATUS_URLS) {
        const ctl = new AbortController();
        const timer = setTimeout(() => ctl.abort(), 5500);
        try {
          const sep = endpoint.includes("?") ? "&" : "?";
          const r = await fetch(endpoint + sep + "t=" + Date.now(), {
            cache: "no-store",
            signal: ctl.signal,
            headers: { Accept: "application/json" }
          });
          if (!r.ok) throw new Error(`HTTP ${r.status}`);
          const s = await r.json();
          if (!s.online) throw new Error("offline");
          ok = apply(s);
          break;
        } catch {
        } finally {
          clearTimeout(timer);
        }
      }
      return ok;
    } finally {
      statusPending = false;
    }
  }

  async function connectAudio() {
    if (isResolving) return;
    isResolving = true;
    setConnectingState(true);
    try {
      if (!streamUrl) {
        await poll("user-connect", true);
      }
      if (!audio.src && streamUrl) {
        audio.src = streamUrl;
        audio.load();
      }
      await audio.play();
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
      reconnectAttempts = 0;
      setPlayingState(true);
      setMsg("Connected to the live feed.", "good");
    } catch (error) {
      if (error?.name === "NotAllowedError") {
        desiredPlay = false;
        setPlayingState(false);
        setMsg("Click play to join the shared broadcast.", "");
      } else if (desiredPlay) {
        scheduleAudioReconnect("play-failed");
      } else {
        setPlayingState(false);
        setMsg("Could not connect to the stream. Try again shortly.", "bad");
      }
    } finally {
      isResolving = false;
      setConnectingState(false);
    }
  }

  function scheduleAudioReconnect(reason = "stream-interrupted") {
    if (!desiredPlay || reconnectTimer) return;
    setPlayingState(false);
    setMsg("Stream interrupted. Reconnecting automatically…", "bad");
    const wait = Math.min(15000, 1000 * Math.pow(2, Math.min(reconnectAttempts++, 4)));
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null;
      if (desiredPlay) connectAudio();
    }, wait);
  }

  async function togglePlay() {
    if (desiredPlay && !audio.paused) {
      desiredPlay = false;
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
      audio.pause();
      setPlayingState(false);
      setMsg("Station paused. Click play to resume.", "");
      return;
    }
    desiredPlay = true;
    await connectAudio();
  }

  async function shareStation() {
    const data = {
      title: "AllThings140Radio",
      text: latest ? `Now playing: ${trackLabel(latest)} on AllThings140Radio` : "Tune into 24/7 heavy bass on AllThings140Radio",
      url: "https://allthings140radio.online/"
    };
    try {
      if (navigator.share) {
        await navigator.share(data);
      } else {
        await navigator.clipboard.writeText(`${data.text} — ${data.url}`);
        const btn = $("#shareStation");
        btn.textContent = "✓ LINK COPIED";
        setTimeout(() => (btn.textContent = "↗ SHARE STATION"), 1800);
      }
    } catch {}
  }

  function setReducedMotion(reduced) {
    document.body.classList.toggle("reduced-motion", reduced);
    motionToggle.setAttribute("aria-pressed", String(reduced));
    motionToggle.textContent = reduced ? "▶ MOTION" : "◉ MOTION";
    localStorage.setItem("allthings140-background-motion-disabled-v2", String(reduced));
    if (backgroundVideo) {
      if (reduced) backgroundVideo.pause();
      else backgroundVideo.play().catch(() => {});
    }
  }

  // Audio Event Listeners
  audio.addEventListener("playing", () => {
    reconnectAttempts = 0;
    lastAudioProgressAt = Date.now();
    setPlayingState(true);
    setMsg("Connected to the live feed.", "good");
  });
  audio.addEventListener("waiting", () => setBufferingState());
  audio.addEventListener("error", () => { if (desiredPlay) scheduleAudioReconnect("audio-error"); });
  audio.addEventListener("stalled", () => { if (desiredPlay && audio.readyState < 3) setBufferingState(); });
  audio.addEventListener("ended", () => { if (desiredPlay) scheduleAudioReconnect("audio-ended"); });
  audio.addEventListener("pause", () => {
    if (desiredPlay && !reconnectTimer && !isResolving) {
      scheduleAudioReconnect("unexpected-pause");
    }
  });

  // Background Video Setup
  if (backgroundVideo) {
    backgroundVideo.muted = true;
    backgroundVideo.defaultMuted = true;
    backgroundVideo.playsInline = true;
    backgroundVideo.loop = true;

    const playVideo = () => {
      if (document.body.classList.contains("reduced-motion") || document.hidden) return;
      backgroundVideo.play().catch(() => {});
    };

    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", playVideo);
    } else {
      playVideo();
    }
    window.addEventListener("load", playVideo);
    document.addEventListener("pointerdown", playVideo, { once: true });
    backgroundVideo.addEventListener("ended", () => {
      backgroundVideo.currentTime = 0;
      playVideo();
    });
    document.addEventListener("visibilitychange", () => {
      if (document.hidden) {
        backgroundVideo.pause();
      } else {
        playVideo();
        poll("visibility-change", true);
      }
    });
  }

  // User Interaction Bindings
  heroPlay.addEventListener("click", togglePlay);
  miniPlay.addEventListener("click", togglePlay);
  $("#shareStation").addEventListener("click", shareStation);
  motionToggle.addEventListener("click", () => setReducedMotion(!document.body.classList.contains("reduced-motion")));

  volumeControl.addEventListener("input", () => setVolume(Number(volumeControl.value) / 100));
  muteControl.addEventListener("click", toggleMute);
  miniMute.addEventListener("click", toggleMute);
  sleepTimer.addEventListener("change", () => setSleep(Number(sleepTimer.value)));

  setVolume(Number.isFinite(lastVolume) && lastVolume >= 0 ? lastVolume : 0.78);
  updateSleep();
  // Ignore the legacy preference: it was set during the broken-video rollout
  // and could make a repaired homepage look broken forever on that browser.
  localStorage.removeItem("allthings140-reduced-motion");
  setReducedMotion(localStorage.getItem("allthings140-background-motion-disabled-v2") === "true");

  // MediaSession API handlers
  if ("mediaSession" in navigator) {
    navigator.mediaSession.setActionHandler("play", () => {
      desiredPlay = true;
      if (audio.paused) togglePlay();
    });
    navigator.mediaSession.setActionHandler("pause", () => {
      desiredPlay = false;
      audio.pause();
      setPlayingState(false);
    });
    navigator.mediaSession.setActionHandler("stop", () => {
      desiredPlay = false;
      audio.pause();
      setPlayingState(false);
    });
  }

  // Mini Player intersection observer
  new IntersectionObserver(
    ([entry]) => {
      miniPlayer.hidden = entry.isIntersecting;
      document.body.classList.toggle("mini-visible", !entry.isIntersecting);
    },
    { threshold: 0.1 }
  ).observe($("#listen"));

  const updatePersistentPlayerHeight = () => {
    const height = miniPlayer.getBoundingClientRect().height;
    if (height > 0) document.documentElement.style.setProperty("--persistent-player-height", `${Math.ceil(height)}px`);
  };
  updatePersistentPlayerHeight();
  if (typeof ResizeObserver === "function") new ResizeObserver(updatePersistentPlayerHeight).observe(miniPlayer);

  // Navigation Menu Toggle
  const navMenu = $(".nav-menu");
  const navToggle = $("#navToggle");
  const siteNav = $("#siteNav");
  if (navMenu && navToggle && siteNav) {
    const closeMenu = () => {
      navMenu.classList.remove("is-open");
      navToggle.setAttribute("aria-expanded", "false");
      siteNav.hidden = true;
      body.classList.remove("nav-open");
    };
    navToggle.addEventListener("click", () => {
      const open = !navMenu.classList.contains("is-open");
      navMenu.classList.toggle("is-open", open);
      navToggle.setAttribute("aria-expanded", String(open));
      siteNav.hidden = !open;
      if (open) {
        body.classList.add("nav-open");
      } else {
        body.classList.remove("nav-open");
      }
    });
    siteNav.addEventListener("click", event => {
      const target = event.target.closest("a,button");
      if (!target) return;
      const href = target.getAttribute("href") || "";
      if (href.startsWith("#")) {
        event.preventDefault();
        const section = $(href);
        closeMenu();
        if (section) {
          section.scrollIntoView({ behavior: "smooth", block: "start" });
        }
      } else {
        closeMenu();
      }
    });
    document.addEventListener("keydown", event => {
      if (event.key === "Escape") closeMenu();
    });
    document.addEventListener("pointerdown", event => {
      if (navMenu.classList.contains("is-open") && !navMenu.contains(event.target)) {
        closeMenu();
      }
    });
  }

  // Track Request Form
  const requestForm = $("#requestForm");
  if (requestForm) {
    requestForm.addEventListener("submit", async event => {
      event.preventDefault();
      const feedback = $("#requestFeedback");
      const titleVal = $("#requestTitle").value.trim();
      const artistVal = $("#requestArtist").value.trim();
      if (!titleVal) return;
      feedback.textContent = "Sending request…";
      try {
        const res = await fetch("/api/public/requests", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ title: titleVal, artist: artistVal, started_at: pageStartedAt })
        });
        if (!res.ok) throw new Error("Could not send request");
        requestForm.reset();
        feedback.textContent = "✓ Request sent to the hosts.";
        feedback.style.color = "var(--green)";
      } catch {
        feedback.textContent = "Request received. Thank you!";
        feedback.style.color = "var(--green)";
      }
    });
  }

  // Submission Form
  const submissionForm = $("#submissionForm");
  const submissionType = $("#submissionType");
  const updateSubmissionType = () => {
    if (!submissionType) return;
    const isMix = submissionType.value === "recorded_mix";
    const mixFields = $("#recordedMixFields");
    if (mixFields) mixFields.hidden = !isMix;
    $("#submissionHeading").textContent = isMix ? "SEND YOUR RECORDED MIX FOR REVIEW" : "SEND YOUR TRACK FOR REVIEW";
    $("#submissionTitleLabel").textContent = isMix ? "MIX TITLE" : "TRACK TITLE";
    $("#submissionLinkLabel").textContent = isMix ? "MIX DOWNLOAD LINK" : "TRACK DOWNLOAD LINK";
  };
  if (submissionType) {
    submissionType.addEventListener("change", updateSubmissionType);
    updateSubmissionType();
  }
  if (submissionForm) {
    submissionForm.addEventListener("submit", async event => {
      event.preventDefault();
      const feedback = $("#submissionFeedback");
      const button = submissionForm.querySelector("button[type=submit]");
      button.disabled = true;
      feedback.textContent = "Sending submission…";
      try {
        const response = await fetch("/api/public/submissions", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            submission_type: submissionType.value,
            artist: $("#submissionArtist").value.trim(),
            title: $("#submissionTitle").value.trim(),
            track_url: $("#submissionTrackUrl").value.trim(),
            duration_minutes: $("#submissionDuration")?.value || 0,
            genres: $("#submissionGenres")?.value || "",
            tracklist: $("#submissionTracklist")?.value || "",
            rights_confirmed: $("#submissionRights")?.checked || true,
            email: $("#submissionEmail").value.trim(),
            notes: $("#submissionNotes")?.value || "",
            started_at: pageStartedAt
          })
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || "Submission failed");
        submissionForm.reset();
        updateSubmissionType();
        feedback.textContent = "✓ Submission received! The team will review your audio.";
        feedback.style.color = "var(--green)";
      } catch (error) {
        feedback.textContent = error.message || "Could not send submission.";
        feedback.style.color = "var(--danger)";
      } finally {
        button.disabled = false;
      }
    });
  }

  // Schedule Polling & Rendering
  function renderSchedule(payload) {
    const root = $("#takeoverSchedule");
    if (!root) return;
    const rows = Array.isArray(payload.takeovers) ? payload.takeovers : [];
    root.replaceChildren();
    if (!rows.length) {
      root.innerHTML = '<div class="takeover-empty"><h3>24/7 HEAVY ROTATION</h3><p>The synchronized station is broadcasting now.</p><b class="countdown">ALWAYS ON</b></div>';
      return;
    }
    rows.forEach(row => {
      const card = document.createElement("section");
      card.className = "takeover-item";
      const titleEl = document.createElement("h3");
      const meta = document.createElement("p");
      const details = document.createElement("p");
      const count = document.createElement("b");
      titleEl.textContent = clean(row.title || row.artist);
      meta.className = "takeover-meta";
      meta.textContent = `${clean(row.artist)} // ${new Date(Number(row.starts_at) * 1000).toLocaleString()}`;
      details.textContent = clean(row.details || "Live guest takeover on AllThings140Radio.");
      count.className = "countdown";
      count.dataset.start = String(Number(row.starts_at) * 1000);
      count.dataset.end = String(Number(row.ends_at) * 1000);
      card.append(titleEl, meta, details, count);
      root.append(card);
    });
    updateClock();
  }

  async function pollSchedule() {
    for (const endpoint of SCHEDULE_URLS) {
      try {
        const response = await fetch(endpoint + "?t=" + Date.now(), { cache: "no-store" });
        if (!response.ok) throw new Error();
        renderSchedule(await response.json());
        return;
      } catch {}
    }
  }

  // Site Content (Sponsors, Partners, Takeover Archives)
  async function loadSiteContent() {
    try {
      const r = await fetch("data/site-content.json?t=" + Date.now());
      if (!r.ok) return;
      const data = await r.json();
      
      const sg = $("#sponsorsGrid");
      if (sg) {
        sg.replaceChildren();
        const activeSponsors = Array.isArray(data.sponsors) ? data.sponsors.filter(s => s.active).sort((a,b) => (a.ordering||0)-(b.ordering||0)) : [];
        if (activeSponsors.length) {
          activeSponsors.forEach(s => {
            const art = document.createElement("article");
            art.className = "brand-card" + (s.featured || s.tier === "Headline" ? " headline" : "");
            art.innerHTML = `<span class="brand-tier">${clean(s.tier || "SPONSOR").toUpperCase()}</span><img src="${clean(s.logoUrl || "assets/allthings140-logo-192.webp")}" alt="${clean(s.name)}" class="brand-logo"><h3>${clean(s.name)}</h3><p>${clean(s.description)}</p><a class="brand-link" href="${clean(s.websiteUrl || "#")}" target="_blank" rel="noopener">VISIT SPONSOR ↗</a>`;
            sg.append(art);
          });
        } else {
          const empty = document.createElement("div");
          empty.className = "brand-empty-state";
          empty.innerHTML = "<p>Official station sponsors and audio partners will be announced soon. Independent sound systems, record labels, and audio brands can reach out below.</p>";
          sg.append(empty);
        }
      }

      const pg = $("#partnersGrid");
      if (pg) {
        pg.replaceChildren();
        const activePartners = Array.isArray(data.partners) ? data.partners.filter(p => p.active).sort((a,b) => (a.ordering||0)-(b.ordering||0)) : [];
        if (activePartners.length) {
          activePartners.forEach(p => {
            const art = document.createElement("article");
            art.className = "brand-card partner";
            art.innerHTML = `<span class="brand-tier partner-tier">${clean(p.category || "PARTNER").toUpperCase()}</span><img src="${clean(p.logoUrl || "assets/allthings140-logo-192.webp")}" alt="${clean(p.name)}" class="brand-logo"><h3>${clean(p.name)}</h3><p>${clean(p.description)}</p><a class="brand-link" href="${clean(p.websiteUrl || "#")}" target="_blank" rel="noopener">EXPLORE PARTNER ↗</a>`;
            pg.append(art);
          });
        } else {
          const empty = document.createElement("div");
          empty.className = "brand-empty-state";
          empty.innerHTML = "<p>Ecosystem partners, underground collectives, and festival affiliations will be announced soon.</p>";
          pg.append(empty);
        }
      }

      if (Array.isArray(data.takeovers) && data.takeovers.length) {
        const tag = $("#takeoverArchiveGrid");
        if (tag) {
          tag.replaceChildren();
          data.takeovers.slice(0, 12).forEach(t => {
            const art = document.createElement("article");
            art.className = "takeover-archive-card";
            const tracklistHtml = Array.isArray(t.tracklist) && t.tracklist.length ? `<div class="tac-tracklist"><small>FEATURED SELECTIONS:</small><p>${clean(t.tracklist.join(" • "))}</p></div>` : "";
            art.innerHTML = `<div class="tac-header"><img src="${clean(t.logoUrl || "assets/takeover-fallback-logo.webp")}" alt="${clean(t.artist)} logo" class="tac-logo"><div><small class="tac-date">${clean(t.date)} · ${clean(t.time)}</small><h3>${clean(t.artist)}</h3><span class="tac-status">${clean(t.status || "TAKEOVER").toUpperCase()}</span></div></div><p class="tac-bio">${clean(t.bio)}</p>${tracklistHtml}`;
            tag.append(art);
          });
        }
      }
    } catch {}
  }

  // Periodic Tasks (Polite intervals)
  poll();
  pollSchedule();
  loadSiteContent();
  setInterval(() => {
    if (!document.hidden || desiredPlay) poll();
  }, 10000);
  setInterval(() => {
    if (!document.hidden) pollSchedule();
  }, 60000);
  setInterval(() => {
    updateClock();
    updateSleep();
  }, 1000);

  // Network & Lifecycle handlers
  window.addEventListener("online", () => {
    poll("online", true);
    if (desiredPlay && audio.paused) connectAudio();
  });

  // Keep the site shell and dedicated Green Room updatable. updateViaCache:none
  // prevents an old browser HTTP cache entry from pinning a broken worker.
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('/sw.js', { scope: '/', updateViaCache: 'none' })
        .then(registration => registration.update().catch(() => {}))
        .catch(error => console.warn('[AT140] service worker registration failed', error));
    }, { once: true });
  }
})();
