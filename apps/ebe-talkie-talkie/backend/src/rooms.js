import {
  PRESENCE_TTL_MS,
  fail,
  pbkdf2Hex,
  randomCode,
  randomSalt,
  readJson,
  respond,
  safeRoomName,
} from "./utils.js";

function visibilityFrom(value) {
  return value === "private" ? "private" : "friends";
}

export function listRooms(store, me) {
  const now = Date.now();
  const friendRows = store.sql.exec(
    `SELECT user_low,user_high FROM friendships
     WHERE status = 'accepted' AND (user_low = ? OR user_high = ?)`,
    me.id,
    me.id,
  ).toArray();
  const friendIds = new Set();
  for (const row of friendRows) friendIds.add(row.user_low === me.id ? row.user_high : row.user_low);
  const memberships = new Set(
    store.sql.exec("SELECT room_id FROM room_members WHERE user_id = ?", me.id).toArray().map((r) => r.room_id),
  );
  const presenceRows = store.sql.exec(
    "SELECT room_id, COUNT(*) AS n FROM presence WHERE last_seen > ? GROUP BY room_id",
    now - PRESENCE_TTL_MS,
  ).toArray();
  const presenceMap = new Map(presenceRows.map((r) => [r.room_id, Number(r.n)]));
  const rooms = [];
  for (const room of store.sql.exec("SELECT * FROM rooms ORDER BY updated_at DESC").toArray()) {
    const visible = room.owner_id === me.id || memberships.has(room.id) || (room.visibility === "friends" && friendIds.has(room.owner_id));
    if (visible) rooms.push(store.roomView(room, me.id, presenceMap));
  }
  return respond({ ok: true, rooms });
}

export async function createRoom(store, request, me) {
  const body = await readJson(request);
  const name = safeRoomName(body.name);
  const visibility = visibilityFrom(body.visibility);
  const locked = !!body.locked;
  const pin = String(body.pin || "").trim();
  if (!name) return fail("Room name is required");
  if (locked && (pin.length < 4 || pin.length > 12 || !/^\d+$/.test(pin))) {
    return fail("Room PIN must be 4-12 digits");
  }

  const requestedCode = String(body.code || "").trim().toUpperCase().replace(/[^A-Z0-9_-]/g, "");
  let code;
  if (requestedCode) {
    if (requestedCode.length < 8 || requestedCode.length > 64) return fail("Imported room code is invalid");
    if (store.roomByCode(requestedCode)) return fail("That room code is already registered", 409);
    code = requestedCode;
  } else {
    do code = randomCode(); while (store.roomByCode(code));
  }

  const roomId = crypto.randomUUID();
  const now = Date.now();
  let pinSalt = null;
  let pinHash = null;
  if (locked) {
    pinSalt = randomSalt();
    pinHash = await pbkdf2Hex(pin, pinSalt, 120_000);
  }
  store.sql.exec(
    `INSERT INTO rooms(id,owner_id,name,code,visibility,locked,pin_salt,pin_hash,created_at,updated_at)
     VALUES(?,?,?,?,?,?,?,?,?,?)`,
    roomId,
    me.id,
    name,
    code,
    visibility,
    locked ? 1 : 0,
    pinSalt,
    pinHash,
    now,
    now,
  );
  store.sql.exec("INSERT INTO room_members(room_id,user_id,joined_at) VALUES(?,?,?)", roomId, me.id, now);
  return respond({ ok: true, room: store.roomView(store.roomRow(roomId), me.id, new Map()) }, 201);
}

export async function joinRoom(store, request, me, roomId) {
  const room = store.roomRow(roomId);
  if (!room) return fail("Room not found", 404);
  const already = room.owner_id === me.id || store.isRoomMember(room.id, me.id);
  if (!already) {
    if (room.visibility !== "friends" || !store.areFriends(me.id, room.owner_id)) {
      return fail("You do not have access to this room", 403);
    }
    const body = await readJson(request);
    if (!(await store.verifyRoomPin(room, body.pin))) {
      return fail("Incorrect room PIN", 403, { pinRequired: !!room.locked });
    }
    store.sql.exec(
      "INSERT OR IGNORE INTO room_members(room_id,user_id,joined_at) VALUES(?,?,?)",
      room.id,
      me.id,
      Date.now(),
    );
  }
  return respond({ ok: true, room: store.roomView(room, me.id, new Map()) });
}

