# Authentication / Accounts

## Listener accounts (public)

- **Provider:** Supabase (`dtvnlpgtmrbnpecsapsv.supabase.co`)
- **Client:** `radio/persistent-auth.js`, Android `SupabaseAuthClient.java`
- **Entitlement RPC:** `account_role_state` (server-authoritative, not cached as privilege)
- **Roles:** REGULAR, PLUS, RESIDENT, PARTNER/SPONSOR, MODERATOR, ADMIN via migrations

## DJ / station accounts (private)

- SQLite `users` table with password hashes
- 2 accounts on production (admin, manager roles)
- Used by DJ desktop tools and private API — not listener-facing

## Cross-device

- Supabase refresh token flow in Android + web
- Token refresh on `TOKEN_REFRESHED` re-resolves entitlements (web)

## Security posture

- Privileged alert preference tables revoked from `anon, authenticated` (migrations verified)
- No destructive auth testing performed

**Status: PARTIAL** (live login flows not exercised)
