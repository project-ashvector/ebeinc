(() => {
  'use strict';
  if (window.__ebeTalkieV013Installed) return;
  window.__ebeTalkieV013Installed = true;

  const extras = window.EBEExtras;
  if (!extras) return;

  const setup = document.getElementById('setupCard');
  const roomInput = document.getElementById('roomInput');
  const nameInput = document.getElementById('nameInput');
  const connectBtn = document.getElementById('connectBtn');
  const disconnectBtn = document.getElementById('disconnectBtn');
  const shareBtn = document.getElementById('shareBtn');
  const talkerName = document.getElementById('talkerName');

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
    .saved-room-name{display:block;font-weight:900;font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
    .saved-room-code{display:block;color:#a99db8;font-size:10px;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;margin-top:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
    .saved-room-delete{width:42px;border-radius:12px;border:1px solid var(--line);background:#0d0a12;color:#ff9ba6;font-weight:900;cursor:pointer}
    .saved-room-actions{display:grid;grid-template-columns:1fr 1fr;gap:9px;margin-top:10px}
    .saved-room-empty{padding:12px;border:1px dashed var(--line);border-radius:12px;color:var(--muted);font-size:11px;line-height:1.45}
    .call-alert-note{margin-top:10px;padding:9px 10px;border-radius:11px;border:1px solid rgba(168,85,247,.23);background:rgba(168,85,247,.06);font-size:10px;color:#cbb8de;line-height:1.45}
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
          <div class="saved-room-sub">Each room keeps its own permanent room code. Tap a saved room to join it.</div>
        </div>
      </div>
      <div class="saved-room-list" id="savedRoomList"></div>
      <div class="saved-room-actions">
        <button class="secondary" id="createSavedRoom" type="button">+ NEW ROOM</button>
        <button class="secondary" id="saveCurrentRoom" type="button">SAVE CURRENT</button>
      </div>
      <div class="call-alert-note">CALL ALERTS ON · If Discord, a phone call, or another app owns your call audio, Talkie Talkie will show a short heads-up/vibration when someone starts transmitting.</div>
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

  function renderRooms() {
    if (!savedRoomList) return;
    const rooms = readRooms();
    savedRoomList.innerHTML = '';

    if (!rooms.length) {
      const empty = document.createElement('div');
      empty.className = 'saved-room-empty';
      empty.textContent = 'No saved rooms yet. Create a new permanent room or save a room code someone shared with you.';
      savedRoomList.appendChild(empty);
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
      join.innerHTML = `<span class="saved-room-name"></span><span class="saved-room-code"></span>`;
      join.querySelector('.saved-room-name').textContent = roomName;
      join.querySelector('.saved-room-code').textContent = roomCode;
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
        renderRooms();
      });

      row.append(join, remove);
      savedRoomList.appendChild(row);
    }
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

  // When a saved room is selected, the existing Share button will share that
  // exact permanent code because roomInput is updated first.
  shareBtn?.addEventListener('click', () => {
    if (roomInput) roomInput.value = cleanCode(roomInput.value);
  }, true);

  // The v0.1.2 radio core already exposes remote PTT state in #talkerName.
  // Observe that proven state instead of changing MQTT/WebRTC code.
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
    new MutationObserver(inspectTalker).observe(talkerName, {
      childList: true,
      characterData: true,
      subtree: true
    });
    inspectTalker();
  }

  const footer = document.querySelector('.footer');
  if (footer) footer.textContent = 'EBE TALKIE TALKIE v0.1.3 · FAMILY BUILD';

  renderRooms();
})();
