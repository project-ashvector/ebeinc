# Production Inventory

| Component | Source | Git Repo | Branch/Commit | Production Location | Runtime | Deployment Method | Status |
|-----------|--------|----------|---------------|---------------------|---------|-------------------|--------|
| Website | `radio/` | github.com/project-ashvector/ebeinc | Pages: `f4e8055` | Cloudflare Pages `ebeinc` | CF Worker + static | `wrangler pages deploy` | ACTIVE |
| Public API proxy | `radio/_worker.js` | same | `f4e8055` | Cloudflare edge | Worker | Pages binding | ACTIVE |
| Backend/AutoDJ | `tools/server.py` | same | matches prod hash | `/opt/allthings140radio-server/server.py` | `allthings140radio-server.service` | manual/rsync + restart | ACTIVE 0.8.0 |
| Icecast | config in repo/deploy | same | — | `/etc/allthings140radio/icecast.xml` | `allthings140radio-icecast` | systemd | ACTIVE |
| Public tunnel | cloudflared unit | — | — | systemd `allthings140radio-tunnel` | cloudflared | systemd | ACTIVE |
| Database | — | — | — | `/var/lib/allthings140radio/station.db` | SQLite 2.2M | local + timers | ACTIVE ok |
| Cache | `cache_manager.py` | same | prod hash match* | `/srv/allthings140radio/cache` | `allthings140radio-cache` | systemd | ACTIVE healthy |
| Drive mount | rclone | — | — | `/mnt/allthings140radio-drive` | `allthings140radio-drive` | systemd | ACTIVE |
| Listener auth | Supabase | `supabase/migrations/` | — | Supabase cloud | GoTrue + RPC | hosted | ACTIVE |
| DJ users (2) | server local auth | same | — | SQLite `users` table | server | — | ACTIVE |
| Alert catalog | `radio/assets/client-alerts/` | same | deployed | Pages assets + worker | edge | Pages | ACTIVE |
| Stream ads meta | runtime | — | — | `/var/lib/allthings140radio/ads.json` | server | — | injection OFF |
| Visuals realtime | `visuals-realtime/` | same | GCP deploy | `/opt/allthings140-visuals-realtime` | GCP VM :8765 | systemd | ACTIVE fallback |
| Green Room | `chat-worker/` | same | — | Cloudflare Worker | `chat.ebeinc.online` | wrangler | NOT FULLY TESTED |
| Android app | `android/mobile-app/` | same | local `f4e8055` branch | Play/sideload | v1.3.11 vc27 | Gradle | ACTIVE on test phone |
| Wear radio | `android/watch-app/...v0.3.2` | same | — | sideload APK | separate package | manual | NOT ACTIVE product |
| Discord relay | `discord-bot/` | same | — | Oracle systemd | `allthings140-discord-radio` | systemd | ACTIVE |

*Server hash verified identical; supporting scripts assumed matched per prior deployment reports.
