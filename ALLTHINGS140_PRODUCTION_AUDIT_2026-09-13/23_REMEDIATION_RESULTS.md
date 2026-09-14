# Remediation Results (2026-09-14 UTC)

Post-audit remediation pass. Production stream was not interrupted.

---

## Git/GitHub

**before:** `main` ahead of `origin/main` by 94 commits; `gh` not authenticated; HTTPS push failed; GitHub SSH key not authorized.

**after:** Secret scan of all 94 commits completed — no private keys, live API tokens, or credential files in diff (only `.env.example` / `config.example.env` placeholders). Push still blocked: `fatal: could not read Username for 'https://github.com'` and `git@github.com: Permission denied (publickey)`.

**result:** **FAIL / BLOCKED** — local history is safe to push once credentials exist. Run `gh auth login` (or configure GitHub SSH deploy key for `project-ashvector/ebeinc`), then `git push origin main` (no force). Current branch: `fix/visuals-24-7-compositor` with additional uncommitted remediation edits.

---

## Oracle Memory

**before:** 946 MiB RAM; 580 MiB used; 309 MiB swap used. Top consumers: Discord relay node (~112 MiB), Discord ffmpeg (~78 MiB), `server.py` (~68 MiB), cache manager (~18 MiB).

**after:** 591 MiB used; 333 MiB swap; no OOM events in kernel journal; `stream_status: online`. No production services stopped. Assessment: **normal for 1 GB VM shape** running broadcast + tunnel + cache + Discord relay — not a leak; hardware sizing limitation.

**result:** **PASS WITH WARNING** — monitor; consider VM resize if swap churn increases. No tuning applied (would risk broadcast stability).

---

## Visuals

**root cause:** GCP realtime gateway healthy (`0.3.0-workstation`) but `workstationLive.active=false`, `lastHeartbeat` age ~2.1 hours. Tailscale node `allthings140-visuals-realtime` has been **offline 18 days**. Local `allthings140radio-visuals` process is running on this workstation but is **not publishing live heartbeats** (operator LIVE session not active).

**repair:** None applied — restoring live compositor requires operator to start **● LIVE VISUALS** in the workstation app on the authoritative machine, or power on the offline Tailscale visuals workstation.

**result:** **BLOCKED — WORKSTATION OFFLINE / NOT IN LIVE MODE**. Fallback on GCP is **HEALTHY**.

---

## Auth

**tests:**
- Supabase GoTrue health: HTTP 200
- Invalid login: HTTP 400 `invalid_credentials` (expected)
- Web/Android config: same Supabase URL + publishable key
- Static entitlement guards: `node tests/test_account_alert_entitlement.mjs` PASS

**result:** **PARTIAL** — endpoints healthy and mis-auth rejected; full signup/login/session lifecycle not exercised (no safe disposable test account created; anonymous signup disabled).

---

## Subscriptions

**tests:**
- `tests/test_subscription_system.py`: **5/5 PASS** (mocked Stripe/Supabase)
- Live Stripe checkout/billing: **not executed** (production billing only)

**result:** **PARTIAL** — code-path and unit tests PASS; real payment intentionally not executed.

---

## Cloudflare DNS

**result:** **BLOCKED** — zone lookup works; DNS record export returns HTTP 403 with Wrangler OAuth token (lacks Zone DNS Read). Partial artifact saved: `cloudflare-dns-export-partial.json` (zone IDs only, no records). Pages custom domains verified via wrangler: `allthings140radio.online`, `ebeinc.online` on project `ebeinc`.

---

## Hub/GUI

**tests:** Installed `pytest` into existing Hub venv (`~/.local/share/allthings140-hub/.venv`). Ran `test_hub_ui_smoke.py` + `test_hub_functional.py`: **13/13 PASS**.

**result:** **PASS**

---

## mcelog

**finding:** `mcelog` unsupported on AMD family 23 VM — "use edac_mce_amd instead."

**action:** Service already masked; ran `systemctl reset-failed mcelog.service`. Backup: `/root/mcelog.service.before-remediation-20260914` on Oracle VM.

**result:** **PASS** — `systemctl --failed` shows **0** units.

---

## Restore Drill

**procedure:** Copied `/srv/allthings140radio/backups/station.db.latest` to `/tmp/at140-restore-drill-20260914/` (via `sudo cat` pipe; production untouched).

**validation:**
- integrity: `ok`
- tables present; aggregate counts: users 2, tracks 2464, takeovers 1, audit_log 3653, billing_links 0

**cleanup:** Temporary directory removed.

**result:** **PASS**

---

## Additional test repairs

| File | Change | Result |
|------|--------|--------|
| `tests/test_radio_system.py` | Alert catalog + SW cache guards (audit) | 20/20 PASS |
| `tests/test_realtime_http.py` | Set `ALLOWED_ORIGINS` / admin tokens / `MEDIA_ROOT` for `create_app()` | 1/10 PASS — tests still use legacy `ADMIN_TOKEN`; need follow-up update for `GREEN_ADMIN_TOKEN`/`LIVE_ADMIN_TOKEN` |

---

## Final regression (post-remediation)

| Check | Result |
|-------|--------|
| Website | PASS 200 |
| Public API | PASS 200 |
| Stream | PASS (online autodj) |
| Alert injection OFF | PASS |
| Client alerts ON | PASS |
| Android unit tests | PASS |
| Android Auto contract | PASS |
| Oracle stream after mcelog fix | PASS (no interruption) |
| Hub tests | PASS 13/13 |
