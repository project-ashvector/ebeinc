(() => {
  "use strict";

  const SERVER = "https://stream.ebeinc.online";
  const STATUS_URL = `${SERVER}/api/public/status`;
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
  let shouldBePlaying = false;

  function formatTime(value) {
    const seconds = Math.max(0, Math.floor(Number(value) || 0));
    return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
  }

  function cleanText(value) {
    return String(value ?? "")
      .replace(/â€”/g, "—")
      .replace(/â€“/g, "–")
      .replace(/â€™|â€˜/g, "'")
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

  async function loadVisualLoop() {
    if (!visualVideo) return;

    try {
      const responses = await Promise.all(
        VISUAL_PARTS.map((path) => fetch(path, { cache: "force-cache" }))
      );
      if (responses.some((response) => !response.ok)) throw new Error("visual asset missing");

      const parts = await Promise.all(responses.map((response) => response.text()));
      const encodedVideo = parts.map((part) => part.trim()).join("");
      const binaryText = window.atob(encodedVideo);
      const bytes = new Uint8Array(binaryText.length);
      for (let index = 0; index < binaryText.length; index += 1) {
        bytes[index] = binaryText.charCodeAt(index);
      }

      const videoBlob = new Blob([bytes], { type: "video/mp4" });
      visualVideo.src = URL.createObjectURL(videoBlob);
      visualVideo.muted = true;
      visualVideo.loop = true;
      visualVideo.playsInline = true;
      await visualVideo.play();
    } catch (error) {
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

  function attachStream(url) {
    if (!url || audio.dataset.src === url) return;
    const resume = shouldBePlaying || !audio.paused;
    audio.dataset.src = url;

    if (hlsPlayer) {
      hlsPlayer.destroy();
      hlsPlayer = null;
    }

    audio.removeAttribute("src");
    audio.load();

    if (url.includes(".m3u8") && window.Hls && Hls.isSupported()) {
      hlsPlayer = new Hls({
        liveSyncDurationCount: 3,
        liveMaxLatencyDurationCount: 8,
        maxLiveSyncPlaybackRate: 1.25,
        enableWorker: true,
      });
      hlsPlayer.loadSource(url);
      hlsPlayer.attachMedia(audio);
      hlsPlayer.on(Hls.Events.MANIFEST_PARSED, () => {
        if (resume) audio.play().catch(() => setPlaying(false));
      });
      hlsPlayer.on(Hls.Events.ERROR, (_event, data) => {
        if (!data.fatal) return;
        if (data.type === Hls.ErrorTypes.NETWORK_ERROR) hlsPlayer.startLoad();
        else if (data.type === Hls.ErrorTypes.MEDIA_ERROR) hlsPlayer.recoverMediaError();
        else {
          hlsPlayer.destroy();
          hlsPlayer = null;
          setPlaying(false);
          setMessage("Live feed interrupted. The player is reconnecting…", "bad");
        }
      });
    } else {
      audio.src = url;
      if (resume) audio.play().catch(() => setPlaying(false));
    }
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
    attachStream(status.hls_url || status.stream_url);
    setMode(status.mode === "live" ? "LIVE DJ" : "24/7 CATALOG", status.mode === "live" ? "live" : "autodj");
    footer.textContent = `SYSTEM STATUS: ${status.mode === "live" ? "LIVE DJ" : "CATALOG AUTO DJ"} // ${status.listeners || 0} CONNECTED // SERVER v${status.version || status.gateway_version || ""}`;
    setMessage("Station uplink established. Press play to join the shared transmission.", "good");
    updateClock();
  }

  function showOffline() {
    latestStatus = null;
    setMode("OFFLINE", "offline");
    listeners.textContent = "0";
    title.textContent = "Station uplink unavailable";
    artist.textContent = "Waiting for the public server connection";
    nextTrack.textContent = "—";
    timeline.style.width = "0";
    elapsed.textContent = "0:00";
    duration.textContent = "0:00";
    footer.textContent = "SYSTEM STATUS: PUBLIC STREAM NOT CONNECTED";
    setMessage("The website is online, but the radio relay is reconnecting.", "bad");
  }

  async function pollStatus() {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 5500);
    try {
      const response = await fetch(`${STATUS_URL}?t=${Date.now()}`, {
        cache: "no-store",
        signal: controller.signal,
      });
      if (!response.ok) throw new Error("status unavailable");
      const status = await response.json();
      if (!status.online) throw new Error("station offline");
      applyStatus(status);
    } catch (error) {
      showOffline();
    } finally {
      clearTimeout(timeout);
    }
  }

  async function togglePlayback() {
    if (!audio.dataset.src) {
      setMessage("The public feed is reconnecting. Try again in a few seconds.", "bad");
      return;
    }

    if (audio.paused) {
      shouldBePlaying = true;
      try {
        setMessage("Opening synchronized transmission…");
        await audio.play();
        setPlaying(true);
        setMessage("Connected to the live feed.", "good");
      } catch (error) {
        setPlaying(false);
        setMessage("The player is loading the live HLS feed. Press play again in a moment.", "bad");
      }
    } else {
      shouldBePlaying = false;
      audio.pause();
      setPlaying(false);
    }
  }

  playButton.addEventListener("click", togglePlayback);
  heroPlayButton.addEventListener("click", togglePlayback);
  volume.addEventListener("input", () => { audio.volume = Number(volume.value); });
  audio.volume = Number(volume.value);
  audio.addEventListener("playing", () => setPlaying(true));
  audio.addEventListener("pause", () => setPlaying(false));
  audio.addEventListener("error", () => {
    setPlaying(false);
    setMessage("Stream interrupted. Retrying automatically…", "bad");
  });
  share.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(location.href);
      setMessage("Station link copied.", "good");
    } catch (error) {
      window.prompt("Copy station link", location.href);
    }
  });

  loadVisualLoop();
  pollStatus();
  setInterval(pollStatus, 5000);
  setInterval(updateClock, 500);
})();
