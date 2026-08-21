import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), "utf8");
const shell = read("radio/persistent-shell.html");
const auth = read("radio/persistent-auth.js");
const config = read("radio/supabase-config.js");
const css = read("radio/persistent-shell.css");
const headers = read("radio/_headers");
const migration = read("supabase/migrations/20260821063612_universal_account_profile_foundation.sql");
const sw = read("radio/sw.js");
const swCompat = read("radio/sw-v47.js");

const checks = [];
function check(name, condition) {
  assert.ok(condition, name);
  checks.push(name);
  console.log(`✓ ${name}`);
}

check("Supabase Auth uses one shell-level client", (auth.match(/sdk\.createClient\(/g) || []).length === 1);
check("exactly one primary auth-state listener exists", (auth.match(/\.onAuthStateChange\(/g) || []).length === 1);
check("one sanitized AT140Auth authority is exposed", auth.includes("window.AT140Auth = Object.freeze") && auth.includes("syncRoute"));
check("route identity contract omits access and refresh tokens", !/access_token|refresh_token|service_role/i.test(auth));
check("account UI is owned by persistent shell", shell.includes('id="accountShell"') && shell.includes('id="accountDialog"'));
check("email sign-up, sign-in, sign-out, reset, and recovery are wired", ["signUp", "signInWithPassword", "signOut", "resetPasswordForEmail", "updateUser"].every((term) => auth.includes(term)));
check("Google application integration point exists without pretending provider readiness", auth.includes('provider: provider === "soundcloud" ? "custom:soundcloud" : provider') && config.includes("googleEnabled: false"));
check("SoundCloud is explicitly foundation-only", config.includes("soundCloudEnabled: false") && shell.includes("FOUNDATION ONLY"));
check("profile avatar upload is normalized and ownership-keyed", auth.includes('canvas.toBlob(resolve, "image/webp"') && auth.includes("`${user.id}/avatar`"));
check("mobile account UI has a dedicated 600px layout", css.includes("@media(max-width:600px)") && css.includes("bottom:max(10px,env(safe-area-inset-bottom))"));
const shellCsp = headers.split("/persistent-shell.html")[1].split("\n\n")[0];
check("CSP allows only the exact Supabase project origins", shellCsp.includes("https://dtvnlpgtmrbnpecsapsv.supabase.co") && !shellCsp.match(/connect-src[^\n]*\*/));
check("no privileged Supabase key is present in browser configuration", !/sb_secret_|service[_-]?role[^\n]*[:=][^\n]+/i.test(config));
check("profiles use auth.users UUID primary key", migration.includes("id uuid primary key references auth.users(id) on delete cascade"));
check("case-insensitive username uniqueness is database-enforced", migration.includes("profiles_username_casefold_unique") && migration.includes("lower(username)"));
check("reserved username skeletons are server-managed", migration.includes("reserved_usernames") && migration.includes("username_skeleton"));
check("username change cooldown is database-enforced", migration.includes("interval '30 days'") && migration.includes("username_cooldown"));
check("profile bootstrap is idempotent for email and OAuth users", migration.includes("auth_user_profile_bootstrap") && migration.includes("on conflict (id) do nothing"));
check("protected profile columns have no authenticated update grant", migration.includes("grant update (username, avatar_path)") && !migration.includes("grant update (account_status"));
check("roles are isolated in a protected table", migration.includes("create table public.user_roles") && migration.includes("revoke all on table public.user_roles"));
check("entitlements are server-write-only and owner-readable", migration.includes("entitlements_owner_read") && !migration.match(/grant (insert|update|delete)[^;]*entitlements/i));
check("avatar bucket restricts size and MIME", migration.includes("2097152") && ["image/jpeg", "image/png", "image/webp"].every((mime) => migration.includes(mime)));
check("avatar RLS binds every write to auth UID path", ["avatar_owner_insert", "avatar_owner_update", "avatar_owner_delete"].every((name) => migration.includes(name)) && migration.includes("auth.uid()::text || '/avatar'"));
check("account deletion is queued for privileged processing", migration.includes("request_my_account_deletion") && migration.includes("secure server/Edge Function"));
check("Terms enforcement is not falsely activated", auth.includes("PENDING LEGAL/UGC PHASE") && migration.includes("terms_accepted_at"));
check("auth assets are cached without touching stream exclusions", sw.includes("persistent-auth.js?v=1.0.0") && sw.includes("vendor-supabase-2.112.3.min.js") && sw.includes("mp3|m3u8"));
check("both service-worker entry files remain synchronized", sw === swCompat);

console.log(`Phase B profile-foundation contract: ${checks.length} checks passed.`);
