import { DurableObject } from "cloudflare:workers";
import { initSchema } from "./schema.js";
import {
  MAX_AVATAR_CHARS,
  PRESENCE_TTL_MS,
  SESSION_TTL_MS,
  USER_RE,
  fail,
  normalizeUsername,
  pbkdf2Hex,
  publicUser,
  randomSalt,
  randomToken,
  readJson,
  respond,
  sha256Hex,
  timingSafeEqualHex,
} from "./utils.js";
import { acceptFriend, listFriends, removeFriend, requestFriend } from "./friends.js";
import { createRoom, deleteRoom, heartbeat, joinByCode, joinRoom, leavePresence, listRooms, updateRoom } from "./rooms.js";

export class SocialStore extends DurableObject {
  constructor(ctx, env) {
    super(ctx, env);
    this.sql = ctx.storage.sql;
    this.rate = new Map();
    initSchema(this.sql);
  }

  rateLimit(request, bucket = "default", limit = 40, windowMs = 60_000) {
    const ip = request.headers.get("cf-connecting-ip") || "unknown";
    const key = `${bucket}:${ip}`;
    const now = Date.now();
    const current = this.rate.get(key);
    if (!current || current.resetAt <= now) {
      this.rate.set(key, { count: 1, resetAt: now + windowMs });
      return true;
    }
    current.count += 1;
    if (current.count > limit) return false;
    if (this.rate.size > 500) {
      for (const [k, v] of this.rate) if (v.resetAt <= now) this.rate.delete(k);
    }
    return true;
  }

  cleanup(now = Date.now()) {
    this.sql.exec("DELETE FROM sessions WHERE expires_at <= ?", now);
    this.sql.exec("DELETE FROM presence WHERE last_seen <= ?", now - PRESENCE_TTL_MS * 3);
  }

  getUserByUsername(username) {
    return this.sql.exec(
      "SELECT id,username,avatar_data_url,avatar_version,password_salt,password_hash FROM users WHERE username = ? LIMIT 1",
      username,
    ).toArray()[0] || null;
  }

  getUserById(id) {
    return this.sql.exec(
      "SELECT id,username,avatar_data_url,avatar_version FROM users WHERE id = ? LIMIT 1",
      id,
    ).toArray()[0] || null;
  }

  areFriends(a, b) {
    const low = a < b ? a : b;
    const high = a < b ? b : a;
    const row = this.sql.exec(
      "SELECT status FROM friendships WHERE user_low = ? AND user_high = ? LIMIT 1",
      low,
      high,
    ).toArray()[0];
    return row?.status === "accepted";
  }

  isRoomMember(roomId, userId) {
    return !!this.sql.exec(
      "SELECT 1 AS ok FROM room_members WHERE room_id = ? AND user_id = ? LIMIT 1",
      roomId,
      userId,
    ).toArray()[0];
  }

  roomRow(roomId) {
    return this.sql.exec("SELECT * FROM rooms WHERE id = ? LIMIT 1", roomId).toArray()[0] || null;
  }

  roomByCode(code) {
    return this.sql.exec("SELECT * FROM rooms WHERE code = ? LIMIT 1", code).toArray()[0] || null;
  }

  roomView(room, userId, presenceMap) {
    const owner = this.getUserById(room.owner_id);
    const joined = room.owner_id === userId || this.isRoomMember(room.id, userId);
    return {
      id: room.id,
      name: room.name,
      owner: publicUser(owner),
      visibility: room.visibility,
      locked: !!room.locked,
      joined,
      mine: room.owner_id === userId,
      code: joined ? room.code : "",
      online: Number(presenceMap.get(room.id) || 0),
      createdAt: Number(room.created_at),
      updatedAt: Number(room.updated_at),
    };
  }

  async verifyRoomPin(room, pin) {
    if (!room.locked) return true;
    const candidate = String(pin || "").trim();
    if (!candidate || !room.pin_salt || !room.pin_hash) return false;
    const hash = await pbkdf2Hex(candidate, room.pin_salt, 120_000);
    return timingSafeEqualHex(hash, room.pin_hash);
  }

  async auth(request) {
    const header = request.headers.get("authorization") || "";
    const match = header.match(/^Bearer\s+(.+)$/i);
    if (!match) return null;
    const tokenHash = await sha256Hex(match[1]);
    const rows = this.sql.exec(
      `SELECT u.id,u.username,u.avatar_data_url,u.avatar_version,s.expires_at
       FROM sessions s JOIN users u ON u.id=s.user_id
       WHERE s.token_hash=? AND s.expires_at>? LIMIT 1`,
      tokenHash,
      Date.now(),
    ).toArray();
    return rows[0] || null;
  }

  async issueSession(userId) {
    const token = randomToken();
    const tokenHash = await sha256Hex(token);
    const now = Date.now();
    const expiresAt = now + SESSION_TTL_MS;
    this.sql.exec(
      "INSERT INTO sessions(token_hash,user_id,created_at,expires_at) VALUES(?,?,?,?)",
      tokenHash,
      userId,
      now,
      expiresAt,
    );
    return { token, expiresAt };
  }

