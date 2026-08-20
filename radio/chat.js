(() => {
  "use strict";

  const ENDPOINT = "wss://chat.ebeinc.online/ws";
  const $ = s => document.querySelector(s);
  const drawer = $("#chat");
  const backdrop = $("#chatBackdrop");
  const stateEl = $("#chatState");
  const countEl = $("#chatCount");
  const launcherCount = $("#chatLauncherCount");
  const messagesEl = $("#chatMessages");
  const nameForm = $("#chatNameForm");
  const nameInput = $("#chatName");
  const colorInput = $("#chatColor");
  const compose = $("#chatCompose");
  const textInput = $("#chatText");
  const feedback = $("#chatFeedback");

  if (!drawer) return;

  let socket = null;
  let joined = false;
  let reconnectDelay = 1000;
  let reconnectTimer = null;
  let stopped = false;
  let isChatOpen = false;

  nameInput.value = localStorage.getItem("allthings140-chat-name") || "";
  colorInput.value = localStorage.getItem("allthings140-chat-color") || "purple";

  function openChat() {
    isChatOpen = true;
    drawer.classList.add("open");
    drawer.setAttribute("aria-hidden", "false");
    if (backdrop) backdrop.hidden = false;
    document.body.classList.add("chat-open");
    document.dispatchEvent(new CustomEvent("chat:drawerOpening"));
    ensureConnected();
    setTimeout(() => (joined ? textInput.focus() : nameInput.focus()), 200);
  }

  function closeChat() {
    isChatOpen = false;
    drawer.classList.remove("open");
    drawer.setAttribute("aria-hidden", "true");
    if (backdrop) backdrop.hidden = true;
    document.body.classList.remove("chat-open");
    document.dispatchEvent(new CustomEvent("chat:drawerClosed"));
  }

  document.querySelectorAll("[data-open-chat]").forEach(button =>
    button.addEventListener("click", openChat)
  );
  const closeBtn = $("#chatClose");
  if (closeBtn) closeBtn.onclick = closeChat;
  if (backdrop) backdrop.onclick = closeChat;
  document.addEventListener("keydown", event => {
    if (event.key === "Escape" && isChatOpen) closeChat();
  });

  function setState(label, state) {
    if (!stateEl) return;
    stateEl.dataset.state = state;
    const b = stateEl.querySelector("b");
    if (b) b.textContent = label;
  }

  function notice(text, kind = "") {
    if (!messagesEl) return;
    const item = document.createElement("li");
    item.className = "chat-notice " + kind;
    item.textContent = text;
    messagesEl.append(item);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function command(type, extra = {}) {
    if (socket?.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ type, ...extra }));
    }
  }

  function addMessage(msg) {
    if (!msg || !messagesEl) return;
    const msgId = msg.id || `${Date.now()}-${Math.random()}`;
    if (document.getElementById(`chat-${msgId}`)) return;

    const item = document.createElement("li");
    item.className = "chat-message" + (msg.verified ? " verified" : "");
    item.id = `chat-${msgId}`;

    const avatar = document.createElement("i");
    avatar.className = `avatar ${msg.color || "purple"}`;
    avatar.textContent = String(msg.name || "?").slice(0, 1).toUpperCase();

    const content = document.createElement("section");
    const header = document.createElement("div");
    const name = document.createElement("b");
    const time = document.createElement("time");
    const body = document.createElement("p");

    name.textContent = msg.name + (msg.verified ? " ✓" : "");
    const date = msg.ts ? new Date(msg.ts) : new Date();
    time.textContent = date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
    body.textContent = msg.text || "";

    header.append(name, time);
    content.append(header, body);
    item.append(avatar, content);

    messagesEl.append(item);
    while (messagesEl.children.length > 60) messagesEl.firstElementChild.remove();
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function sendJoin() {
    const name = nameInput.value.trim();
    if (!name || socket?.readyState !== WebSocket.OPEN) return;
    localStorage.setItem("allthings140-chat-name", name);
    localStorage.setItem("allthings140-chat-color", colorInput.value);
    command("join", { name, color: colorInput.value });
  }

  function ensureConnected() {
    if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) {
      return;
    }
    connect();
  }

  function connect() {
    if (stopped) return;
    setState("CONNECTING", "connecting");
    try {
      socket = new WebSocket(ENDPOINT);
    } catch {
      setState("OFFLINE", "offline");
      return;
    }

    socket.addEventListener("open", () => {
      reconnectDelay = 1000;
      setState("ONLINE", "online");
      if (feedback) feedback.textContent = "";
      if (nameInput.value.trim()) sendJoin();
    });

    socket.addEventListener("message", event => {
      let data;
      try {
        data = JSON.parse(event.data);
      } catch {
        return;
      }

      if (data.type === "reactions") {
        updateReactionCounts(data.reactions);
      } else if (data.type === "history") {
        if (messagesEl) messagesEl.replaceChildren();
        (data.messages || []).forEach(addMessage);
        if (countEl) countEl.textContent = String(data.count || 0);
        if (launcherCount) launcherCount.textContent = String(data.count || 0);
      } else if (data.type === "message") {
        addMessage(data.message);
      } else if (data.type === "presence") {
        if (countEl) countEl.textContent = String(data.count || 0);
        if (launcherCount) launcherCount.textContent = String(data.count || 0);
      } else if (data.type === "joined") {
        joined = true;
        nameForm.hidden = true;
        compose.hidden = false;
        if (feedback) feedback.textContent = `Chatting as ${data.name}`;
      } else if (data.type === "cleared") {
        if (messagesEl) {
          messagesEl.replaceChildren();
          notice("Chat was cleared by a moderator.");
        }
      }
    });

    socket.addEventListener("close", () => {
      setState("RECONNECTING", "connecting");
      if (countEl) countEl.textContent = "0";
      if (!stopped && isChatOpen) {
        clearTimeout(reconnectTimer);
        reconnectTimer = setTimeout(connect, reconnectDelay);
        reconnectDelay = Math.min(reconnectDelay * 2, 15000);
      }
    });

    socket.addEventListener("error", () => {
      if (socket) socket.close();
    });
  }

  function updateReactionCounts(counts = {}) {
    if (counts.fire !== undefined) $("#reactFire").textContent = String(counts.fire || 0);
    if (counts.skull !== undefined) $("#reactSkull").textContent = String(counts.skull || 0);
    if (counts.vortex !== undefined) $("#reactVortex").textContent = String(counts.vortex || 0);
  }

  nameForm.addEventListener("submit", event => {
    event.preventDefault();
    ensureConnected();
    sendJoin();
  });

  compose.addEventListener("submit", event => {
    event.preventDefault();
    const text = textInput.value.trim();
    if (!text) return;
    command("message", { text });
    textInput.value = "";
  });

  // Track reactions click
  document.querySelectorAll("[data-reaction]").forEach(button => {
    button.addEventListener("click", () => {
      ensureConnected();
      const reaction = button.dataset.reaction;
      button.classList.toggle("selected");
      command("react", { reaction });
    });
  });

  window.addEventListener("pagehide", () => {
    stopped = true;
    socket?.close(1000, "Page closed");
  });
})();
