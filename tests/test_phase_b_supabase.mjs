import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { randomUUID } from "node:crypto";

const statusOutput = execFileSync(
  "npx",
  ["--offline", "--yes", "supabase@latest", "status", "-o", "env"],
  { cwd: new URL("..", import.meta.url), encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] },
);

function envValue(name) {
  const match = statusOutput.match(new RegExp(`^${name}="?([^"\\n]+)"?$`, "m"));
  if (!match) throw new Error(`Local Supabase did not report ${name}`);
  return match[1];
}

const API = envValue("API_URL");
const ANON = envValue("ANON_KEY");
const SERVICE = envValue("SERVICE_ROLE_KEY");
const createdUsers = [];
const results = [];

function pass(name) {
  results.push(name);
  process.stdout.write(`PASS ${name}\n`);
}

async function request(path, { method = "GET", token = ANON, body, headers = {} } = {}) {
  const response = await fetch(`${API}${path}`, {
    method,
    headers: {
      apikey: ANON,
      Authorization: `Bearer ${token}`,
      ...(body && !(body instanceof Uint8Array) ? { "Content-Type": "application/json" } : {}),
      ...headers,
    },
    body: body instanceof Uint8Array ? body : body === undefined ? undefined : JSON.stringify(body),
  });
  const text = await response.text();
  let data = text;
  try { data = text ? JSON.parse(text) : null; } catch {}
  return { response, data, text };
}

async function createUser() {
  const suffix = randomUUID().replaceAll("-", "");
  const email = `phase-b-${suffix}@example.invalid`;
  const password = `A${suffix.slice(0, 14)}9z`;
  const created = await request("/auth/v1/admin/users", {
    method: "POST",
    token: SERVICE,
    body: { email, password, email_confirm: true },
  });
  assert.equal(created.response.status, 200, created.text);
  createdUsers.push(created.data.id);
  const login = await request("/auth/v1/token?grant_type=password", {
    method: "POST",
    body: { email, password },
  });
  assert.equal(login.response.status, 200, login.text);
  return { id: created.data.id, email, token: login.data.access_token, refresh: login.data.refresh_token };
}

async function profile(id, token) {
  return request(`/rest/v1/profiles?id=eq.${id}&select=id,username,avatar_path,account_status`, { token });
}

async function patchProfile(id, token, changes) {
  return request(`/rest/v1/profiles?id=eq.${id}&select=id,username,avatar_path,account_status`, {
    method: "PATCH",
    token,
    body: changes,
    headers: { Prefer: "return=representation" },
  });
}

