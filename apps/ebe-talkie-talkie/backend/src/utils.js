export const CORS = {
  "access-control-allow-origin": "*",
  "access-control-allow-methods": "GET,POST,PATCH,DELETE,OPTIONS",
  "access-control-allow-headers": "authorization,content-type",
  "access-control-max-age": "86400",
};
export const SESSION_TTL_MS = 30 * 24 * 60 * 60 * 1000;
export const PRESENCE_TTL_MS = 35_000;
export const MAX_AVATAR_CHARS = 190_000;
export const USER_RE = /^[a-z0-9_]{3,24}$/;
const ROOM_NAME_MAX = 48;
const ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";

const JSON_HEADERS = { ...CORS, "content-type": "application/json; charset=utf-8", "cache-control": "no-store" };

export function respond(data, status = 200) {
  return new Response(JSON.stringify(data), { status, headers: JSON_HEADERS });
}
export function empty(status = 204) {
  return new Response(null, { status, headers: CORS });
}
export function fail(message, status = 400, extra = {}) {
  return respond({ ok: false, error: message, ...extra }, status);
}
export function normalizeUsername(value) {
  return String(value || "").trim().toLowerCase();
}
export function safeRoomName(value) {
  return String(value || "").trim().replace(/[\r\n\t]+/g, " ").slice(0, ROOM_NAME_MAX);
}
export function pairFor(a, b) {
  return a < b ? [a, b] : [b, a];
}
export function publicUser(row) {
  if (!row) return null;
  return {
    id: row.id,
    username: row.username,
    avatar: row.avatar_data_url || "",
    avatarVersion: Number(row.avatar_version || 0),
  };
}
function toHex(bytes) {
  return [...bytes].map((b) => b.toString(16).padStart(2, "0")).join("");
}
function randomBytes(length) {
  const out = new Uint8Array(length);
  crypto.getRandomValues(out);
  return out;
}
function b64url(bytes) {
  let raw = "";
  for (const b of bytes) raw += String.fromCharCode(b);
  return btoa(raw).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}
export function randomSalt() {
  return b64url(randomBytes(18));
}
export function randomToken() {
  return b64url(randomBytes(32));
}
export function randomCode() {
  let out = "EBE";
  for (let group = 0; group < 3; group++) {
    out += "-";
    for (let i = 0; i < 4; i++) out += ALPHABET[Math.floor(Math.random() * ALPHABET.length)];
  }
  return out;
}
export async function sha256Hex(value) {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(String(value)));
  return toHex(new Uint8Array(digest));
}
export async function pbkdf2Hex(secret, salt, iterations = 210_000) {
  const enc = new TextEncoder();
  const key = await crypto.subtle.importKey("raw", enc.encode(secret), "PBKDF2", false, ["deriveBits"]);
  const bits = await crypto.subtle.deriveBits({ name: "PBKDF2", hash: "SHA-256", salt: enc.encode(salt), iterations }, key, 256);
  return toHex(new Uint8Array(bits));
}
export function timingSafeEqualHex(a, b) {
  if (!a || !b || a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}
export async function readJson(request) {
  const type = request.headers.get("content-type") || "";
  if (!type.includes("application/json")) throw new Error("JSON body required");
  return request.json();
}
