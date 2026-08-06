(() => {
  "use strict";

  const FUNNEL = "https://ebmarah-laptop-ai.tail9b0b89.ts.net";
  const STREAMS = [`${FUNNEL}/live.mp3`, "https://stream.ebeinc.online/live.mp3"];
  const STATUSES = [
    `${FUNNEL}/api/public/status`,
    `${FUNNEL}/public/status.json`,
    "https://status.ebeinc.online/api/public/status",
    "https://stream.ebeinc.online/api/public/status",
  ];
  const VISUAL_PARTS = ["assets/visuals/micro/chunk-00.txt", "assets/visuals/micro/chunk-01.txt"];

  const $ = (selector) => document.querySelector(selector);
  const audio = $("#audio");
  const play = $("#play");
  const heroPlay = $("#heroPlay");
  const volume = $("#volume");
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
  const share = $("#share");
  const video = $("#visualVideo");
  const visualMode = $("#visualMode");

  let status = null;
  let streamIndex = 0;
  let streamReady = false;
  let wantsPlayback = false;
  let attempt = 0;

  const clean = (value) => String(value ?? "")
    .replace(/â€”/g, "—").replace(/â€“/g, "–")
    .replace(/â€™|â€˜/g, "'").replace(/â€œ|â€/g, '"')
    .replace(/Â/g, " ").replace(/\s+/g, " ").trim();

  const formatTime = (value) => {
    const seconds = Math.max(0, Math.floor(Number(value) || 0));
    return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
  };

  function setPlaying(value) {
    document.body.classList.toggle("playing", value);
    play.textContent = value ? "Ⅱ" : "▶";
    heroPlay.textContent = value ? "Ⅱ PAUSE FEED" : "▶ CONNECT TO FEED";
  }

  function setMode(label, state) {
    mode.dataset.state = state;
    header.dataset.state = state;
    mode.innerHTML = `<i></i>${label}`;
    header.innerHTML = `<i></i>${label}`;
    if (visualMode) visualMode.textContent = state === "live" ? "LIVE DJ VISUAL LOOP" : "CATALOG VISUALIZER";
  }

  function setMessage(text, state = "") {
    message.textContent = text;
    message.className = `message ${state}`;
  }

  function showConnecting() {
    if (status) return;
    setMode("CONNECTING", "offline");
    listeners.textContent = "—";
    title.textContent = "Connecting to the 24/7 feed";
    artist.textContent = "AllThings140Radio";
    next.textContent = "Now-playing data reconnecting";
    elapsed.textContent = "LIVE";
    duration.textContent = "24/7";
    timeline.style.width = "0%";
    footer.textContent = "SYSTEM STATUS: CONNECTING TO PUBLIC AUDIO";
  }

  function showReady() {
    if (status) return;
    setMode("FEED READY", "autodj");
    title.textContent = "AllThings140Radio 24/7 Catalog";
    artist.textContent = "Press play to join the live server transmission";
    next.textContent = "Now-playing data reconnecting";
    elapsed.textContent = "LIVE";
    duration.textContent = "24/7";
    timeline.style.width = "100%";
    footer.textContent = "SYSTEM STATUS: AUDIO READY // METADATA RECONNECTING";
    setMessage("The public stream is ready. Press play to listen.", "good");
  }

  function showPlaying() {
    if (!status) {
      setMode("24/7 FEED", "autodj");
      title.textContent = "AllThings140Radio 24/7 Catalog";
      artist.textContent = "Live server transmission";
      footer.textContent = "SYSTEM STATUS: PUBLIC AUDIO PLAYING // METADATA RECONNECTING";
    }
    setMessage("Connected to the live feed.", "good");
  }

  async function loadVisual() {
    if (!video) return;
    try {
      const responses = await Promise.all(VISUAL_PARTS.map((path) => fetch(path, { cache: "force-cache" })));
      if (responses.some((response) => !response.ok)) throw new Error();
      const parts = await Promise.all(responses.map((response) => response.text()));
      const binary = atob(parts.map((part) => part.trim()).join(""));
      const bytes = new Uint8Array(binary.length);
      for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
      video.src = URL.createObjectURL(new Blob([bytes], { type: "video/mp4" }));
      video.muted = true;
      video.loop = true;
      video.playsInline = true;
      await video.play();
    } catch (_error) {
      video.removeAttribute("src");
    }
  }

  function loadStream(index = 0) {
    const url = STREAMS[index];
    if (!url) return false;
    streamIndex = index;
    streamReady = false;
    audio.pause();
    audio.removeAttribute("src");
    audio.dataset.src = url;
    audio.src = url;
    audio.load();
    showConnecting();
    setMessage("Contacting the public MP3 stream…");
    return true;
  }

  function beginPlayback() {
    const id = ++attempt;
    if (!audio.dataset.src) loadStream(0);
    wantsPlayback = true;
    setMessage("Opening synchronized transmission…");
    audio.play().catch(() => {});

    window.setTimeout(() => {
      if (id !== attempt || !wantsPlayback || !audio.paused) return;
      if (STREAMS[streamIndex + 1]) {
        setMessage("Primary stream did not start. Trying the backup route…", "bad");
        loadStream(streamIndex + 1);
        window.setTimeout(() => audio.play().catch(() => {}), 300);
      } else {
        setMode("AUDIO ERROR", "offline");
        setMessage("The address loaded, but no MP3 audio arrived. Run Fix Public Audio in the Server app.", "bad");
      }
    }, 8000);
  }

  function togglePlayback() {
    if (!audio.paused) {
      wantsPlayback = false;
      attempt += 1;
      audio.pause();
      setPlaying(false);
      setMessage("Feed paused.");
      return;
    }
    beginPlayback();
  }

  function applyStatus(value) {
    status = { ...value, _fetched: Date.now() / 1000 };
    listeners.textContent = String(value.listeners || 0);
    title.textContent = clean(value.current_title || "AllThings140Radio Rotation");
    artist.textContent = clean(value.current_artist || (value.mode === "live" ? "Live host transmission" : "Ebmarah catalog"));
    next.textContent = clean([value.next_artist, value.next_title].filter(Boolean).join(" — ") || "—");
    const live = value.mode === "live";
    setMode(live ? "LIVE DJ" : "24/7 CATALOG", live ? "live" : "autodj");
    footer.textContent = `SYSTEM STATUS: ${live ? "LIVE DJ" : "CATALOG AUTO DJ"} // ${value.listeners || 0} CONNECTED // SERVER v${value.version || ""}`;
    if (audio.paused) setMessage(streamReady ? "The public stream is ready. Press play to listen." : "Connecting to the public audio stream…", streamReady ? "good" : "");
    updateClock();
  }

  function updateClock() {
    if (!status) return;
    const total = Number(status.duration_seconds) || 0;
    const start = Number(status.position_seconds) || 0;
    const fetched = Number(status._fetched) || Date.now() / 1000;
    const position = Math.min(total || Infinity, start + (Date.now() / 1000 - fetched));
    elapsed.textContent = formatTime(position);
    duration.textContent = formatTime(total);
    timeline.style.width = `${total ? Math.min(100, position / total * 100) : 0}%`;
  }

  async function pollStatus() {
    for (const endpoint of STATUSES) {
      const controller = new AbortController();
      const timeout = window.setTimeout(() => controller.abort(), 3500);
      try {
        const response = await fetch(`${endpoint}?t=${Date.now()}`, { cache: "no-store", signal: controller.signal });
        if (!response.ok) throw new Error();
        const value = await response.json();
        if (!value.online) throw new Error();
        window.clearTimeout(timeout);
        applyStatus(value);
        return;
      } catch (_error) {
        window.clearTimeout(timeout);
      }
    }
    status = null;
    if (!audio.paused) showPlaying();
    else if (streamReady) showReady();
    else showConnecting();
  }

  play.addEventListener("click", togglePlayback);
  heroPlay.addEventListener("click", togglePlayback);
  volume.addEventListener("input", () => { audio.volume = Number(volume.value); });
  audio.volume = Number(volume.value);
  audio.addEventListener("canplay", () => { streamReady = true; if (audio.paused) showReady(); });
  audio.addEventListener("playing", () => { streamReady = true; setPlaying(true); showPlaying(); });
  audio.addEventListener("pause", () => setPlaying(false));
  audio.addEventListener("error", () => {
    streamReady = false;
    setPlaying(false);
    if (wantsPlayback && STREAMS[streamIndex + 1]) {
      loadStream(streamIndex + 1);
      window.setTimeout(() => audio.play().catch(() => {}), 300);
    } else {
      setMode("AUDIO ERROR", "offline");
      setMessage("The stream address responded without playable MP3 audio. Run Fix Public Audio in the Server app.", "bad");
    }
  });
  share.addEventListener("click", async () => {
    try { await navigator.clipboard.writeText(location.href); setMessage("Station link copied.", "good"); }
    catch (_error) { window.prompt("Copy station link", location.href); }
  });

  loadVisual();
  loadStream(0);
  pollStatus();
  window.setInterval(pollStatus, 5000);
  window.setInterval(updateClock, 500);
})();
