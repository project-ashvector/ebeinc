/**
 * ALLTHINGS140 Green Room — moderated public chat bridge.
 *
 * Visual layout/presence/reactions stay on visuals-realtime. Listener messages
 * stay on the existing chat.ebeinc.online service so the Host dashboard,
 * moderation, history and the established public chat community keep working.
 */
(() => {
  'use strict';
  const C = window.AT140_GREEN_CONFIG || {};
  if (!C.chatUrl) return;

  const $ = s => document.querySelector(s);
  const list = $('#chat');
  const profileForm = $('#profile');
  const nameInput = $('#name');
  const avatarInput = $('#avatar');
  const messageForm = $('#message');
  const messageInput = $('#messageText');
  const status = $('#chatConnection');
  if (!list || !profileForm || !nameInput || !avatarInput || !messageForm || !messageInput) return;

  let socket = null;
  let reconnectTimer = null;
  let reconnectDelay = 1000;
  let stopped = false;
  let joined = false;

  const colorFromAvatar = avatar => ({
    'orb-purple': 'purple',
    'orb-cyan': 'cyan',
    'orb-pink': 'pink',
    'orb-green': 'green',
    'orb-fire': 'purple'
  })[avatar] || 'purple';

  function setStatus(text, state = '') {
    if (!status) return;
    status.textContent = text;
    status.dataset.state = state;
  }

  function send(type, extra = {}) {
    if (socket?.readyState === WebSocket.OPEN) socket.send(JSON.stringify({ type, ...extra }));
  }

  function sendJoin() {
    const name = nameInput.value.trim().slice(0, 24);
    if (!name || socket?.readyState !== WebSocket.OPEN) return;
    try {
      localStorage.setItem('allthings140-chat-name', name);
      localStorage.setItem('allthings140-chat-color', colorFromAvatar(avatarInput.value));
    } catch (_) {}
    send('join', { name, color: colorFromAvatar(avatarInput.value) });
  }

  function messageId(msg) {
    return `legacy-chat-${String(msg?.id || `${msg?.ts || Date.now()}-${msg?.name || 'listener'}`).replace(/[^a-zA-Z0-9_-]/g, '_')}`;
  }

  function addMessage(msg) {
    if (!msg || !msg.text) return;
    const id = messageId(msg);
    if (document.getElementById(id)) return;
    const li = document.createElement('li');
    li.id = id;
    li.dataset.messageId = msg.id || '';
    const b = document.createElement('b');
    b.textContent = `${msg.name || 'Listener'}${msg.verified ? ' ✓' : ''} `;
    const time = document.createElement('time');
    time.textContent = new Date(msg.ts || Date.now()).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
    const text = document.createElement('span');
    text.textContent = msg.text;
    li.append(b, time, document.createElement('br'), text);
    list.append(li);
    while (list.children.length > 60) list.firstElementChild?.remove();
    list.scrollTop = list.scrollHeight;
  }

  function showNotice(text) {
    const li = document.createElement('li');
    li.className = 'chat-notice';
    li.textContent = text;
    list.append(li);
    while (list.children.length > 60) list.firstElementChild?.remove();
    list.scrollTop = list.scrollHeight;
  }

  function connect() {
    if (stopped || socket?.readyState === WebSocket.CONNECTING || socket?.readyState === WebSocket.OPEN) return;
    setStatus('CHAT CONNECTING', 'connecting');
    try { socket = new WebSocket(C.chatUrl); }
    catch (_) { scheduleReconnect(); return; }

    socket.addEventListener('open', () => {
      reconnectDelay = 1000;
      setStatus('CHAT LIVE', 'online');
      sendJoin();
    });

    socket.addEventListener('message', event => {
      let data;
      try { data = JSON.parse(event.data); } catch (_) { return; }
      if (data.type === 'history') {
        list.replaceChildren();
        (data.messages || []).forEach(addMessage);
      } else if (data.type === 'message') {
        addMessage(data.message);
      } else if (data.type === 'joined') {
        joined = true;
        setStatus('CHAT LIVE', 'online');
      } else if (data.type === 'cleared') {
        list.replaceChildren();
        showNotice('Chat was cleared by a moderator.');
      } else if (data.type === 'deleted') {
        const id = data.messageId || data.id;
        if (id) [...list.children].find(el => el.dataset.messageId === String(id))?.remove();
      } else if (data.type === 'error') {
        showNotice(data.message || 'Chat request could not be completed.');
      }
    });

    socket.addEventListener('close', () => {
      socket = null;
      joined = false;
      setStatus('CHAT RECONNECTING', 'connecting');
      scheduleReconnect();
    });
    socket.addEventListener('error', () => socket?.close());
  }

  function scheduleReconnect() {
    if (stopped || reconnectTimer) return;
    const delay = reconnectDelay;
    reconnectDelay = Math.min(reconnectDelay * 2, 15000);
    reconnectTimer = setTimeout(() => { reconnectTimer = null; connect(); }, delay);
  }

  profileForm.addEventListener('submit', () => {
    // stage.js persists the visual-room profile; this mirrors it to legacy chat.
    if (socket?.readyState === WebSocket.OPEN) sendJoin(); else connect();
  });

  messageForm.addEventListener('submit', event => {
    event.preventDefault();
    const text = messageInput.value.trim();
    if (!text) return;
    if (!joined) sendJoin();
    if (socket?.readyState !== WebSocket.OPEN) {
      setStatus('CHAT RECONNECTING', 'connecting');
      connect();
      return;
    }
    send('message', { text });
    messageInput.value = '';
  });

  window.addEventListener('pagehide', () => {
    stopped = true;
    clearTimeout(reconnectTimer);
    socket?.close(1000, 'Page closed');
  });

  connect();
})();
