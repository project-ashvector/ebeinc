import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { randomUUID } from "node:crypto";

const API = "https://dtvnlpgtmrbnpecsapsv.supabase.co";
const browserConfig = readFileSync(new URL("../radio/supabase-config.js", import.meta.url), "utf8");
const keyMatch = browserConfig.match(/publishableKey:\s*"([^"]+)"/);
assert.ok(keyMatch, "publishable key missing from browser-safe config");
const KEY = keyMatch[1];
const credentials = JSON.parse(readFileSync("/tmp/at140-phase-b-remote-users.json", "utf8"));
assert.equal(credentials.length, 2, "two ephemeral remote users are required");

async function request(path, { method = "GET", token = KEY, body, headers = {} } = {}) {
  const binary = body instanceof Uint8Array;
  const response = await fetch(`${API}${path}`, {
    method,
    headers: {
      apikey: KEY,
      Authorization: `Bearer ${token}`,
      ...(body !== undefined && !binary ? { "Content-Type": "application/json" } : {}),
      ...headers,
    },
    body: binary ? body : body === undefined ? undefined : JSON.stringify(body),
  });
  const text = await response.text();
  let data = text;
  try { data = text ? JSON.parse(text) : null; } catch {}
  return { response, data, text };
}

async function login({ email, password }) {
  const result = await request("/auth/v1/token?grant_type=password", { method: "POST", body: { email, password } });
  assert.equal(result.response.status, 200, "ephemeral hosted email/password sign-in failed");
  return { id: result.data.user.id, token: result.data.access_token };
}

function pass(name) { console.log(`PASS ${name}`); }

const userA = await login(credentials[0]);
const userB = await login(credentials[1]);
pass("hosted email/password sign-in for two isolated users");

const suffix = randomUUID().replaceAll("-", "").slice(0, 8);
const alpha = `Alpha_${suffix}`;
const beta = `Beta_${suffix}`;

async function patchProfile(id, token, changes) {
  return request(`/rest/v1/profiles?id=eq.${id}&select=id,username,avatar_path,account_status`, {
    method: "PATCH", token, body: changes, headers: { Prefer: "return=representation" },
  });
}

const profileA = await request(`/rest/v1/profiles?id=eq.${userA.id}&select=id,username`, { token: userA.token });
assert.equal(profileA.response.status, 200, profileA.text);
assert.equal(profileA.data.length, 1);
pass("hosted auth trigger bootstrapped profile by UUID");

const setA = await patchProfile(userA.id, userA.token, { username: `  ${alpha}  ` });
assert.equal(setA.response.status, 200, setA.text);
assert.equal(setA.data[0].username, alpha);
pass("hosted username normalization works");

const duplicate = await patchProfile(userB.id, userB.token, { username: alpha.toLowerCase() });
assert.equal(duplicate.response.status, 409, duplicate.text);
pass("hosted case-insensitive uniqueness works");

for (const candidate of ["ab", "bad-name", "ALLTHINGS_140"]) {
  const invalid = await patchProfile(userB.id, userB.token, { username: candidate });
  assert.ok(invalid.response.status >= 400, invalid.text);
}
pass("hosted length, character, and reserved-name rules work");

const setB = await patchProfile(userB.id, userB.token, { username: beta });
assert.equal(setB.response.status, 200, setB.text);

const cross = await patchProfile(userB.id, userA.token, { username: `Hack_${suffix}` });
assert.equal(cross.response.status, 200, cross.text);
assert.deepEqual(cross.data, []);
pass("hosted User A cannot update User B");

const statusWrite = await patchProfile(userA.id, userA.token, { account_status: "banned" });
assert.equal(statusWrite.response.status, 403, statusWrite.text);
pass("hosted protected account status is not client-writable");

const entitlementWrite = await request(`/rest/v1/entitlements?user_id=eq.${userA.id}`, {
  method: "PATCH", token: userA.token, body: { ad_free: true, status: "active" },
});
assert.equal(entitlementWrite.response.status, 403, entitlementWrite.text);
pass("hosted subscription/ad-free truth is not client-writable");

const png = Uint8Array.from(Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=", "base64"));
const pathA = `${userA.id}/avatar`;
const upload = await request(`/storage/v1/object/avatars/${pathA}`, {
  method: "POST", token: userA.token, body: png, headers: { "Content-Type": "image/png", "x-upsert": "true" },
});
assert.equal(upload.response.status, 200, upload.text);
const publicAvatar = await fetch(`${API}/storage/v1/object/public/avatars/${pathA}`);
assert.equal(publicAvatar.status, 200);
pass("hosted avatar upload and public display work");

const crossAvatar = await request(`/storage/v1/object/avatars/${userB.id}/avatar`, {
  method: "POST", token: userA.token, body: png, headers: { "Content-Type": "image/png", "x-upsert": "true" },
});
assert.ok(crossAvatar.response.status >= 400, crossAvatar.text);
pass("hosted avatar namespace ownership blocks User A to User B");

const badMime = await request(`/storage/v1/object/avatars/${pathA}`, {
  method: "POST", token: userA.token, body: new TextEncoder().encode("not image"), headers: { "Content-Type": "text/plain", "x-upsert": "true" },
});
assert.ok(badMime.response.status >= 400, badMime.text);
pass("hosted avatar MIME restriction works");

const deleteAvatar = await request(`/storage/v1/object/avatars/${pathA}`, { method: "DELETE", token: userA.token });
assert.equal(deleteAvatar.response.status, 200, deleteAvatar.text);
pass("hosted avatar owner deletion works");

console.log("PHASE B HOSTED SECURITY: 12/12 PASS");
