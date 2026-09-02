(() => {
  'use strict';
  if (window.__ebeTalkieV014Installed) return;
  window.__ebeTalkieV014Installed = true;

  const extras = window.EBEExtras;
  const native = window.EBEAndroid;
  if (!extras) return;

  const setup = document.getElementById('setupCard');
  const roomInput = document.getElementById('roomInput');
  const nameInput = document.getElementById('nameInput');
  const connectBtn = document.getElementById('connectBtn');
  const disconnectBtn = document.getElementById('disconnectBtn');
  const shareBtn = document.getElementById('shareBtn');
  const talkerName = document.getElementById('talkerName');

  const enc = new TextEncoder();
  const dec = new TextDecoder();
  const BROKER = 'wss://test.mosquitto.org:8081/mqtt';
  const PRESENCE_TTL_MS = 22000;
  const roomPresence = new Map();
  const roomCrypto = new Map();
  let monitorSocket = null;
  let monitorConnected = false;
  let monitorPacketId = 4000;
  let monitorReconnect = null;
  let monitorReconnectDelay = 900;
  let monitorKeepAlive = null;
  let currentTopicToCode = new Map();

  const style = document.createElement('style');
  style.textContent = `
    .saved-room-card{position:relative;overflow:hidden}
    .saved-room-head{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-bottom:12px}
    .saved-room-title{font-weight:900;font-size:14px;letter-spacing:.08em}
    .saved-room-sub{color:var(--muted);font-size:11px;line-height:1.45;margin-top:4px}
    .saved-room-list{display:grid;gap:9px}
    .saved-room-row{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:8px;align-items:stretch}
    .saved-room-join{min-width:0;text-align:left;border:1px solid var(--line);border-radius:13px;background:#0d0a12;padding:10px 12px;cursor:pointer}
    .saved-room-join:active{transform:scale(.99)}
    .saved-room-topline{display:flex;align-items:center;justify-content:space-between;gap:10px}
    .saved-room-name{display:block;min-width:0;font-weight:900;font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
    .saved-room-count{display:inline-flex;align-items:center;gap:6px;flex:0 0 auto;padding:4px 8px;border-radius:999px;border:1px solid rgba(85,227,157,.22);background:rgba(85,227,157,.07);color:#83e9b7;font-size:10px;font-weight:900;letter-spacing:.04em}
    .saved-room-count.zero{border-color:var(--line);background:transparent;color:#82778e}
    .saved-room-count i{width:6px;height:6px;border-radius:50%;background:currentColor}
    .saved-room-code{display:block;color:#a99db8;font-size:10px;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;margin-top:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
    .saved-room-delete{width:42px;border-radius:12px;border:1px solid var(--line);background:#0d0a12;color:#ff9ba6;font-weight:900;cursor:pointer}
    .saved-room-actions{display:grid;grid-template-columns:1fr 1fr;gap:9px;margin-top:10px}
    .saved-room-empty{padding:12px;border:1px dashed var(--line);border-radius:12px;color:var(--muted);font-size:11px;line-height:1.45}
    .call-alert-note{margin-top:10px;padding:9px 10px;border-radius:11px;border:1px solid rgba(168,85,247,.23);background:rgba(168,85,247,.06);font-size:10px;color:#cbb8de;line-height:1.45}
    .presence-note{margin-top:8px;color:#756b80;font-size:9px;line-height:1.35}
  `;
  document.head.appendChild(style);

  if (setup && !document.getElementById('savedRoomsCard')) {
    const card = document.createElement('section');
    card.className = 'card saved-room-card';
    card.id = 'savedRoomsCard';
    card.innerHTML = `
      <div class="saved-room-head">
        <div>
          <div class="saved-room-title">SAVED ROOMS</div>
          <div class="saved-room-sub">Tap a room to join. Live badges show how many people are currently connected to each saved room.</div>
        </div>
      </div>
      <div class="saved-room-list" id="savedRoomList"></div>
      <div class="saved-room-actions">
        <button class="secondary" id="createSavedRoom" type="button">+ NEW ROOM</button>
        <button class="secondary" id="saveCurrentRoom" type="button">SAVE CURRENT</button>
      </div>
      <div class="call-alert-note">CALL ALERTS ON · If Discord, a phone call, or another app owns your call audio, Talkie Talkie shows a short heads-up/vibration when someone starts transmitting.</div>
      <div class="presence-note">ONLINE COUNTS · A person drops from the count automatically if their encrypted room heartbeat has not been seen for about 22 seconds.</div>
    `;
    setup.parentNode.insertBefore(card, setup);
  }

  const savedRoomList = document.getElementById('savedRoomList');
  const createSavedRoom = document.getElementById('createSavedRoom');
  const saveCurrentRoom = document.getElementById('saveCurrentRoom');

  function cleanName(value) {
    return String(value || '').trim().replace(/[<>]/g, '').slice(0, 32);
  }

  function cleanCode(value) {
    return String(value || '').trim().toUpperCase().replace(/[^A-Z0-9_-]/g, '').slice(0, 64);
  }

  function readRooms() {
    try {
      const parsed = JSON.parse(extras.getSavedRoomsJson());
      return Array.isArray(parsed) ? parsed : [];
    } catch (_) {
      return [];
    }
  }

  function setCurrentRoom(code) {
    const safeCode = cleanCode(code);
    if (!roomInput || !safeCode) return;
    roomInput.value = safeCode;
    roomInput.dispatchEvent(new Event('input', { bubbles: true }));
  }

  function joinRoom(code) {
    const safeCode = cleanCode(code);
    if (!safeCode || !roomInput || !connectBtn) return;

    const reconnect = () => {
      roomInput.disabled = false;
      setCurrentRoom(safeCode);
      setTimeout(() => connectBtn.click(), 80);
    };

    if (roomInput.disabled && disconnectBtn && !disconnectBtn.classList.contains('hidden')) {
      disconnectBtn.click();
      setTimeout(reconnect, 500);
    } else {
      reconnect();
    }
  }

  function activeCount(code) {
    const entries = roomPresence.get(code);
    if (!entries) return 0;
    const now = Date.now();
    for (const [id, seen] of entries) {
      if (now - seen > PRESENCE_TTL_MS) entries.delete(id);
    }
    return entries.size;
  }

  function updateCountBadges() {
    document.querySelectorAll('[data-room-count-code]').forEach((badge) => {
      const code = badge.getAttribute('data-room-count-code') || '';
      const count = activeCount(code);
      badge.classList.toggle('zero', count === 0);
      const text = badge.querySelector('span');
      if (text) text.textContent = `${count} online`;
    });
  }

  function renderRooms() {
    if (!savedRoomList) return;
    const rooms = readRooms();
    savedRoomList.innerHTML = '';

    if (!rooms.length) {
      const empty = document.createElement('div');
      empty.className = 'saved-room-empty';
      empty.textContent = 'No saved rooms yet. Create a new permanent room or save a room code someone shared with you.';
      savedRoomList.appendChild(empty);
      rebuildPresenceSubscriptions();
      return;
    }

    for (const room of rooms) {
      const roomName = cleanName(room?.name) || 'Room';
      const roomCode = cleanCode(room?.code);
      if (!roomCode) continue;

      const row = document.createElement('div');
      row.className = 'saved-room-row';

      const join = document.createElement('button');
      join.type = 'button';
      join.className = 'saved-room-join';
      join.innerHTML = `<span class="saved-room-topline"><span class="saved-room-name"></span><span class="saved-room-count zero" data-room-count-code=""><i></i><span>0 online</span></span></span><span class="saved-room-code"></span>`;
      join.querySelector('.saved-room-name').textContent = roomName;
      join.querySelector('.saved-room-code').textContent = roomCode;
      join.querySelector('.saved-room-count').setAttribute('data-room-count-code', roomCode);
      join.addEventListener('click', () => joinRoom(roomCode));

      const remove = document.createElement('button');
      remove.type = 'button';
      remove.className = 'saved-room-delete';
      remove.textContent = '×';
      remove.setAttribute('aria-label', `Delete ${roomName}`);
      remove.addEventListener('click', (event) => {
        event.stopPropagation();
        if (!confirm(`Remove “${roomName}” from this phone?\n\nThe room code itself will still work for anyone who has it.`)) return;
        try { extras.deleteRoom(roomCode); } catch (_) {}
        roomPresence.delete(roomCode);
        roomCrypto.delete(roomCode);
        renderRooms();
      });

      row.append(join, remove);
      savedRoomList.appendChild(row);
    }

    updateCountBadges();
    rebuildPresenceSubscriptions();
  }

  createSavedRoom?.addEventListener('click', () => {
    const roomName = cleanName(prompt('Name this room:', 'Family'));
    if (!roomName) return;
    let code = '';
    try { code = cleanCode(extras.createRoom(roomName)); } catch (_) {}
    if (!code) {
      alert('Could not create the room. Try again.');
      return;
    }
    setCurrentRoom(code);
    renderRooms();
  });

  saveCurrentRoom?.addEventListener('click', () => {
    const code = cleanCode(roomInput?.value);
    if (code.length < 8) {
      alert('Enter a valid room code first.');
      return;
    }
    const roomName = cleanName(prompt('Name this saved room:', 'Family'));
    if (!roomName) return;
    let saved = false;
    try { saved = !!extras.saveRoomBookmark(roomName, code); } catch (_) {}
    if (!saved) {
      alert('Could not save that room.');
      return;
    }
    renderRooms();
  });

  shareBtn?.addEventListener('click', () => {
    if (roomInput) roomInput.value = cleanCode(roomInput.value);
  }, true);

  let lastTalkerState = '';
  const inspectTalker = () => {
    if (!talkerName) return;
    const text = String(talkerName.textContent || '').trim();
    if (text === lastTalkerState) return;
    lastTalkerState = text;

    const suffix = ' — TRANSMITTING';
    if (!text.endsWith(suffix)) return;

    const who = cleanName(text.slice(0, -suffix.length));
    const me = cleanName(nameInput?.value);
    if (!who || who.toLowerCase() === 'you' || (me && who.toLowerCase() === me.toLowerCase())) return;
    try { extras.notifyTalker(who); } catch (_) {}
  };

  if (talkerName) {
    new MutationObserver(inspectTalker).observe(talkerName, { childList: true, characterData: true, subtree: true });
    inspectTalker();
  }

  async function sha256Hex(text) {
    const digest = await crypto.subtle.digest('SHA-256', enc.encode(text));
    return [...new Uint8Array(digest)].map(b => b.toString(16).padStart(2, '0')).join('');
  }

  function b64ToBytes(s) {
    const raw = atob(s);
    const out = new Uint8Array(raw.length);
    for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
    return out;
  }

  async function deriveRoomKey(code) {
    if (roomCrypto.has(code)) return roomCrypto.get(code);
    const material = await crypto.subtle.importKey('raw', enc.encode(code), 'PBKDF2', false, ['deriveKey']);
    const key = await crypto.subtle.deriveKey(
      { name: 'PBKDF2', salt: enc.encode('EBE-Talkie-Talkie-v1'), iterations: 150000, hash: 'SHA-256' },
      material,
      { name: 'AES-GCM', length: 256 },
      false,
      ['decrypt']
    );
    roomCrypto.set(code, key);
    return key;
  }

  async function decryptPresencePayload(code, text) {
    try {
      const box = JSON.parse(text);
      if (box.v !== 1) return null;
      const key = await deriveRoomKey(code);
      const plain = await crypto.subtle.decrypt({ name: 'AES-GCM', iv: b64ToBytes(box.iv) }, key, b64ToBytes(box.data));
      return JSON.parse(dec.decode(plain));
    } catch (_) {
      return null;
    }
  }

  function mqttString(str) {
    const b = enc.encode(str);
    const out = new Uint8Array(2 + b.length);
    out[0] = (b.length >> 8) & 255;
    out[1] = b.length & 255;
    out.set(b, 2);
    return out;
  }

  function concat(...arrays) {
    const len = arrays.reduce((n, a) => n + a.length, 0);
    const out = new Uint8Array(len);
    let offset = 0;
    for (const a of arrays) { out.set(a, offset); offset += a.length; }
    return out;
  }

  function remainingLength(n) {
    const out = [];
    do {
      let digit = n % 128;
      n = Math.floor(n / 128);
      if (n > 0) digit |= 0x80;
      out.push(digit);
    } while (n > 0);
    return new Uint8Array(out);
  }

  function mqttPacket(type, body) {
    return concat(new Uint8Array([type]), remainingLength(body.length), body);
  }

  function mqttConnectPacket() {
    const variable = concat(mqttString('MQTT'), new Uint8Array([4, 2, 0, 30]));
    let suffix = '';
    try { suffix = String(native?.getDeviceId?.() || '').replace(/-/g, '').slice(0, 10); } catch (_) {}
    const cid = `ebe-presence-${suffix || Math.floor(Math.random() * 999999)}`;
    return mqttPacket(0x10, concat(variable, mqttString(cid)));
  }

  function mqttSubscribePacket(topics) {
    monitorPacketId = (monitorPacketId % 65535) + 1;
    const id = new Uint8Array([(monitorPacketId >> 8) & 255, monitorPacketId & 255]);
    const filters = topics.map(topic => concat(mqttString(topic), new Uint8Array([0])));
    return mqttPacket(0x82, concat(id, ...filters));
  }

  function monitorSend(bytes) {
    if (monitorSocket?.readyState === WebSocket.OPEN) monitorSocket.send(bytes);
  }

  async function rebuildPresenceSubscriptions() {
    const rooms = readRooms();
    const mapping = new Map();
    for (const room of rooms) {
      const code = cleanCode(room?.code);
      if (!code) continue;
      const hash = await sha256Hex(code);
      mapping.set(`ebe-talkie-talkie/v1/${hash.slice(0, 40)}`, code);
      if (!roomPresence.has(code)) roomPresence.set(code, new Map());
    }
    currentTopicToCode = mapping;

    if (!monitorSocket || monitorSocket.readyState === WebSocket.CLOSED || monitorSocket.readyState === WebSocket.CLOSING) {
      connectPresenceMonitor();
      return;
    }
    if (monitorConnected && mapping.size) monitorSend(mqttSubscribePacket([...mapping.keys()]));
  }

  function connectPresenceMonitor() {
    clearTimeout(monitorReconnect);
    if (!readRooms().length) return;
    try {
      monitorSocket = new WebSocket(BROKER, ['mqtt']);
      monitorSocket.binaryType = 'arraybuffer';
    } catch (_) {
      schedulePresenceReconnect();
      return;
    }

    monitorSocket.onopen = () => monitorSend(mqttConnectPacket());
    monitorSocket.onerror = () => {};
    monitorSocket.onclose = () => {
      monitorConnected = false;
      clearInterval(monitorKeepAlive);
      schedulePresenceReconnect();
    };
    monitorSocket.onmessage = event => parseMonitorMqtt(event.data);
  }

  function schedulePresenceReconnect() {
    clearTimeout(monitorReconnect);
    monitorReconnect = setTimeout(connectPresenceMonitor, monitorReconnectDelay);
    monitorReconnectDelay = Math.min(Math.floor(monitorReconnectDelay * 1.6), 10000);
  }

  function parseMonitorMqtt(buffer) {
    const data = new Uint8Array(buffer);
    let i = 0;
    while (i < data.length) {
      const header = data[i++];
      let mult = 1, rem = 0, digit;
      do {
        if (i >= data.length) return;
        digit = data[i++]; rem += (digit & 127) * mult; mult *= 128;
      } while (digit & 128);
      const end = i + rem;
      if (end > data.length) return;
      const type = header >> 4;

      if (type === 2) {
        monitorConnected = true;
        monitorReconnectDelay = 900;
        if (currentTopicToCode.size) monitorSend(mqttSubscribePacket([...currentTopicToCode.keys()]));
        clearInterval(monitorKeepAlive);
        monitorKeepAlive = setInterval(() => monitorSend(new Uint8Array([0xC0, 0])), 20000);
      } else if (type === 3 && i + 2 <= end) {
        const len = (data[i] << 8) | data[i + 1]; i += 2;
        const topic = dec.decode(data.slice(i, i + len)); i += len;
        const payload = dec.decode(data.slice(i, end));
        const code = currentTopicToCode.get(topic);
        if (code) inspectPresencePayload(code, payload);
      }
      i = end;
    }
  }

  async function inspectPresencePayload(code, payload) {
    const message = await decryptPresencePayload(code, payload);
    if (!message?.from) return;
    if (!['hello', 'offer', 'answer', 'ice', 'ptt-start', 'ptt-heartbeat', 'ptt-stop'].includes(message.type)) return;
    let entries = roomPresence.get(code);
    if (!entries) { entries = new Map(); roomPresence.set(code, entries); }
    entries.set(String(message.from), Date.now());
    updateCountBadges();
  }

  setInterval(() => updateCountBadges(), 3000);
  window.addEventListener('online', () => {
    if (!monitorConnected) { monitorReconnectDelay = 300; connectPresenceMonitor(); }
  });

  const footer = document.querySelector('.footer');
  if (footer) footer.textContent = 'EBE TALKIE TALKIE v0.1.4 · FAMILY BUILD';

  renderRooms();
})();