export async function joinByCode(store, request, me) {
  const body = await readJson(request);
  const code = String(body.code || "").trim().toUpperCase();
  const room = store.roomByCode(code);
  if (!room) return fail("Room code not found", 404);
  if (!(await store.verifyRoomPin(room, body.pin))) {
    return fail("Incorrect room PIN", 403, { pinRequired: !!room.locked });
  }
  store.sql.exec(
    "INSERT OR IGNORE INTO room_members(room_id,user_id,joined_at) VALUES(?,?,?)",
    room.id,
    me.id,
    Date.now(),
  );
  return respond({ ok: true, room: store.roomView(room, me.id, new Map()) });
}

export async function updateRoom(store, request, me, roomId) {
  const room = store.roomRow(roomId);
  if (!room) return fail("Room not found", 404);
  if (room.owner_id !== me.id) return fail("Only the room owner can change this room", 403);
  const body = await readJson(request);
  const name = body.name === undefined ? room.name : safeRoomName(body.name);
  if (!name) return fail("Room name is required");
  const visibility = body.visibility === undefined ? room.visibility : visibilityFrom(body.visibility);
  const locked = body.locked === undefined ? !!room.locked : !!body.locked;
  let pinSalt = room.pin_salt;
  let pinHash = room.pin_hash;
  if (!locked) {
    pinSalt = null;
    pinHash = null;
  } else if (body.pin !== undefined && String(body.pin).trim() !== "") {
    const pin = String(body.pin).trim();
    if (pin.length < 4 || pin.length > 12 || !/^\d+$/.test(pin)) return fail("Room PIN must be 4-12 digits");
    pinSalt = randomSalt();
    pinHash = await pbkdf2Hex(pin, pinSalt, 120_000);
  } else if (!room.locked) {
    return fail("A PIN is required when locking a room");
  }
  const now = Date.now();
  store.sql.exec(
    `UPDATE rooms SET name = ?, visibility = ?, locked = ?, pin_salt = ?, pin_hash = ?, updated_at = ? WHERE id = ?`,
    name,
    visibility,
    locked ? 1 : 0,
    pinSalt,
    pinHash,
    now,
    room.id,
  );
  return respond({ ok: true, room: store.roomView(store.roomRow(room.id), me.id, new Map()) });
}

export function deleteRoom(store, me, roomId) {
  const room = store.roomRow(roomId);
  if (!room) return fail("Room not found", 404);
  if (room.owner_id !== me.id) return fail("Only the room owner can delete this room", 403);
  store.sql.exec("DELETE FROM presence WHERE room_id = ?", room.id);
  store.sql.exec("DELETE FROM room_members WHERE room_id = ?", room.id);
  store.sql.exec("DELETE FROM rooms WHERE id = ?", room.id);
  return respond({ ok: true });
}

export async function heartbeat(store, request, me) {
  const body = await readJson(request);
  const roomId = String(body.roomId || "");
  const room = store.roomRow(roomId);
  if (!room || !(room.owner_id === me.id || store.isRoomMember(room.id, me.id))) {
    return fail("Join the room before sending presence", 403);
  }
  const now = Date.now();
  store.sql.exec("DELETE FROM presence WHERE user_id = ? AND room_id != ?", me.id, room.id);
  store.sql.exec(
    `INSERT INTO presence(room_id,user_id,last_seen) VALUES(?,?,?)
     ON CONFLICT(room_id,user_id) DO UPDATE SET last_seen = excluded.last_seen`,
    room.id,
    me.id,
    now,
  );
  return respond({ ok: true, at: now });
}

export async function leavePresence(store, request, me) {
  const body = await readJson(request);
  const roomId = String(body.roomId || "");
  store.sql.exec("DELETE FROM presence WHERE room_id = ? AND user_id = ?", roomId, me.id);
  return respond({ ok: true });
}
