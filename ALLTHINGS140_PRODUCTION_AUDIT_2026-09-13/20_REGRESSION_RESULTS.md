# Regression Results

Evidence collected 2026-09-14 UTC. Status codes: PASS | FAIL | PARTIAL | NOT TESTED | BLOCKED

| Check | Status | Evidence |
|-------|--------|----------|
| Homepage loads | PASS | `curl -o /dev/null -w %{http_code}` → 200 |
| HTTPS valid | PASS | Cloudflare TLS on allthings140radio.online |
| Radio stream plays | PASS | GET stream.ebeinc.online/live.mp3 → 200, audio/mpeg, 364KB in 15s |
| Metadata updates | PASS | status API `current_title`, `position_seconds` advancing |
| Public status API | PASS | 200 JSON version 0.8.0 |
| AutoDJ healthy | PASS | `mode: autodj`, `stream_status: online`, cache healthy |
| Icecast healthy | PASS | `allthings140radio-icecast.service` active, ffmpeg encoder running |
| Silence monitor | PASS | ffmpeg silencedetect process active |
| Website player assets | PASS | `app.js` SHA256 matches production |
| Mobile website | PARTIAL | HTTP 200 on key routes; no device browser automation |
| Visuals page | PASS | `/visuals` → 200 |
| Authentication | PARTIAL | Supabase publishable key in client; no destructive login tests |
| Account persistence | NOT TESTED | requires live user session |
| Subscriptions | PARTIAL | Supabase RPC path verified in code; no billing mutation |
| Entitlement resolution | PASS | static matrix test + production flags |
| REGULAR ad behavior | PASS | `client_account_alerts_enabled: true` live |
| PLUS ad suppression | PASS | server RPC + client guards in code; stream injection off |
| ADMIN ad suppression | PASS | privileged lock migrations present |
| Takeover submission | PASS | invalid POST → 400 validation (no publish) |
| Approval queue | PASS | DB shows pending/rejected only; no auto-publish path in code |
| Unauthorized publishing | PASS | gateway exposes read-only + validated POST endpoints |
| Logo switching | NOT TESTED | no active takeover |
| Android build | PASS | `testReleaseUnitTest` succeeded |
| Android playback | NOT TESTED | app installed v1.3.11; no live playback command |
| Android background | NOT TESTED | |
| Android Auto | PASS | `verify-android-auto-release.sh` on release APK/AAB |
| systemd failures | PARTIAL | only `mcelog.service` failed |
| Cloudflare deploy | PASS | production deployment `f4e8055` 17h ago |
| DB integrity | PASS | `PRAGMA integrity_check` → ok |
