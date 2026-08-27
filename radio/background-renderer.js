(() => {
  "use strict";

  const video = document.getElementById("backgroundVideo");
  const canvas = document.getElementById("backgroundCanvas");
  if (!video || !canvas) return;

  const context = canvas.getContext("2d", { alpha: false, desynchronized: true });
  if (!context) return;

  let running = true;
  let fallbackFrame = 0;

  function resize() {
    const scale = Math.min(devicePixelRatio || 1, 1.5);
    const width = Math.max(1, Math.round(innerWidth * scale));
    const height = Math.max(1, Math.round(innerHeight * scale));
    if (canvas.width !== width || canvas.height !== height) {
      canvas.width = width;
      canvas.height = height;
    }
  }

  function draw() {
    if (!running || video.readyState < HTMLMediaElement.HAVE_CURRENT_DATA) return;
    resize();
    const sourceWidth = video.videoWidth || 16;
    const sourceHeight = video.videoHeight || 9;
    const scale = Math.max(canvas.width / sourceWidth, canvas.height / sourceHeight);
    const width = sourceWidth * scale;
    const height = sourceHeight * scale;
    context.drawImage(video, (canvas.width - width) / 2, (canvas.height - height) / 2, width, height);
    document.body.classList.add("canvas-background-ready");
  }

  function frameCallback() {
    draw();
    if (running) video.requestVideoFrameCallback(frameCallback);
  }

  function fallbackLoop() {
    draw();
    fallbackFrame = requestAnimationFrame(fallbackLoop);
  }

  function ensurePlayback() {
    if (document.hidden || document.body.classList.contains("reduced-motion")) return;
    video.muted = true;
    video.defaultMuted = true;
    video.play().catch(() => {});
  }

  resize();
  if ("requestVideoFrameCallback" in HTMLVideoElement.prototype) {
    video.requestVideoFrameCallback(frameCallback);
  } else {
    fallbackLoop();
  }
  video.addEventListener("loadeddata", draw);
  video.addEventListener("playing", draw);
  video.addEventListener("error", () => document.body.classList.remove("canvas-background-ready"));
  addEventListener("resize", resize, { passive: true });
  addEventListener("pointerdown", ensurePlayback, { once: true });
  document.addEventListener("visibilitychange", () => {
    running = !document.hidden;
    if (running) {
      ensurePlayback();
      if ("requestVideoFrameCallback" in HTMLVideoElement.prototype) video.requestVideoFrameCallback(frameCallback);
      else if (!fallbackFrame) fallbackLoop();
    } else if (fallbackFrame) {
      cancelAnimationFrame(fallbackFrame);
      fallbackFrame = 0;
    }
  });
  ensurePlayback();
})();
