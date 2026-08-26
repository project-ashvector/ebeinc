(() => {
  "use strict";
  const query = new URLSearchParams(location.search);
  if (query.get("at140_route") === "1" || window.parent !== window) {
    // Route frames own timers, sockets, media decoders, and observers. Prevent
    // old frame documents from being retained in BFCache; the shell restores
    // routes authoritatively from its History API state instead.
    window.addEventListener("unload", () => {});
    document.addEventListener("click", (event) => {
      if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      const anchor = event.target.closest("a[href]");
      if (!anchor || anchor.target || anchor.hasAttribute("download") || anchor.dataset.noPersistentNav !== undefined) return;
      const url = new URL(anchor.href, location.href);
      const path = url.pathname.replace(/\/index\.html$/, "/");
      if (url.origin !== location.origin || !["/", "/submit-audio/", "/takeovers/", "/community/", "/visuals/", "/room/", "/roadmap/"].includes(path)) return;
      event.preventDefault();
      setTimeout(() => window.top.AT140Navigate?.(url.href), 0);
    }, true);
    const removeLocalAudio = () => document.querySelectorAll("audio").forEach((node) => node.remove());
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", removeLocalAudio, { once: true });
    else removeLocalAudio();
    return;
  }
  if (sessionStorage.getItem("at140_shell_bypass") === "1") {
    sessionStorage.removeItem("at140_shell_bypass");
    return;
  }
  const route = new URL(location.href);
  route.searchParams.delete("at140_route");
  const shell = new URL("/persistent-shell.html", location.origin);
  shell.searchParams.set("route", route.pathname + route.search + route.hash);
  location.replace(shell.href);
})();
