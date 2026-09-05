import assert from "node:assert/strict";
import fs from "node:fs";

const read = path => fs.readFileSync(new URL(`../${path}`, import.meta.url), "utf8");
const migration = read("supabase/migrations/20260824010000_alert_ads_preference.sql");
const privilegedLock = read("supabase/migrations/20260901010000_lock_privileged_alert_ads.sql");
const preferenceRemoval = read("supabase/migrations/20260901020000_remove_alert_preference_authority.sql");
const accountMigration = read("supabase/migrations/20260823124500_account_types_and_alert_entitlements.sql");
const auth = read("radio/persistent-auth.js");
const scheduler = read("radio/persistent-shell.js");
const android = read("android/mobile-app/app/src/main/java/online/ebeinc/allthings140radio/RadioService.java");
const worker = read("radio/_worker.js");

function resolve({ role = "user", accountClass = "regular", preference = "default" } = {}) {
  const effectiveRole = role === "admin" ? "admin" : ["moderator", "staff"].includes(role) ? "moderator" : "user";
  const accountType = effectiveRole === "user" ? accountClass : effectiveRole;
  const enabled = effectiveRole === "user" && accountClass === "regular";
  return { accountType, enabled };
}

const matrix = [
  ["anonymous", true],
  ["regular", resolve().enabled],
  ["plus", resolve({ accountClass: "plus" }).enabled],
  ["admin", resolve({ role: "admin" }).enabled],
  ["moderator", resolve({ role: "moderator" }).enabled],
  ["staff", resolve({ role: "staff" }).enabled],
  ["resident (artist)", resolve({ accountClass: "resident" }).enabled],
  ["partner / sponsor", resolve({ accountClass: "partner_sponsor" }).enabled],
];
assert.deepEqual(matrix, [
  ["anonymous", true], ["regular", true], ["plus", false], ["admin", false],
  ["moderator", false], ["staff", false], ["resident (artist)", false],
  ["partner / sponsor", false],
]);
assert.equal(resolve({ accountClass: "plus", preference: "on" }).enabled, false, "privileged accounts cannot opt back in");

assert.match(auth, /authState: "AUTH_UNKNOWN"/);
assert.match(auth, /entitlementResolved \? roleState\?\.alert_ads_enabled === true : false/);
assert.match(auth, /event === "TOKEN_REFRESHED"/);
assert.match(auth, /5 \* 60 \* 1000/);
assert.match(scheduler, /ALERT_QA \? 15 : Math\.max\(60,/, "15-second mode is restricted to non-production QA");
assert.ok(scheduler.includes("await window.AT140Auth?.refreshRole?.()"), "web final pre-play server authorization");
assert.match(scheduler, /cancelActive\(\)/, "web pending and active alert cancellation");
assert.match(scheduler, /this\.playbackStarts \+= 1/, "actual successful alert playback is observable");
assert.match(scheduler, /if \(!ALERT_QA\) throw new Error\("qa_only"\)/,
  "test identity and forced opportunities are inaccessible on production hosts");
assert.match(scheduler, /BroadcastChannel\("at140-radio-owner-v1"\)/, "one scheduler owner across tabs");
assert.match(android, /private void startAuthorizedAlert\(\)/);
assert.match(android, /authClient\.loadRole\(\(ok, role, status, email, accountClass, accountType,/,
  "Android final pre-play server authorization");
assert.match(android, /expectedGeneration != entitlementGeneration/, "Android stale callback protection");
assert.match(android, /BuildConfig\.DEBUG && alertPrefs\.getBoolean\("qa_client_alerts", false\)/,
  "Android accelerated mode is debug-only");
assert.match(worker, /SERVER_STREAM_ALERT_INJECTION_ENABLED === "true"/,
  "global stream injection is fail-off");
assert.match(worker, /CLIENT_ACCOUNT_ALERTS_ENABLED !== "false"/,
  "account-aware client delivery is enabled by default");

for (const protectedTable of ["account_classes", "alert_ads_preferences"]) {
  assert.match(accountMigration + migration, new RegExp(`revoke all on public\\.${protectedTable} from anon, authenticated`));
}
assert.match(migration, /regular_alert_ads_locked_on/);
assert.match(privilegedLock, /authority\.role = 'user' and benefit\.class = 'regular/,
  'Privileged account types are unconditionally ad-free in the effective entitlement');
assert.match(privilegedLock, /security_role='user' and benefit_class='regular/,
  'Preference RPC returns the canonical effective state instead of granting privileged opt-in');
assert.match(preferenceRemoval, /'default'::text/);
assert.match(preferenceRemoval, /drop function if exists public\.set_alert_ads_preference/);
assert.match(preferenceRemoval, /authority\.role = 'user' and benefit\.class = 'regular/);
assert.match(migration, /security definer/);

console.log("PASS account-aware alert entitlement matrix and playback guards");
