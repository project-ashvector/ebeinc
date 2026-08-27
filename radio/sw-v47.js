const CACHE = "allthings140-radio-v68";
const SHELL = [
  "./",
  "index.html",
  "styles.css?v=2.1.3",
  "support.css?v=1.1.0",
  "app.js?v=2.0.3",
  "support.js?v=1.1.0",
  "persistent-shell.html",
  "persistent-shell.css?v=2.0.0",
  "persistent-shell.js?v=1.0.0",
  "vendor-supabase-2.112.3.min.js",
  "supabase-config.js?v=1.0.0",
  "persistent-auth.js?v=1.0.0",
  "persistent-route.js?v=1.0.0",
  "persistent-audio-adapter.js?v=1.0.0",
  "manifest.webmanifest",
  "assets/allthings140-logo-64.png",
  "assets/allthings140-logo-192.webp",
  "assets/allthings140-logo-512.png",
  "assets/main-vis-home-v1-poster.webp?v=1.0.0",
  "room/index.html",
  "room/stage.css?v=2.5.0",
  "room/overlay.css?v=2.4.0",
  "room/config.js?v=2.2.0",
  "room/stage.js?v=2.5.0",
  "room/chat-bridge.js?v=1.0.0"
];

self.addEventListener("install", event => {
  event.waitUntil(
    caches.open(CACHE)
      .then(cache => cache.addAll(SHELL))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(key => key !== CACHE).map(key => caches.delete(key))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", event => {
  const request = event.request;
  const url = new URL(request.url);

  if (request.method !== "GET" || url.origin !== location.origin) return;

  // Never cache live/dynamic media or APIs.
  if (
    /\.(?:mp4|webm|mp3|m3u8|ts)$/i.test(url.pathname) ||
    url.pathname.startsWith("/api/") ||
    url.pathname.startsWith("/obs/")
  ) return;

  if (request.mode === "navigate") {
    // Navigation is network-first and cached by its own URL. Never overwrite
    // the homepage cache with /room/, /visuals/, or another document.
    event.respondWith(
      fetch(request)
        .then(response => {
          if (response.ok) {
            const copy = response.clone();
            caches.open(CACHE).then(cache => cache.put(request, copy));
          }
          return response;
        })
        .catch(async () => {
          const exact = await caches.match(request);
          if (exact) return exact;
          if (url.pathname === "/" || url.pathname.endsWith("/index.html")) {
            const home = await caches.match("./");
            if (home) return home;
          }
          return Response.error();
        })
    );
    return;
  }

  const networkFirst =
    url.pathname.endsWith("/styles.css") ||
    url.pathname.endsWith("/support.css") ||
    url.pathname.endsWith("/app.js") ||
    url.pathname.endsWith("/route-layout.js") ||
    url.pathname.endsWith("/persistent-shell.js") ||
    url.pathname.endsWith("/persistent-auth.js") ||
    url.pathname.endsWith("/supabase-config.js") ||
    url.pathname.endsWith("/persistent-route.js") ||
    url.pathname.endsWith("/persistent-audio-adapter.js") ||
    url.pathname.endsWith("/sw-v47.js") ||
    url.pathname.endsWith("/sw.js") ||
    url.pathname.includes("/room/stage.js") ||
    url.pathname.includes("/room/config.js") ||
    url.pathname.includes("/room/stage.css") ||
    url.pathname.includes("/room/overlay.css") ||
    url.pathname.includes("/room/chat-bridge.js");

  if (networkFirst) {
    event.respondWith(
      fetch(request)
        .then(response => {
          if (response.ok) caches.open(CACHE).then(cache => cache.put(request, response.clone()));
          return response;
        })
        .catch(() => caches.match(request))
    );
    return;
  }

  event.respondWith(
    caches.match(request).then(cached => cached || fetch(request).then(response => {
      if (response.ok) caches.open(CACHE).then(cache => cache.put(request, response.clone()));
      return response;
    }))
  );
});