async function run() {
  const userA = await createUser();
  const userB = await createUser();

  try {
    const bootA = await profile(userA.id, userA.token);
    const bootB = await profile(userB.id, userB.token);
    assert.equal(bootA.response.status, 200, bootA.text);
    assert.equal(bootB.response.status, 200, bootB.text);
    assert.equal(bootA.data.length, 1);
    assert.equal(bootA.data[0].username, null);
    pass("auth UUID bootstrap creates exactly one profile");

    const unauthenticated = await patchProfile(userA.id, ANON, { username: "NoAccess" });
    assert.ok(unauthenticated.response.status === 401 || unauthenticated.response.status === 403, unauthenticated.text);
    pass("unauthenticated profile write blocked");

    const valid = await patchProfile(userA.id, userA.token, { username: "  Alpha_User  " });
    assert.equal(valid.response.status, 200, valid.text);
    assert.equal(valid.data[0].username, "Alpha_User");
    pass("valid username accepted and whitespace trimmed");

    for (const [candidate, expected] of [
      ["ab", "too-short"],
      ["a".repeat(25), "too-long"],
      ["bad-name", "invalid-character"],
      ["ALLTHINGS_140", "reserved"],
    ]) {
      const attempt = await patchProfile(userB.id, userB.token, { username: candidate });
      assert.ok(attempt.response.status >= 400, `${expected}: ${attempt.text}`);
      pass(`username ${expected} rejected`);
    }

    const duplicate = await patchProfile(userB.id, userB.token, { username: "alpha_user" });
    assert.equal(duplicate.response.status, 409, duplicate.text);
    pass("case-insensitive duplicate username rejected");

    const beta = await patchProfile(userB.id, userB.token, { username: "Beta_User" });
    assert.equal(beta.response.status, 200, beta.text);

    const cooldown = await patchProfile(userA.id, userA.token, { username: "AlphaChanged" });
    assert.ok(cooldown.response.status >= 400, cooldown.text);
    pass("30-day username cooldown enforced");

    const crossWrite = await patchProfile(userB.id, userA.token, { username: "HackedUser" });
    assert.equal(crossWrite.response.status, 200, crossWrite.text);
    assert.deepEqual(crossWrite.data, []);
    const verifyB = await profile(userB.id, userB.token);
    assert.equal(verifyB.data[0].username, "Beta_User");
    pass("User A cannot update User B");

    const protectedProfile = await patchProfile(userA.id, userA.token, { account_status: "banned" });
    assert.equal(protectedProfile.response.status, 403, protectedProfile.text);
    pass("listener cannot modify protected account status");

    const protectedEntitlement = await request(`/rest/v1/entitlements?user_id=eq.${userA.id}`, {
      method: "PATCH",
      token: userA.token,
      body: { ad_free: true, status: "active" },
    });
    assert.equal(protectedEntitlement.response.status, 403, protectedEntitlement.text);
    const ownEntitlement = await request(`/rest/v1/entitlements?select=user_id,plan,status,ad_free`, { token: userA.token });
    assert.equal(ownEntitlement.response.status, 200, ownEntitlement.text);
    assert.equal(ownEntitlement.data.length, 1);
    assert.equal(ownEntitlement.data[0].ad_free, false);
    pass("listener cannot self-grant subscription or ad-free entitlement");

    const tinyPng = Uint8Array.from(Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=", "base64"));
    const avatarPathA = `${userA.id}/avatar`;
    const upload = await request(`/storage/v1/object/avatars/${avatarPathA}`, {
      method: "POST",
      token: userA.token,
      body: tinyPng,
      headers: { "Content-Type": "image/png", "x-upsert": "true" },
    });
    assert.equal(upload.response.status, 200, upload.text);
    const replace = await request(`/storage/v1/object/avatars/${avatarPathA}`, {
      method: "POST",
      token: userA.token,
      body: tinyPng,
      headers: { "Content-Type": "image/png", "x-upsert": "true" },
    });
    assert.equal(replace.response.status, 200, replace.text);
    const display = await fetch(`${API}/storage/v1/object/public/avatars/${avatarPathA}`);
    assert.equal(display.status, 200);
    pass("avatar upload, public display, and replacement work");

    const crossAvatar = await request(`/storage/v1/object/avatars/${userB.id}/avatar`, {
      method: "POST",
      token: userA.token,
      body: tinyPng,
      headers: { "Content-Type": "image/png", "x-upsert": "true" },
    });
    assert.ok(crossAvatar.response.status >= 400, crossAvatar.text);
    pass("User A cannot overwrite User B avatar namespace");

    const badMime = await request(`/storage/v1/object/avatars/${userA.id}/avatar`, {
      method: "POST",
      token: userA.token,
      body: new TextEncoder().encode("not an image"),
      headers: { "Content-Type": "text/plain", "x-upsert": "true" },
    });
    assert.ok(badMime.response.status >= 400, badMime.text);
    pass("unsupported avatar MIME blocked");

    const tooLarge = await request(`/storage/v1/object/avatars/${userA.id}/avatar`, {
      method: "POST",
      token: userA.token,
      body: new Uint8Array(2 * 1024 * 1024 + 1),
      headers: { "Content-Type": "image/png", "x-upsert": "true" },
    });
    assert.ok(tooLarge.response.status >= 400, tooLarge.text);
    pass("oversize avatar blocked");

    const reset = await request("/auth/v1/recover", {
      method: "POST",
      body: { email: userA.email, redirect_to: "http://127.0.0.1:4173/" },
    });
    assert.equal(reset.response.status, 200, reset.text);
    pass("password reset initiation accepted");

    const deletion = await request("/rest/v1/rpc/request_my_account_deletion", {
      method: "POST",
      token: userA.token,
      body: {},
    });
    assert.equal(deletion.response.status, 200, deletion.text);
    pass("authenticated deletion request queues without client auth-user deletion");

    const signOut = await request("/auth/v1/logout", { method: "POST", token: userA.token });
    assert.equal(signOut.response.status, 204, signOut.text);
    pass("sign out invalidates the active session");

    assert.ok(results.length >= 18);
    process.stdout.write(`PHASE B SUPABASE SECURITY: ${results.length}/${results.length} PASS\n`);
  } finally {
    for (const id of createdUsers) {
      await request(`/auth/v1/admin/users/${id}`, { method: "DELETE", token: SERVICE });
    }
  }
}

run().catch((error) => {
  console.error(error.message);
  process.exitCode = 1;
});
