(() => {
  "use strict";
  if (window.top === window || !window.top.AT140Radio) return;
  const localAudio = document.querySelector("audio");
  if (!localAudio) return;
  const authority = window.top.AT140Radio.client(window);
  for (const property of ["paused", "ended", "error", "readyState", "networkState", "currentTime", "duration", "src", "volume", "muted"]) {
    const descriptor = {
      configurable: true,
      get: () => authority[property],
    };
    if (["currentTime", "src", "volume", "muted"].includes(property)) descriptor.set = (value) => { authority[property] = value; };
    Object.defineProperty(localAudio, property, descriptor);
  }
  localAudio.play = () => authority.play();
  localAudio.pause = () => authority.pause();
  localAudio.load = () => authority.load();
  localAudio.addEventListener = (...args) => authority.addEventListener(...args);
  localAudio.removeEventListener = (...args) => authority.removeEventListener(...args);
  document.addEventListener("DOMContentLoaded", () => {
    const button = document.getElementById("listen");
    if (button && !authority.paused) button.textContent = "❚❚ PAUSE LIVE";
  }, { once: true });
})();
