(() => {
  "use strict";

  const STATUS_URLS = [
    "https://status.ebeinc.online/api/public/status",
    "https://status.ebeinc.online/public/status.json",
    "https://stream.ebeinc.online/api/public/status",
    "https://stream.ebeinc.online/public/status.json",
  ];

  const STREAM_URLS = [
    "https://stream.ebeinc.online/hls/live.m3u8",
    "https://stream.ebeinc.online/live.mp3",
  ];

  const VISUAL_PARTS = [
    "assets/visuals/micro/chunk-00.txt",
    "assets/visuals/micro/chunk-01.txt",
  ];

  const audio = document.querySelector("#audio");
  const playButton = document.querySelector("#play");
  const heroPlayButton = document.querySelector("#heroPlay");
  const volume = document.querySelector("#volume");
  const message = document.querySelector("#message");
  const mode = document.querySelector("#mode");
  const headerStatus = document.querySelector("#headerStatus");
  const title = document.querySelector("#trackTitle");
  const artist = document.querySelector("#trackArtist");
  const listeners = document.querySelector("#listeners");
  const timeline = document.querySelector("#timeline");
  const elapsed = document.querySelector("#elapsed");
  const duration = document.querySelector("#duration");
  const nextTrack = document.querySelector("#nextTrack");
  const footer = document.querySelector("#footerStatus");
  const share = document.querySelector("#share");
  const visualVideo = document.querySelector("#visualVideo");
  const visualMode = document.querySelector("#visualMode");

  let latestStatus = null;
  let hlsPlayer = null;
  let desiredPlayback = false;
  let streamReady = false;
  let streamIndex = 0;
  let hlsNetworkErrors = 0;

  function formatTime(value) {
    const seconds = Math.max(0, Math.floor(Number(value) || 0));
    return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
  }

  function cleanText(value) {
    return String(value ?? "")
      .replace(/â€”/g, "—")
      .replace(/â€“/g, "–")
      .replace(/â€™|â€˜/g, "'")
      .replace(/â€œ|â€/g, '"')
      .replace(/Â/g, " ")
      .replace(/\s+/g, " ")
      .trim();
  }

  function setPlaying(isPlaying) {
    document.body.classList.toggle("playing", isPlaying);
    playButton.textContent = isPlaying ? "Ⅱ" : "▶";
    heroPlayButton.textContent = isPlaying ? "Ⅱ PAUSE FEED" : "▶ CONNECT TO FEED";
  }

  function setMode(label, state) {
    mode.dataset.state = state;
    headerStatus.dataset.state = state;
    mode.innerHTML = `<i></i>${label}`;
    headerStatus.innerHTML = `<i></i>${label}`;
    if (visualMode) {
      visualMode.textContent = state === "live" ? "LIVE DJ VISUAL LOOP" : "CATALOG VISUALIZER";
    }
  }

  function setMessage(text, state = "") {
    message.textContent = text;
    message.className = `message ${state}`;
  }

  function showAudioOnlyOnline() {
    if (latestStatus) return;
    setMode("24/7 FEED", "autodj");
    listeners.textContent = "—";
    title.textContent = "AllThings140Radio 24/7 Catalog";
    artist.textContent = "Live server transmission";
    nextTrack.textContent = "Now-playing data reconnecting";
    elapsed.textContent = "LIVE";
    duration.textContent = "24/7";
    timeline.style.width = "100%";
    footer.textContent = "SYSTEM STATUS: AUDIO ONLINE // METADATA RECONNECTING";
    setMessage("Audio feed is available. Track titles will return automatically when the status relay reconnects.", "good");
  }

  async function loadVisualLoop() {
    if (!visualVideo) return;
    try {
      const responses = await Promise.all(
        VISUAL_PARTS.map((path) => fetch(path, { cache: "force-cache" }))
      );
      if (responses.some((response) => !response.ok)) throw new Error("visual asset missing");
      const parts = await Promise.all(responses.map((response) => response.text()));
      const binaryText = window.atob(parts.map((part) => part.trim()).join(""));
      const bytes = new Uint8Array(binaryText.length);
      for (let index = 0; index < binaryText.length; index += 1) {
        bytes[index] = binaryText.charCodeAt(index);
      }
      visualVideo.src = URL.createObjectURL(new Blob([bytes], { type: "video/mp4" }));
      visualVideo.muted = true;
      visualVideo.loop = true;
      visualVideo.playsInline = true;
      await visualVideo.play();
    } catch (_error) {
      visualVideo.removeAttribute("src");
    }
  }

  function updateClock() {
    if (!latestStatus) return;
    const total = Number(latestStatus.duration_seconds) || 0;
    const startingPosition = Number(latestStatus.position_seconds) || 0;
    const fetchedAt = Number(latestStatus._fetched) || Date.now() / 1000;
    const position = Math.min(total || Infinity, startingPosition + (Date.now() / 1000 - fetchedAt));
    elapsed.textContent = formatTime(position);
    duration.textContent = formatTime(total);
    timeline.style.width = `${total ? Math.min(100, (position / total) * 100) : 0}%`;
  }

  function attachStream(url, index = 0) {
    if (!url) return;
    if (audio.dataset.src === url && (hlsPlayer || audio.src)) return;

    streamIndex = index;
    const resume = desiredPlayback || !audio.paused;
    audio.dataset.src = url;
    streamReady = false;

    if (hlsPlayer) {
      hlsPlayer.destroy();
      hlsPlayer = null;
    }

    audio.removeAttribute("src");
    audio.load();

    if (url.includes(".m3u8") && window.Hls && Hls.isSupported()) {
      hlsNetworkErrors = 0;
      hlsPlayer = new Hls({
        liveSyncDurationCount: 3,
        liveMaxLatencyDurationCount: 8,
        maxLiveSyncPlaybackRate: 1.25,
        enableWorker: true,
      });
      hlsPlayer.loadSource(url);
      hlsPlayer.attachMedia(audio);
      hlsPlayer.on(Hls.Events.MANIFEST_PARSED, () => {
        streamReady = true;
        showAudioOnlyOnline();
        if (resume) audio.play().catch(() => setPlaying(false));
      });
      hlsPlayer.on(Hls.Events.ERROR, (_event, data) => {
        if (!data.fatal) return;
        if (data.type === Hls.ErrorTypes.NETWORK_ERROR && hlsNetworkErrors < 3) {
          hlsNetworkErrors += 1;
          hlsPlayer.startLoad();
          return;
        }
        if (data.type === Hls.ErrorTypes.MEDIA_ERROR) {
          hlsPlayer.recoverMediaError();
          return;
        }
        hlsPlayer.destroy();
        hlsPlayer = null;
        if (STREAM_URLS[streamIndex + 1]) {
          attachStream(STREAM_URLS[streamIndex + 1], streamIndex + 1);
        } else {
          streamReady = false;
          setPlaying(false);
          setMode("OFFLINE", "offline");
          setMessage("The public audio feed could not be reached.", "bad");
        }
      });
      return;
    }

    audio.src = url;
    audio.addEventListener("canplay", () => {
      streamReady = true;
      showAudioOnlyOnline();
    }, { once: true });
    if (resume) audio.play().catch(() => setPlaying(false));
  }

  function applyStatus(status) {
    latestStatus = { ...status, _fetched: Date.now() / 1000 };
    listeners.textContent = String(status.listeners || 0);
    title.textContent = cleanText(status.current_title || "AllThings140Radio Rotation");
    artist.textContent = cleanText(
      status.current_artist || (status.mode === "live" ? "Live host transmission" : "Ebmarah catalog")
    );
    nextTrack.textContent = cleanText(
      [status.next_artist, status.next_title].filter(Boolean).join(" — ") || "—"
    );

    const suppliedStream = status.hls_url || status.stream_url;
    if (suppliedStream && suppliedStream !== audio.dataset.src) {
      attachStream(suppliedStream, 0);
    }

    const isLive = status.mode === "live";
    setMode(isLive ? "LIVE DJ" : "24/7 CATALOG", isLive ? "live" : "autodj");
    footer.textContent = `SYSTEM STATUS: ${isLive ? "LIVE DJ" : "CATALOG AUTO DJ"} // ${status.listeners || 0} CONNECTED // SERVER v${status.version || status.gateway_version || ""}`;
    setMessage("Station uplink established. Press play to join the shared transmission.", "good");
    updateClock();
  }

  async function fetchStatus(endpoint) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 3500);
    try {
      const response = await fetch(`${endpoint}?t=${Date.now()}`, {
        cache: "no-store",
        signal: controller.signal,
      });
      if (!response.ok) throw new Error("status unavailable");
      const status = await response.json();
      if (!status.online) throw new Error("station offline");
      return status;
    } finally {
      clearTimeout(timeout);
    }
  }

  async function pollStatus() {
    for (const endpoint of STATUS_URLS) {
      try {
        const status = await fetchStatus(endpoint);
        applyStatus(status);
        return;
      } catch (_error) {
        // Try the next public status route.
      }
    }

    latestStatus = null;
    if (streamReady || audio.dataset.src) {
      showAudioOnlyOnline();
    } else {
      setMode("CONNECTING", "offline");
      title.textContent = "Connecting to the 24/7 feed";
      artist.textContent = "AllThings140Radio";
      nextTrack.textContent = "—";
      setMessage("The audio player is connecting directly while the metadata relay retries.", "");
    }
  }

  async function togglePlayback() {
    if (!audio.dataset.src) {
      attachStream(STREAM_URLS[0], 0);
    }

    if (audio.paused) {
      desiredPlayback = true;
      try {
        setMessage("Opening synchronized transmission…");
        await audio.play();
        setPlaying(true);
        setMessage("Connected to the live feed.", "good");
      } catch (_error) {
        setPlaying(false);
        setMessage("The live feed is loading. Press play again in a moment.", "bad");
      }
    } else {
      desiredPlayback = false;
      audio.pause();
      setPlaying(false);
    }
  }

  playButton.addEventListener("click", togglePlayback);
  heroPlayButton.addEventListener("click", togglePlayback);
  volume.addEventListener("input", () => {
    audio.volume = Number(volume.value);
  });
  audio.volume = Number(volume.value);
  audio.addEventListener("playing", () => {
    streamReady = true;
    setPlaying(true);
    showAudioOnlyOnline();
  });
  audio.addEventListener("pause", () => setPlaying(false));
  audio.addEventListener("error", () => {
    setPlaying(false);
    if (STREAM_URLS[streamIndex + 1]) {
      attachStream(STREAM_URLS[streamIndex + 1], streamIndex + 1);
    } else {
      setMessage("Stream interrupted. Retrying automatically…", "bad");
    }
  });
  share.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(location.href);
      setMessage("Station link copied.", "good");
    } catch (_error) {
      window.prompt("Copy station link", location.href);
    }
  });

  loadVisualLoop();
  attachStream(STREAM_URLS[0], 0);
  pollStatus();
  setInterval(pollStatus, 5000);
  setInterval(updateClock, 500);
})();
