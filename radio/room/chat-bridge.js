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
  let identity = { signedIn: false };
  let accessToken = null;
  let termsAccepted = false;

  function updatePostingUi() {
    if (!identity.signedIn) {
      messageInput.placeholder = 'SIGN IN TO JOIN GREEN ROOM';
      messageForm.querySelector('button')?.replaceChildren(document.createTextNode('SIGN IN TO POST'));
      return;
    }
    messageInput.placeholder = termsAccepted ? 'Say something…' : 'ACCEPT TERMS TO POST';
    messageForm.querySelector('button')?.replaceChildren(document.createTextNode(termsAccepted ? 'SEND' : 'ACCEPT TERMS'));
  }

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

  function requestSession() {
    try { window.parent.postMessage({ type: 'AT140_REQUEST_SESSION' }, location.origin); } catch (_) {}
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
    li.dataset.senderId = msg.senderId || '';
    const b = document.createElement('b');
    b.textContent = `${msg.name || 'Listener'}${msg.verified ? ' ✓' : ''} `;
    const time = document.createElement('time');
    time.textContent = new Date(msg.ts || Date.now()).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
    const text = document.createElement('span');
    text.textContent = msg.text;
    li.append(b, time, document.createElement('br'), text);
    if (identity.signedIn && msg.senderId && msg.senderId !== identity.userId) {
      const actions = document.createElement('span');
      actions.className = 'chat-message-actions';
      const report = document.createElement('button'); report.type = 'button'; report.textContent = 'REPORT';
      report.addEventListener('click', () => { const reason = prompt('Report reason (harassment, hate, sexual, threat, spam, scam, privacy, copyright, other):', 'other'); if (reason) send('report', { messageId: msg.id, reason: reason.toLowerCase().trim() }); });
      const block = document.createElement('button'); block.type = 'button'; block.textContent = 'BLOCK';
      block.addEventListener('click', () => { if (confirm(`Block ${msg.name || 'this listener'}?`)) send('block', { userId: msg.senderId }); });
      actions.append(' ', report, ' ', block); li.append(actions);
    }
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

  function showTermsGate() {
    const li = document.createElement('li');
    li.className = 'chat-notice terms-gate';
    const copy = document.createElement('span');
    copy.textContent = 'Read the current Green Room Terms before posting.';
    const link = document.createElement('a'); link.href = '/terms/'; link.target = '_blank'; link.rel = 'noopener'; link.textContent = ' OPEN TERMS';
    const agree = document.createElement('button'); agree.type = 'button'; agree.textContent = 'I AGREE — ENTER GREEN ROOM';
    const notNow = document.createElement('button'); notNow.type = 'button'; notNow.textContent = 'NOT NOW';
    agree.addEventListener('click', () => { send('terms_accept'); agree.disabled = true; });
    notNow.addEventListener('click', () => li.remove());
    li.append(copy, link, document.createElement('br'), agree, ' ', notNow);
    list.append(li); list.scrollTop = list.scrollHeight;
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
      requestSession();
    });

    socket.addEventListener('message', event => {
      let data;
      try { data = JSON.parse(event.data); } catch (_) { return; }
      if (data.type === 'history') {
        list.replaceChildren();
        (data.messages || []).forEach(addMessage);
      } else if (data.type === 'message') {
        addMessage(data.message);
      } else if (data.type === 'auth_state') {
        identity = { signedIn: true, userId: data.userId, username: data.username, avatarUrl: data.avatarPath || null, accountStatus: data.accountStatus };
        termsAccepted = false;
        updatePostingUi();
        nameInput.value = data.username || nameInput.value;
        setStatus('SIGNED IN — ACCEPT TERMS TO POST', 'online');
        send('post_policy');
      } else if (data.type === 'post_policy') {
        termsAccepted = Boolean(data.allowed);
        if (termsAccepted) { setStatus('CHAT LIVE', 'online'); updatePostingUi(); }
        else if (data.reason === 'terms_acceptance_required') showTermsGate();
        else setStatus(data.reason === 'sign_in_required' ? 'SIGN IN TO JOIN GREEN ROOM' : 'POSTING RESTRICTED', 'error');
      } else if (data.type === 'terms_accepted') {
        termsAccepted = true; setStatus('CHAT LIVE', 'online'); updatePostingUi();
      } else if (data.type === 'report_submitted') {
        showNotice('Report submitted to moderation.');
      } else if (data.type === 'blocked') {
        [...list.children].find(el => el.dataset.senderId === String(data.userId))?.remove(); showNotice('Listener blocked.');
      } else if (data.type === 'expired') {
        [...list.children].find(el => el.dataset.messageId === String(data.id))?.remove();
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
    if (!identity.signedIn) { showNotice('Sign in to join Green Room.'); window.parent.postMessage({ type: 'AT140_OPEN_AUTH', mode: 'signin' }, location.origin); return; }
    if (!termsAccepted) { send('post_policy'); showNotice('Accept the current Green Room Terms before posting.'); return; }
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

  window.addEventListener('message', event => {
    if (event.origin !== location.origin || event.data?.type !== 'AT140_SESSION') return;
    accessToken = event.data.accessToken || null;
    if (accessToken) send('auth', { accessToken });
  });

  connect();
  updatePostingUi();
})();
