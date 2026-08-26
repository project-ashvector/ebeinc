(() => {
  "use strict";
  const path = location.pathname.replace(/\/index\.html$/, "/").replace(/\/+$/, "/") || "/";
  const pages = {
    "/": { title: "ALLTHINGS140 Radio // Live Transmission", keep: ["listen", "homeRouteGrid", "schedule"] },
    "/submit-audio/": { title: "Submit Audio // ALLTHINGS140 Radio", keep: ["submit"], label: "ARTIST UPLINK" },
    "/takeovers/": { title: "Takeovers // ALLTHINGS140 Radio", keep: ["about", "archive"], label: "TAKE CONTROL OF 140" },
    "/community/": { title: "Community // ALLTHINGS140 Radio", keep: ["sponsors", "discord"], label: "UNDERGROUND NETWORK" },
  };
  const page = pages[path] || pages["/"];
  document.title = page.title;
  document.body.dataset.route = path;
  const keep = new Set(page.keep);
  document.querySelectorAll("main > section, main > nav.home-route-grid").forEach(section => {
    if (!keep.has(section.id)) section.remove();
  });
  if (path === "/") document.querySelector(".subgrid")?.remove();
  if (path !== "/") {
    const player = document.querySelector("#miniPlayer");
    if (player) player.hidden = false;
    document.body.classList.add("mini-visible");
    document.documentElement.style.setProperty("--persistent-player-height", innerWidth <= 680 ? "56px" : "62px");
  }
  document.querySelectorAll("[data-route]").forEach(link => {
    const active = link.dataset.route === path;
    link.classList.toggle("is-current", active);
    if (active) link.setAttribute("aria-current", "page"); else link.removeAttribute("aria-current");
  });
  if (path !== "/") {
    const main = document.querySelector("main");
    const intro = document.createElement("header");
    intro.className = "route-intro wrap";
    intro.innerHTML = `<p class="kicker">${page.label}</p><a href="/">← LIVE RADIO HOME</a>`;
    main?.prepend(intro);
  }
})();
