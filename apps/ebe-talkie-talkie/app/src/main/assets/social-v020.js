(() => {
  'use strict';
  if (window.__ebeTalkieV020Installed) return;
  window.__ebeTalkieV020Installed = true;

  const social = window.EBESocial;
  const extras = window.EBEExtras;
  const android = window.EBEAndroid;
  if (!social) return;

  const $ = (id) => document.getElementById(id);
  const setupCard = $('setupCard');
  const roomInput = $('roomInput');
  const nameInput = $('nameInput');
  const connectBtn = $('connectBtn');
  const disconnectBtn = $('disconnectBtn');
  const statusValue = $('statusValue');
  const talkerName = $('talkerName');
  const app = document.querySelector('.app');
  const footer = document.querySelector('.footer');

  const API = String(social.getApiBaseUrl?.() || '').replace(/\/+$/, '');
  let token = String(social.getAuthToken?.() || '');
  let me = null;
  let friends = { accepted: [], incoming: [], outgoing: [] };
  let rooms = [];
  let currentRoom = null;
  let syncTimer = null;
  let presenceTimer = null;
  let syncing = false;

  const style = document.createElement('style');
  style.textContent = `
    .social-auth{position:fixed;z-index:9999;inset:0;background:radial-gradient(circle at 50% 0,#2d1540 0,#09060e 52%);padding:max(28px,env(safe-area-inset-top)) 18px 28px;display:flex;align-items:center;justify-content:center}
    .social-auth.hidden{display:none}.auth-box{width:min(100%,430px);background:#15101d;border:1px solid #39284c;border-radius:24px;padding:22px;box-shadow:0 28px 90px rgba(0,0,0,.55)}
    .auth-logo{text-align:center;margin-bottom:19px}.auth-logo b{font-size:25px;letter-spacing:.05em}.auth-logo span{display:block;color:#a99db8;font-size:11px;letter-spacing:.14em;margin-top:7px}.auth-tabs{display:grid;grid-template-columns:1fr 1fr;gap:7px;margin-bottom:16px}.auth-tab{border:1px solid #34263f;background:#0d0a12;border-radius:11px;padding:11px;font-weight:800;color:#a99db8}.auth-tab.active{background:#7c3aed;color:white;border-color:#9f62ef}
    .social-input{width:100%;min-height:46px;border-radius:12px;border:1px solid #352642;background:#0d0a12;color:#f6f2fb;padding:0 12px;font-size:15px;margin-bottom:9px;outline:none}.social-input:focus{border-color:#a855f7}.social-primary{width:100%;border:0;border-radius:12px;min-height:47px;background:linear-gradient(135deg,#7c3aed,#a855f7);color:white;font-weight:900;letter-spacing:.07em}.auth-note{font-size:10px;color:#9587a4;line-height:1.5;margin-top:11px;text-align:center}.social-msg{font-size:11px;line-height:1.4;min-height:16px;margin:9px 1px;color:#ff8d99}.social-msg.good{color:#6ce7ab}
    .social-card{background:linear-gradient(180deg,rgba(27,19,38,.97),rgba(16,12,23,.97));border:1px solid #30243f;border-radius:20px;padding:15px;margin-bottom:14px}.social-head{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:12px}.social-title{font-size:12px;font-weight:950;letter-spacing:.11em}.social-sub{font-size:10px;color:#a99db8;margin-top:3px}.small-btn{border:1px solid #3a2b47;background:#0d0a12;color:#d8cce5;border-radius:10px;padding:8px 10px;font-size:10px;font-weight:850}.small-btn.purple{border-color:#70419a;color:#d7a8ff}.small-btn.warn{color:#ff9aa5}.mini-row{display:flex;align-items:center;gap:10px;padding:9px 0;border-top:1px solid rgba(255,255,255,.05)}.mini-row:first-child{border-top:0}.avatar{width:42px;height:42px;border-radius:50%;object-fit:cover;background:linear-gradient(135deg,#7c3aed,#ff7a1a);display:grid;place-items:center;font-weight:950;flex:0 0 auto;overflow:hidden}.avatar img{width:100%;height:100%;object-fit:cover}.avatar.big{width:64px;height:64px;font-size:20px}.person-info{min-width:0;flex:1}.person-name{font-weight:900;overflow:hidden;text-overflow:ellipsis}.person-meta{font-size:10px;color:#a99db8;margin-top:3px}.profile-top{display:flex;align-items:center;gap:13px}.profile-actions{display:flex;gap:7px;flex-wrap:wrap;margin-top:12px}
    .friend-add{display:grid;grid-template-columns:1fr auto;gap:8px}.friend-add .social-input{margin:0}.friend-add+.social-msg{margin-bottom:0}.section-label{font-size:9px;color:#8f819d;letter-spacing:.13em;margin:13px 0 5px}.badge{display:inline-flex;align-items:center;border-radius:999px;padding:4px 7px;font-size:9px;font-weight:900;background:#251a31;color:#c9b7da;margin-left:5px}.badge.green{background:rgba(85,227,157,.10);color:#6ce7ab}.badge.orange{background:rgba(255,122,26,.12);color:#ff9c55}.badge.lock{background:rgba(168,85,247,.15);color:#d4a6ff}
    .room-list{display:grid;gap:9px}.room-card{border:1px solid #342641;background:#0d0a12;border-radius:15px;padding:12px}.room-top{display:flex;align-items:center;gap:10px}.room-main{min-width:0;flex:1}.room-name{font-weight:950;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.room-owner{font-size:10px;color:#a99db8;margin-top:3px}.room-actions{display:flex;gap:7px;flex-wrap:wrap;margin-top:10px}.room-code{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:9px;color:#766a84;margin-top:7px;word-break:break-all}.join-code{display:grid;grid-template-columns:1fr auto;gap:8px;margin-top:11px}.join-code .social-input{margin:0}.empty-box{border:1px dashed #3a2b47;border-radius:12px;padding:12px;color:#998ca7;font-size:11px;line-height:1.45}
    .current-room{display:flex;align-items:center;gap:10px}.current-room-main{flex:1;min-width:0}.current-room-name{font-weight:950;font-size:15px}.current-room-meta{font-size:10px;color:#a99db8;margin-top:3px}.talker-profile{display:flex;align-items:center;justify-content:center;gap:8px;margin-top:7px}.talker-profile .avatar{width:29px;height:29px;font-size:10px}.backend-pill{display:inline-flex;border:1px solid rgba(85,227,157,.22);color:#6ce7ab;background:rgba(85,227,157,.05);border-radius:999px;padding:5px 8px;font-size:9px;font-weight:900}
    #setupCard.social-hidden{display:none!important}.social-hidden{display:none!important}
  `;
  document.head.appendChild(style);

  const auth = document.createElement('div');
  auth.className = 'social-auth';
  auth.id = 'socialAuth';
  auth.innerHTML = `
    <div class="auth-box">
      <div class="auth-logo"><b>EBE TALKIE TALKIE</b><span>PRIVATE SOCIAL RADIO</span></div>
      <div class="auth-tabs"><button class="auth-tab active" id="loginTab">LOG IN</button><button class="auth-tab" id="signupTab">SIGN UP</button></div>
      <input class="social-input" id="authUsername" maxlength="24" autocapitalize="none" autocomplete="username" placeholder="Username">
      <input class="social-input" id="authPassword" maxlength="128" type="password" autocomplete="current-password" placeholder="Password">
      <button class="social-primary" id="authSubmit">LOG IN</button>
      <div class="social-msg" id="authMessage"></div>
      <div class="auth-note">No email or phone number required. Usernames use letters, numbers, and underscore. Passwords stay hashed on the EBE social backend.</div>
    </div>`;
  document.body.appendChild(auth);

  const socialRoot = document.createElement('div');
  socialRoot.id = 'socialRoot';
  socialRoot.className = 'social-hidden';
  socialRoot.innerHTML = `
    <section class="social-card" id="profileCard">
      <div class="social-head"><div><div class="social-title">PROFILE</div><div class="social-sub">Your Talkie identity</div></div><span class="backend-pill">SYNCED</span></div>
      <div class="profile-top"><div class="avatar big" id="meAvatar"></div><div class="person-info"><div class="person-name" id="meUsername"></div><div class="person-meta">Username is also your radio call sign</div></div></div>
      <div class="profile-actions"><button class="small-btn purple" id="changeAvatar">CHANGE PHOTO</button><button class="small-btn" id="removeAvatar">REMOVE PHOTO</button><button class="small-btn warn" id="logoutBtn">LOG OUT</button></div>
    </section>
    <section class="social-card" id="friendsCard">
      <div class="social-head"><div><div class="social-title">FRIENDS</div><div class="social-sub">Friends automatically see your friend-visible rooms</div></div><span class="badge" id="friendCount">0</span></div>
      <div class="friend-add"><input class="social-input" id="friendUsername" maxlength="24" autocapitalize="none" placeholder="Add by username"><button class="small-btn purple" id="addFriendBtn">ADD</button></div>
      <div class="social-msg" id="friendMessage"></div>
      <div id="incomingWrap"></div><div id="friendsList"></div>
    </section>
    <section class="social-card" id="roomsCard">
      <div class="social-head"><div><div class="social-title">ROOMS</div><div class="social-sub">Synced rooms from you and your friends</div></div><button class="small-btn purple" id="newRoomBtn">+ NEW ROOM</button></div>
      <div class="room-list" id="roomList"></div>
      <div class="section-label">JOIN A SHARED CODE</div>
      <div class="join-code"><input class="social-input" id="joinCodeInput" maxlength="64" autocapitalize="characters" placeholder="EBE-XXXX-XXXX-XXXX"><button class="small-btn" id="joinCodeBtn">JOIN</button></div>
      <div class="social-msg" id="roomMessage"></div>
    </section>
    <section class="social-card" id="currentRoomCard">
      <div class="social-title" style="margin-bottom:10px">CURRENT RADIO ROOM</div>
      <div class="current-room"><div class="avatar" id="currentOwnerAvatar"></div><div class="current-room-main"><div class="current-room-name" id="currentRoomName">Not connected</div><div class="current-room-meta" id="currentRoomMeta">Choose a room above.</div></div><button class="small-btn warn social-hidden" id="socialDisconnect">LEAVE</button></div>
    </section>`;
  if (app && setupCard) app.insertBefore(socialRoot, setupCard);
  if (setupCard) setupCard.classList.add('social-hidden');
  if (footer) footer.textContent = 'EBE TALKIE TALKIE v0.2.0 · SOCIAL FAMILY BUILD';

  const ui = {
    auth, loginTab: $('loginTab'), signupTab: $('signupTab'), authUser: $('authUsername'), authPass: $('authPassword'), authSubmit: $('authSubmit'), authMsg: $('authMessage'),
    root: socialRoot, meAvatar: $('meAvatar'), meUsername: $('meUsername'), changeAvatar: $('changeAvatar'), removeAvatar: $('removeAvatar'), logout: $('logoutBtn'),
    friendUsername: $('friendUsername'), addFriend: $('addFriendBtn'), friendMsg: $('friendMessage'), friendCount: $('friendCount'), incoming: $('incomingWrap'), friendList: $('friendsList'),
    roomList: $('roomList'), newRoom: $('newRoomBtn'), joinCode: $('joinCodeInput'), joinCodeBtn: $('joinCodeBtn'), roomMsg: $('roomMessage'),
    currentAvatar: $('currentOwnerAvatar'), currentName: $('currentRoomName'), currentMeta: $('currentRoomMeta'), socialDisconnect: $('socialDisconnect'),
  };

  let authMode = 'login';

  function msg(el, text, good = false) {
    if (!el) return;
    el.textContent = text || '';
    el.className = 'social-msg' + (good ? ' good' : '');
  }
  function initials(name) { return String(name || '?').slice(0, 2).toUpperCase(); }
  function fillAvatar(el, user) {
    if (!el) return;
    el.innerHTML = '';
    if (user?.avatar) {
      const img = document.createElement('img');
      img.src = user.avatar;
      img.alt = '';
      el.appendChild(img);
    } else el.textContent = initials(user?.username);
  }
  function cleanUsername(v) { return String(v || '').trim().toLowerCase().replace(/[^a-z0-9_]/g, '').slice(0, 24); }
  function cleanCode(v) { return String(v || '').trim().toUpperCase().replace(/[^A-Z0-9_-]/g, '').slice(0, 64); }
  function backendReady() { return /^https:\/\//i.test(API) && !API.includes('.invalid'); }

  async function api(path, options = {}) {
    if (!backendReady()) throw new Error('Social backend is not linked to this build.');
    const headers = { ...(options.headers || {}) };
    if (options.body !== undefined && !headers['content-type']) headers['content-type'] = 'application/json';
    if (token) headers.authorization = `Bearer ${token}`;
    const response = await fetch(API + path, { ...options, headers });
    let data = {};
    try { data = await response.json(); } catch (_) {}
    if (!response.ok) {
      if (response.status === 401 && token) {
        token = '';
        try { social.clearAuthToken?.(); } catch (_) {}
      }
      const error = new Error(data.error || `Request failed (${response.status})`);
      error.data = data;
      error.status = response.status;
      throw error;
    }
    return data;
  }

  function setAuthMode(mode) {
    authMode = mode === 'signup' ? 'signup' : 'login';
    ui.loginTab.classList.toggle('active', authMode === 'login');
    ui.signupTab.classList.toggle('active', authMode === 'signup');
    ui.authSubmit.textContent = authMode === 'signup' ? 'CREATE ACCOUNT' : 'LOG IN';
    ui.authPass.autocomplete = authMode === 'signup' ? 'new-password' : 'current-password';
    msg(ui.authMsg, '');
  }

  async function submitAuth() {
    const username = cleanUsername(ui.authUser.value);
    const password = String(ui.authPass.value || '');
    if (username.length < 3) return msg(ui.authMsg, 'Username must be at least 3 characters.');
    if (password.length < 6) return msg(ui.authMsg, 'Password must be at least 6 characters.');
    ui.authSubmit.disabled = true;
    ui.authSubmit.textContent = authMode === 'signup' ? 'CREATING…' : 'LOGGING IN…';
    try {
      const data = await api(authMode === 'signup' ? '/v1/signup' : '/v1/login', { method: 'POST', body: JSON.stringify({ username, password }) });
      token = data.token;
      me = data.user;
      social.saveAuthToken?.(token);
      social.setAccountUsername?.(me.username);
      await enterApp();
    } catch (e) { msg(ui.authMsg, e.message); }
    finally {
      ui.authSubmit.disabled = false;
      ui.authSubmit.textContent = authMode === 'signup' ? 'CREATE ACCOUNT' : 'LOG IN';
    }
  }

  async function restoreSession() {
    if (!token) return false;
    try {
      const data = await api('/v1/me');
      me = data.user;
      social.setAccountUsername?.(me.username);
      return true;
    } catch (_) {
      token = '';
      social.clearAuthToken?.();
      return false;
    }
  }

  async function enterApp() {
    ui.auth.classList.add('hidden');
    ui.root.classList.remove('social-hidden');
    if (nameInput) {
      nameInput.value = me.username;
      nameInput.dispatchEvent(new Event('input', { bubbles: true }));
    }
    renderProfile();
    await syncAll(true);
    startTimers();
  }

  function renderProfile() {
    ui.meUsername.textContent = '@' + (me?.username || '');
    fillAvatar(ui.meAvatar, me);
  }

  function personRow(user, meta, actions = []) {
    const row = document.createElement('div'); row.className = 'mini-row';
    const avatar = document.createElement('div'); avatar.className = 'avatar'; fillAvatar(avatar, user);
    const info = document.createElement('div'); info.className = 'person-info';
    const name = document.createElement('div'); name.className = 'person-name'; name.textContent = '@' + user.username;
    const sub = document.createElement('div'); sub.className = 'person-meta'; sub.textContent = meta || '';
    info.append(name, sub); row.append(avatar, info); for (const action of actions) row.append(action); return row;
  }

  function actionButton(label, cls = '') {
    const btn = document.createElement('button'); btn.type = 'button'; btn.className = 'small-btn ' + cls; btn.textContent = label; return btn;
  }

  function renderFriends() {
    ui.friendCount.textContent = String(friends.accepted.length);
    ui.incoming.innerHTML = ''; ui.friendList.innerHTML = '';
    if (friends.incoming.length) {
      const label = document.createElement('div'); label.className = 'section-label'; label.textContent = 'FRIEND REQUESTS'; ui.incoming.appendChild(label);
      for (const user of friends.incoming) {
        const accept = actionButton('ACCEPT', 'purple');
        accept.addEventListener('click', async () => {
          accept.disabled = true;
          try { await api('/v1/friends/accept', { method:'POST', body:JSON.stringify({ username:user.username }) }); await syncAll(); }
          catch (e) { msg(ui.friendMsg, e.message); }
        });
        ui.incoming.appendChild(personRow(user, 'Wants to be friends', [accept]));
      }
    }
    const label = document.createElement('div'); label.className = 'section-label'; label.textContent = 'YOUR FRIENDS'; ui.friendList.appendChild(label);
    if (!friends.accepted.length) {
      const empty = document.createElement('div'); empty.className = 'empty-box'; empty.textContent = 'Add your mom, girlfriend, or anyone else by username. Once accepted, friend-visible rooms sync automatically.'; ui.friendList.appendChild(empty);
    } else {
      for (const user of friends.accepted) {
        const remove = actionButton('REMOVE', 'warn');
        remove.addEventListener('click', async () => {
          if (!confirm(`Remove @${user.username} from friends?`)) return;
          try { await api('/v1/friends/remove', { method:'POST', body:JSON.stringify({ username:user.username }) }); await syncAll(); }
          catch (e) { msg(ui.friendMsg, e.message); }
        });
        ui.friendList.appendChild(personRow(user, 'Friend', [remove]));
      }
    }
  }

  function roomOwnerUser(room) { return room?.owner || { username:'unknown', avatar:'' }; }

  function renderRooms() {
    ui.roomList.innerHTML = '';
    if (!rooms.length) {
      const empty = document.createElement('div'); empty.className = 'empty-box'; empty.textContent = 'No synced rooms yet. Create one, or add a friend and their friend-visible rooms will appear here automatically.'; ui.roomList.appendChild(empty); return;
    }
    for (const room of rooms) {
      const card = document.createElement('div'); card.className = 'room-card';
      const top = document.createElement('div'); top.className = 'room-top';
      const av = document.createElement('div'); av.className = 'avatar'; fillAvatar(av, roomOwnerUser(room));
      const main = document.createElement('div'); main.className = 'room-main';
      const title = document.createElement('div'); title.className = 'room-name'; title.textContent = room.name;
      const owner = document.createElement('div'); owner.className = 'room-owner'; owner.textContent = room.mine ? 'Created by you' : `Created by @${room.owner?.username || 'unknown'}`;
      main.append(title, owner);
      const online = document.createElement('span'); online.className = 'badge green'; online.textContent = `${room.online || 0} online`;
      top.append(av, main, online); card.appendChild(top);

      const badges = document.createElement('div'); badges.style.marginTop = '8px';
      const vis = document.createElement('span'); vis.className = 'badge'; vis.textContent = room.visibility === 'private' ? 'PRIVATE' : 'FRIENDS'; badges.appendChild(vis);
      if (room.locked) { const lock = document.createElement('span'); lock.className = 'badge lock'; lock.textContent = '🔒 PIN'; badges.appendChild(lock); }
      if (room.joined) { const joined = document.createElement('span'); joined.className = 'badge orange'; joined.textContent = 'MEMBER'; badges.appendChild(joined); }
      card.appendChild(badges);

      const actions = document.createElement('div'); actions.className = 'room-actions';
      const join = actionButton(currentRoom?.id === room.id ? 'CONNECTED' : 'JOIN', 'purple'); join.disabled = currentRoom?.id === room.id;
      join.addEventListener('click', () => joinSocialRoom(room)); actions.appendChild(join);
      if (room.joined && room.code) {
        const share = actionButton('SHARE CODE'); share.addEventListener('click', () => { try { android?.shareRoom?.(room.code); } catch (_) {} }); actions.appendChild(share);
      }
      if (room.mine) {
        const edit = actionButton('EDIT'); edit.addEventListener('click', () => editRoom(room)); actions.appendChild(edit);
        const del = actionButton('DELETE', 'warn'); del.addEventListener('click', () => deleteRoom(room)); actions.appendChild(del);
      }
      card.appendChild(actions);
      if (room.joined && room.code) { const code = document.createElement('div'); code.className = 'room-code'; code.textContent = room.code; card.appendChild(code); }
      ui.roomList.appendChild(card);
    }
  }

  async function createNewRoom() {
    const name = String(prompt('Room name:', 'Family') || '').trim().slice(0, 48); if (!name) return;
    const locked = confirm('Lock this room with a PIN?\n\nOK = PIN locked\nCancel = Open'); let pin = '';
    if (locked) { pin = String(prompt('Enter a 4-12 digit PIN:') || '').trim(); if (!/^\d{4,12}$/.test(pin)) return msg(ui.roomMsg, 'PIN must be 4-12 digits.'); }
    const friendVisible = confirm('Should your friends automatically see this room?\n\nOK = Friends can see it\nCancel = Private');
    try {
      const data = await api('/v1/rooms', { method:'POST', body:JSON.stringify({ name, locked, pin, visibility:friendVisible ? 'friends' : 'private' }) });
      msg(ui.roomMsg, `Created “${data.room.name}”.`, true); await syncAll();
    } catch (e) { msg(ui.roomMsg, e.message); }
  }

  async function editRoom(room) {
    const name = String(prompt('Room name:', room.name) ?? room.name).trim().slice(0, 48); if (!name) return;
    const friendVisible = confirm('Should friends automatically see this room?\n\nOK = Friends\nCancel = Private');
    const locked = confirm('Should this room require a PIN?\n\nOK = Locked\nCancel = Open'); let pin;
    if (locked) {
      const promptText = room.locked ? 'New PIN (leave blank to keep current PIN):' : 'Enter a 4-12 digit PIN:';
      pin = String(prompt(promptText) ?? '').trim();
      if ((!room.locked || pin) && !/^\d{4,12}$/.test(pin)) return msg(ui.roomMsg, 'PIN must be 4-12 digits.');
    }
    const body = { name, visibility:friendVisible ? 'friends' : 'private', locked }; if (locked && pin) body.pin = pin;
    try { await api(`/v1/rooms/${encodeURIComponent(room.id)}`, { method:'PATCH', body:JSON.stringify(body) }); msg(ui.roomMsg, 'Room updated.', true); await syncAll(); }
    catch (e) { msg(ui.roomMsg, e.message); }
  }

  async function deleteRoom(room) {
    if (!confirm(`Delete “${room.name}”?\n\nThis removes the synced room for everyone.`)) return;
    try { if (currentRoom?.id === room.id) await leaveCurrentRoom(); await api(`/v1/rooms/${encodeURIComponent(room.id)}`, { method:'DELETE' }); msg(ui.roomMsg, 'Room deleted.', true); await syncAll(); }
    catch (e) { msg(ui.roomMsg, e.message); }
  }

  async function joinSocialRoom(room) {
    let pin = '';
    if (room.locked && !room.joined) { pin = String(prompt(`PIN for “${room.name}”:`) || '').trim(); if (!pin) return; }
    try { const data = await api(`/v1/rooms/${encodeURIComponent(room.id)}/join`, { method:'POST', body:JSON.stringify({ pin }) }); await connectRoom(data.room); await syncAll(); }
    catch (e) { msg(ui.roomMsg, e.message); }
  }

  async function joinSharedCode() {
    const code = cleanCode(ui.joinCode.value); if (code.length < 8) return msg(ui.roomMsg, 'Enter a valid room code.'); let pin = '';
    try {
      let data;
      try { data = await api('/v1/rooms/join-code', { method:'POST', body:JSON.stringify({ code, pin }) }); }
      catch (e) {
        if (e.data?.pinRequired) { pin = String(prompt('This room is PIN locked. Enter the PIN:') || '').trim(); if (!pin) return; data = await api('/v1/rooms/join-code', { method:'POST', body:JSON.stringify({ code, pin }) }); }
        else throw e;
      }
      ui.joinCode.value = ''; await connectRoom(data.room); await syncAll();
    } catch (e) { msg(ui.roomMsg, e.message); }
  }

  async function connectRoom(room) {
    if (!room?.code) throw new Error('The backend did not authorize a room code.');
    if (currentRoom && currentRoom.id !== room.id) await leavePresence(currentRoom.id);
    if (disconnectBtn && !disconnectBtn.classList.contains('hidden')) { disconnectBtn.click(); await new Promise((r) => setTimeout(r, 450)); }
    if (nameInput) { nameInput.disabled = false; nameInput.value = me.username; nameInput.dispatchEvent(new Event('input', { bubbles:true })); }
    if (roomInput) { roomInput.disabled = false; roomInput.value = room.code; roomInput.dispatchEvent(new Event('input', { bubbles:true })); }
    currentRoom = room; renderCurrentRoom(); setTimeout(() => connectBtn?.click(), 90);
  }

  async function leavePresence(roomId) { if (!roomId || !token) return; try { await api('/v1/presence/leave', { method:'POST', body:JSON.stringify({ roomId }) }); } catch (_) {} }
  async function leaveCurrentRoom() { if (currentRoom) await leavePresence(currentRoom.id); currentRoom = null; if (disconnectBtn && !disconnectBtn.classList.contains('hidden')) disconnectBtn.click(); renderCurrentRoom(); renderRooms(); }

  function renderCurrentRoom() {
    if (!currentRoom) { ui.currentName.textContent = 'Not connected'; ui.currentMeta.textContent = 'Choose a room above.'; fillAvatar(ui.currentAvatar, null); ui.socialDisconnect.classList.add('social-hidden'); return; }
    ui.currentName.textContent = currentRoom.name;
    ui.currentMeta.textContent = `@${currentRoom.owner?.username || 'unknown'} · ${currentRoom.locked ? 'PIN locked' : 'Open'} · ${currentRoom.online || 0} online`;
    fillAvatar(ui.currentAvatar, currentRoom.owner); ui.socialDisconnect.classList.remove('social-hidden');
  }

  async function migrateLegacyRoomIfNeeded() {
    if (rooms.length) return;
    const legacy = cleanCode(roomInput?.value); if (legacy.length < 8) return;
    try { await api('/v1/rooms', { method:'POST', body:JSON.stringify({ name:'Family', visibility:'friends', locked:false, code:legacy }) }); }
    catch (e) { if (e.status === 409) { try { await api('/v1/rooms/join-code', { method:'POST', body:JSON.stringify({ code:legacy, pin:'' }) }); } catch (_) {} } }
  }

  async function syncAll(initial = false) {
    if (!token || syncing) return; syncing = true;
    try {
      const [friendData, roomData] = await Promise.all([api('/v1/friends'), api('/v1/rooms')]); friends = friendData; rooms = roomData.rooms || [];
      if (initial && !rooms.length) { await migrateLegacyRoomIfNeeded(); rooms = (await api('/v1/rooms')).rooms || []; }
      if (currentRoom) { const newer = rooms.find((r) => r.id === currentRoom.id); if (newer) currentRoom = { ...currentRoom, ...newer, code: newer.code || currentRoom.code }; }
      else { const currentCode = cleanCode(roomInput?.value); const match = rooms.find((r) => r.code && r.code === currentCode && (statusValue?.textContent || '').includes('ONLINE')); if (match) currentRoom = match; }
      renderFriends(); renderRooms(); renderCurrentRoom(); updateTalkerAvatar();
    } catch (e) { if (e.status === 401) return showAuth('Session expired. Log in again.'); msg(ui.roomMsg, `Sync: ${e.message}`); }
    finally { syncing = false; }
  }

  async function heartbeatPresence() { if (!currentRoom || !token || !String(statusValue?.textContent || '').includes('ONLINE')) return; try { await api('/v1/presence', { method:'POST', body:JSON.stringify({ roomId:currentRoom.id }) }); } catch (_) {} }
  function startTimers() { clearInterval(syncTimer); clearInterval(presenceTimer); syncTimer = setInterval(() => syncAll(), 7000); presenceTimer = setInterval(heartbeatPresence, 9000); setTimeout(heartbeatPresence, 1200); }
  function stopTimers() { clearInterval(syncTimer); clearInterval(presenceTimer); syncTimer = null; presenceTimer = null; }
  function showAuth(message = '') { stopTimers(); ui.root.classList.add('social-hidden'); ui.auth.classList.remove('hidden'); if (disconnectBtn && !disconnectBtn.classList.contains('hidden')) disconnectBtn.click(); if (message) msg(ui.authMsg, message); }

  async function logout() {
    try { if (token) await api('/v1/logout', { method:'POST', body:'{}' }); } catch (_) {}
    if (currentRoom) await leavePresence(currentRoom.id);
    token = ''; me = null; friends = {accepted:[],incoming:[],outgoing:[]}; rooms=[]; currentRoom=null; social.clearAuthToken?.(); showAuth('Logged out.');
  }

  async function addFriend() {
    const username = cleanUsername(ui.friendUsername.value); if (username.length < 3) return msg(ui.friendMsg, 'Enter a username.');
    try { await api('/v1/friends/request', { method:'POST', body:JSON.stringify({ username }) }); ui.friendUsername.value=''; msg(ui.friendMsg, `Friend request sent to @${username}.`, true); await syncAll(); }
    catch (e) { msg(ui.friendMsg, e.message); }
  }

  window.ebeSocialAvatarSelected = async (dataUrl) => {
    msg(ui.friendMsg, 'Uploading profile picture…', true);
    try { const data = await api('/v1/profile/avatar', { method:'POST', body:JSON.stringify({ dataUrl }) }); me = data.user; renderProfile(); await syncAll(); msg(ui.friendMsg, 'Profile picture updated.', true); }
    catch (e) { msg(ui.friendMsg, e.message); }
  };
  window.ebeSocialAvatarError = (error) => msg(ui.friendMsg, error || 'Could not select picture.');

  function findKnownUser(username) { if (me?.username === username) return me; return [...friends.accepted, ...friends.incoming, ...friends.outgoing].find((u) => u.username === username) || rooms.map((r) => r.owner).find((u) => u?.username === username) || null; }
  let talkerAvatarWrap = null;
  function updateTalkerAvatar() {
    if (!talkerName) return;
    const text = String(talkerName.textContent || '').trim(); const suffix = ' — TRANSMITTING'; const talking = text.endsWith(suffix); const who = talking ? text.slice(0, -suffix.length).trim().toLowerCase() : '';
    if (!talkerAvatarWrap) {
      talkerAvatarWrap = document.createElement('div'); talkerAvatarWrap.className = 'talker-profile social-hidden';
      const av = document.createElement('div'); av.className = 'avatar'; av.id = 'socialTalkerAvatar';
      const label = document.createElement('span'); label.id = 'socialTalkerLabel'; label.style.fontSize='10px'; label.style.color='#a99db8'; talkerAvatarWrap.append(av,label); talkerName.parentNode?.appendChild(talkerAvatarWrap);
    }
    if (!talking) { talkerAvatarWrap.classList.add('social-hidden'); return; }
    const username = who === 'you' ? me?.username : who; const user = findKnownUser(username) || { username };
    fillAvatar($('socialTalkerAvatar'), user); $('socialTalkerLabel').textContent = '@' + (username || 'radio'); talkerAvatarWrap.classList.remove('social-hidden');
    if (username && username !== me?.username) { try { extras?.notifyTalker?.(username); } catch (_) {} }
  }

  ui.loginTab.addEventListener('click', () => setAuthMode('login')); ui.signupTab.addEventListener('click', () => setAuthMode('signup')); ui.authSubmit.addEventListener('click', submitAuth); ui.authPass.addEventListener('keydown', (e) => { if (e.key === 'Enter') submitAuth(); });
  ui.addFriend.addEventListener('click', addFriend); ui.friendUsername.addEventListener('keydown', (e) => { if (e.key === 'Enter') addFriend(); }); ui.newRoom.addEventListener('click', createNewRoom); ui.joinCodeBtn.addEventListener('click', joinSharedCode); ui.joinCode.addEventListener('keydown', (e) => { if (e.key === 'Enter') joinSharedCode(); });
  ui.changeAvatar.addEventListener('click', () => social.pickAvatar?.());
  ui.removeAvatar.addEventListener('click', async () => { try { const data=await api('/v1/profile/avatar',{method:'POST',body:JSON.stringify({dataUrl:''})}); me=data.user;renderProfile();await syncAll(); } catch(e){msg(ui.friendMsg,e.message);} });
  ui.logout.addEventListener('click', logout); ui.socialDisconnect.addEventListener('click', leaveCurrentRoom);

  if (talkerName) new MutationObserver(updateTalkerAvatar).observe(talkerName, { childList:true, characterData:true, subtree:true });
  if (statusValue) new MutationObserver(() => { if (String(statusValue.textContent || '').includes('ONLINE')) heartbeatPresence(); }).observe(statusValue, { childList:true, characterData:true,subtree:true });

  (async () => { if (!backendReady()) return showAuth('This build is missing its social backend URL.'); const restored = await restoreSession(); if (restored) await enterApp(); else showAuth(); })();
})();
