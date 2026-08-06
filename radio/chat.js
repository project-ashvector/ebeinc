(() => {
  "use strict";
  const ENDPOINT = "wss://chat.ebeinc.online/ws";
  const stateEl = document.querySelector("#chatState");
  const countEl = document.querySelector("#chatCount");
  const messagesEl = document.querySelector("#chatMessages");
  const nameForm = document.querySelector("#chatNameForm");
  const nameInput = document.querySelector("#chatName");
  const compose = document.querySelector("#chatCompose");
  const textInput = document.querySelector("#chatText");
  const feedback = document.querySelector("#chatFeedback");
  let socket;
  let joined = false;
  let reconnectDelay = 1000;
  let stopped = false;

  const savedName = localStorage.getItem("allthings140-chat-name");
  if (savedName) nameInput.value = savedName;

  function setState(label, state) {
    stateEl.dataset.state = state;
    stateEl.querySelector("b").textContent = label;
  }

  function notice(text) {
    const item = document.createElement("li");
    item.className = "chat-notice";
    item.textContent = text;
    messagesEl.append(item);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function addMessage(message) {
    if (!message || document.getElementById(`chat-${message.id}`)) return;
    const item = document.createElement("li");
    item.className = "chat-message";
    item.id = `chat-${message.id}`;
    const meta = document.createElement("div");
    const name = document.createElement("b");
    const time = document.createElement("time");
    const body = document.createElement("p");
    name.textContent = message.name;
    time.dateTime = new Date(message.ts).toISOString();
    time.textContent = new Date(message.ts).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
    body.textContent = message.text;
    meta.append(name, time);
    item.append(meta, body);
    messagesEl.append(item);
    while (messagesEl.children.length > 60) messagesEl.firstElementChild.remove();
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function sendJoin() {
    const name = nameInput.value.trim();
    if (!name || socket?.readyState !== WebSocket.OPEN) return;
    localStorage.setItem("allthings140-chat-name", name);
    socket.send(JSON.stringify({ type: "join", name }));
  }

  function connect() {
    setState("CONNECTING", "connecting");
    socket = new WebSocket(ENDPOINT);
    socket.addEventListener("open", () => {
      reconnectDelay = 1000;
      setState("ONLINE", "online");
      feedback.textContent = "";
      if (joined || nameInput.value.trim()) sendJoin();
    });
    socket.addEventListener("message", event => {
      let data;
      try { data = JSON.parse(event.data); } catch { return; }
      if (data.type === "history") {
        messagesEl.replaceChildren();
        data.messages.forEach(addMessage);
        if (!data.messages.length) notice("You’re early—the room is open.");
        countEl.textContent = String(data.count || 0);
        if (!nameInput.value) nameInput.value = data.name || "";
      } else if (data.type === "message") addMessage(data.message);
      else if (data.type === "presence") countEl.textContent = String(data.count || 0);
      else if (data.type === "joined") {
        joined = true;
        nameInput.value = data.name;
        localStorage.setItem("allthings140-chat-name", data.name);
        nameForm.hidden = true;
        compose.hidden = false;
        textInput.focus();
        feedback.textContent = `Chatting as ${data.name}`;
      } else if (data.type === "error") feedback.textContent = data.message;
    });
    socket.addEventListener("close", () => {
      setState("RECONNECTING", "connecting");
      countEl.textContent = "0";
      if (!stopped) setTimeout(connect, reconnectDelay);
      reconnectDelay = Math.min(reconnectDelay * 2, 15000);
    });
    socket.addEventListener("error", () => socket.close());
  }

  nameForm.addEventListener("submit", event => {
    event.preventDefault();
    if (socket?.readyState === WebSocket.OPEN) sendJoin();
    else feedback.textContent = "Chat is reconnecting—try again in a moment.";
  });
  compose.addEventListener("submit", event => {
    event.preventDefault();
    const text = textInput.value.trim();
    if (!text || socket?.readyState !== WebSocket.OPEN) return;
    socket.send(JSON.stringify({ type: "message", text }));
    textInput.value = "";
  });
  window.addEventListener("pagehide", () => { stopped = true; socket?.close(1000, "Page closed"); });
  connect();
})();