  async signup(request) {
    if (!this.rateLimit(request, "signup", 12, 10 * 60_000)) return fail("Too many signup attempts", 429);
    const body = await readJson(request);
    const username = normalizeUsername(body.username);
    const password = String(body.password || "");
    if (!USER_RE.test(username)) return fail("Username must be 3-24 characters using letters, numbers, or underscore");
    if (password.length < 6 || password.length > 128) return fail("Password must be 6-128 characters");
    if (this.getUserByUsername(username)) return fail("Username is already taken", 409);

    const salt = randomSalt();
    const hash = await pbkdf2Hex(password, salt);
    const id = crypto.randomUUID();
    const now = Date.now();
    this.sql.exec(
      "INSERT INTO users(id,username,password_salt,password_hash,created_at,updated_at) VALUES(?,?,?,?,?,?)",
      id,
      username,
      salt,
      hash,
      now,
      now,
    );
    const session = await this.issueSession(id);
    return respond({ ok: true, token: session.token, expiresAt: session.expiresAt, user: publicUser(this.getUserById(id)) }, 201);
  }

  async login(request) {
    if (!this.rateLimit(request, "login", 30, 10 * 60_000)) return fail("Too many login attempts", 429);
    const body = await readJson(request);
    const username = normalizeUsername(body.username);
    const password = String(body.password || "");
    const row = this.getUserByUsername(username);
    if (!row || !password) return fail("Invalid username or password", 401);
    const hash = await pbkdf2Hex(password, row.password_salt);
    if (!timingSafeEqualHex(hash, row.password_hash)) return fail("Invalid username or password", 401);
    const session = await this.issueSession(row.id);
    return respond({ ok: true, token: session.token, expiresAt: session.expiresAt, user: publicUser(row) });
  }

  async logout(request) {
    const header = request.headers.get("authorization") || "";
    const match = header.match(/^Bearer\s+(.+)$/i);
    if (match) this.sql.exec("DELETE FROM sessions WHERE token_hash = ?", await sha256Hex(match[1]));
    return respond({ ok: true });
  }

  async updateAvatar(request, me) {
    const body = await readJson(request);
    const dataUrl = String(body.dataUrl || "");
    if (dataUrl && !/^data:image\/(jpeg|png|webp);base64,/i.test(dataUrl)) return fail("Unsupported image format");
    if (dataUrl.length > MAX_AVATAR_CHARS) return fail("Profile picture is too large");
    if (dataUrl) {
      try {
        const b64 = dataUrl.slice(dataUrl.indexOf(",") + 1);
        if (atob(b64).length > 140_000) return fail("Profile picture must be under 140 KB after compression");
      } catch (_) {
        return fail("Invalid profile picture");
      }
    }
    this.sql.exec(
      "UPDATE users SET avatar_data_url=?,avatar_version=avatar_version+1,updated_at=? WHERE id=?",
      dataUrl,
      Date.now(),
      me.id,
    );
    return respond({ ok: true, user: publicUser(this.getUserById(me.id)) });
  }

  searchUsers(url, me) {
    const q = normalizeUsername(url.searchParams.get("q") || "");
    if (q.length < 2) return respond({ ok: true, users: [] });
    const rows = this.sql.exec(
      `SELECT id,username,avatar_data_url,avatar_version FROM users
       WHERE username LIKE ? AND id != ? ORDER BY username LIMIT 20`,
      `${q}%`,
      me.id,
    ).toArray();
    return respond({ ok: true, users: rows.map(publicUser) });
  }

  async fetch(request) {
    try {
      const url = new URL(request.url);
      const path = url.pathname.replace(/\/+$/, "") || "/";
      if (path === "/health" && request.method === "GET") return respond({ ok: true, service: "EBE Talkie Talkie Social", version: "0.2.0" });
      if (path === "/__selftest" && request.method === "GET") return respond({ ok: this.sql.exec("SELECT 140 AS value").one().value === 140, sqlite: true });
      this.cleanup();

      if (path === "/v1/signup" && request.method === "POST") return this.signup(request);
      if (path === "/v1/login" && request.method === "POST") return this.login(request);

      const me = await this.auth(request);
      if (!me) return fail("Authentication required", 401);

      if (path === "/v1/logout" && request.method === "POST") return this.logout(request);
      if (path === "/v1/me" && request.method === "GET") return respond({ ok: true, user: publicUser(me) });
      if (path === "/v1/profile/avatar" && request.method === "POST") return this.updateAvatar(request, me);
      if (path === "/v1/users/search" && request.method === "GET") return this.searchUsers(url, me);

      if (path === "/v1/friends" && request.method === "GET") return listFriends(this, me);
      if (path === "/v1/friends/request" && request.method === "POST") return requestFriend(this, request, me);
      if (path === "/v1/friends/accept" && request.method === "POST") return acceptFriend(this, request, me);
      if (path === "/v1/friends/remove" && request.method === "POST") return removeFriend(this, request, me);

      if (path === "/v1/rooms" && request.method === "GET") return listRooms(this, me);
      if (path === "/v1/rooms" && request.method === "POST") return createRoom(this, request, me);
      if (path === "/v1/rooms/join-code" && request.method === "POST") return joinByCode(this, request, me);

      const roomMatch = path.match(/^\/v1\/rooms\/([a-zA-Z0-9-]+)$/);
      if (roomMatch && request.method === "PATCH") return updateRoom(this, request, me, roomMatch[1]);
      if (roomMatch && request.method === "DELETE") return deleteRoom(this, me, roomMatch[1]);
      const joinMatch = path.match(/^\/v1\/rooms\/([a-zA-Z0-9-]+)\/join$/);
      if (joinMatch && request.method === "POST") return joinRoom(this, request, me, joinMatch[1]);

      if (path === "/v1/presence" && request.method === "POST") return heartbeat(this, request, me);
      if (path === "/v1/presence/leave" && request.method === "POST") return leavePresence(this, request, me);
      return fail("Not found", 404);
    } catch (error) {
      console.error(error);
      return fail("Server error", 500);
    }
  }
}
