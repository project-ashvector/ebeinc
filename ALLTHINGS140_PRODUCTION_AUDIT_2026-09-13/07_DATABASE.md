# Database Audit

- **Path:** `/var/lib/allthings140radio/station.db` (2.2M)
- **Integrity:** `PRAGMA integrity_check` → **ok**
- **Tables:** 23 (tracks, takeovers, users, billing_links, support_transactions, etc.)
- **Tracks:** 2464 catalog / 2462 approved (matches status API)
- **DJ users:** 2 (admin, manager) — separate from Supabase listener accounts
- **Takeovers:** 1 row (rejected)
- **Review queue:** 2 items
- **Support transactions:** 7

## Backups observed

- `/srv/allthings140radio/backups/station.db.latest` — updated 2026-09-14 04:58 UTC
- Daily encrypted state tarball on `/srv/allthings140radio/backups/`

No mutations performed. No user PII exported.

**Status: PASS**
