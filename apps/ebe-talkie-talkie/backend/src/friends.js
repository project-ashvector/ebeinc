import { fail, normalizeUsername, pairFor, publicUser, readJson, respond } from "./utils.js";

export function listFriends(store, me) {
  const rows = store.sql.exec(
    "SELECT * FROM friendships WHERE user_low = ? OR user_high = ? ORDER BY updated_at DESC",
    me.id,
    me.id,
  ).toArray();
  const accepted = [];
  const incoming = [];
  const outgoing = [];
  for (const row of rows) {
    const otherId = row.user_low === me.id ? row.user_high : row.user_low;
    const other = publicUser(store.getUserById(otherId));
    if (!other) continue;
    if (row.status === "accepted") accepted.push(other);
    else if (row.requested_by === me.id) outgoing.push(other);
    else incoming.push(other);
  }
  return respond({ ok: true, accepted, incoming, outgoing });
}

export async function requestFriend(store, request, me) {
  const body = await readJson(request);
  const username = normalizeUsername(body.username);
  const other = store.getUserByUsername(username);
  if (!other) return fail("User not found", 404);
  if (other.id === me.id) return fail("You cannot add yourself");
  const [low, high] = pairFor(me.id, other.id);
  const existing = store.sql.exec(
    "SELECT * FROM friendships WHERE user_low = ? AND user_high = ? LIMIT 1",
    low,
    high,
  ).toArray()[0];
  if (existing?.status === "accepted") return fail("Already friends", 409);
  if (existing?.status === "pending") {
    return fail(
      existing.requested_by === me.id ? "Friend request already sent" : "This user already sent you a friend request",
      409,
      { incoming: existing.requested_by !== me.id },
    );
  }
  const now = Date.now();
  store.sql.exec(
    `INSERT INTO friendships(user_low,user_high,status,requested_by,created_at,updated_at)
     VALUES(?,?,?,?,?,?)`,
    low,
    high,
    "pending",
    me.id,
    now,
    now,
  );
  return respond({ ok: true, requested: publicUser(other) }, 201);
}

export async function acceptFriend(store, request, me) {
  const body = await readJson(request);
  const other = store.getUserByUsername(normalizeUsername(body.username));
  if (!other) return fail("User not found", 404);
  const [low, high] = pairFor(me.id, other.id);
  const existing = store.sql.exec(
    "SELECT * FROM friendships WHERE user_low = ? AND user_high = ? LIMIT 1",
    low,
    high,
  ).toArray()[0];
  if (!existing || existing.status !== "pending" || existing.requested_by === me.id) {
    return fail("No incoming friend request", 404);
  }
  store.sql.exec(
    "UPDATE friendships SET status = 'accepted', updated_at = ? WHERE user_low = ? AND user_high = ?",
    Date.now(),
    low,
    high,
  );
  return respond({ ok: true, friend: publicUser(other) });
}

export async function removeFriend(store, request, me) {
  const body = await readJson(request);
  const other = store.getUserByUsername(normalizeUsername(body.username));
  if (!other) return fail("User not found", 404);
  const [low, high] = pairFor(me.id, other.id);
  store.sql.exec("DELETE FROM friendships WHERE user_low = ? AND user_high = ?", low, high);
  return respond({ ok: true });
}
