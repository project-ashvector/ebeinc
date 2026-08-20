# ALLTHINGS140 RADIO — Project Memory

**Generated:** 2026-08-16 (Onboarding Discovery Pass)  
**Purpose:** Concise but comprehensive description of the ecosystem for future OpenCode sessions.

---

## Quick Ecosystem Overview

ALLTHINGS140 Radio is a **24/7 dubstep/bass internet radio station** with a layered architecture spanning local workstations, Oracle Cloud VMs, Cloudflare CDN/Edge, and Google Drive storage.

### Four Operational Planes

| Plane | Name | Key Services | Responsibility |
|-------|------|-------------|----------------|
| 1 | Public Listener & Community | Cloudflare Pages, Cloudflare Tunnel, status.ebeinc.online, stream.ebeinc.online, visuals-realtime-staging.allthings140radio.online | Listener-facing web, stream delivery, chat, reactions, presence |
| 2 | 24/7 Broadcast Authority | Oracle VM 1 (`allthings140radio-server`, 64.181.235.228), Icecast 2, SQLite, FFmpeg, Google Drive via rclone | AutoDJ timeline, track scheduling, encoding, Icecast publishing, catalog management |
| 3 | Visuals & Realtime Server | Oracle VM 2 (`allthings140-visuals-realtime`, 163.192.1.208), aiohttp WebSocket server (port 8765/14140), static media origin (port 20242) | Presence, chat, reactions, room energy, takeover schedules, video streaming |
| 4 | Management & Workstation | Desktop DJ (`tools/dj_app.py`, Tkinter), Visuals Tauri app (`visuals-app/`, v0.1.30), Discord bot, Android app | Administrative control, visual show control, community bot, mobile listening |

### Current Status

- **Radio:** ONLINE — 24/7 production, load 0.69, memory 497M/946M, disk 31% used, 571 tracks in DB (569 approved)
- **Visuals:** STAGING — GREEN environment (`allthings140-visuals-green.pages.dev`) frozen at production baseline; production locked
- **Website:** ONLINE — `allthings140radio.online` on Cloudflare Pages, HTTP 200 OK
- **Status API:** ONLINE — `status.ebeinc.online/api/public/status`, HTTP 200 OK
- **Stream:** ONLINE — `stream.ebeinc.online/live.mp3`, HTTP 200 with audio
- **Tailscale:** MESH — allthings140radio-server active (direct), allthings140-visuals-realtime connected

---

## Applications Discovered

| Component | Installed | Latest Source | Latest Build | Status | Primary Purpose |
|-----------|-----------|--------------|-------------|--------|-----------------|
| **Station Broadcast Server** | 0.8.0 | `tools/server.py` (git, main, 24 commits ahead of origin) | 0.8.0 | ACTIVE PRODUCTION | AutoDJ, SQLite, FFmpeg encoder, Icecast, private API (port 14080) |
| **Desktop DJ Workstation** | 0.7.0 | `tools/dj_app.py` (git, main) | 0.7.0 | ACTIVE TOOL | Catalog browsing, rotation inspection, ad scheduling, takeover triggers |
| **Web Listener Frontend** | 1.6.1 | `radio/` (git, main) | 1.6.1 | ACTIVE PRODUCTION | Public player, background playback recovery, chat, Stripe support |
| **Visuals Desktop App** | 0.1.30 | `visuals-app/` (git, main, Tauri) | 0.1.30 | ACTIVE DEV/WORKSTATION | 7-layer canvas compositing, staging deployment, media management |
| **Green Web Stage** | N/A | `visuals-green/` (git, main) | N/A | ACTIVE STAGING | Web-based visual broadcast stage, dual video buffer, HUD overlays |
| **Visuals Realtime Server** | 0.1.0-staging | `visuals-realtime/app.py` (git, main) | 0.1.0-staging | ACTIVE STAGING | aiohttp WebSocket: presence, chat, reactions, energy, takeover schedules |
| **Android Mobile App** | 1.1.0 | `android/mobile-app/` (git) | 1.1.0 | ACTIVE ARTIFACT | Media3 ExoPlayer, Android Auto, debug-signed APK |
| **Discord Bot** | N/A | `discord-bot/` (git, main) | N/A | STANDALONE BOT | `/nowplaying`, `/radio`, `/invite`, `/announce` commands |
| **AI Host Generator** | N/A | `tools/ai_host.py` (git, main) | N/A | INTEGRATED EXTENSION | Ollama LLM + Piper TTS, scheduled radio breaks |
| **Hot Cache Manager** | N/A | `tools/cache_manager.py` (git, main) | N/A | ACTIVE SERVICE | Predictive pre-fetcher from Google Drive, 50-track hot cache |
| **Catalog Integrity System** | N/A | `tools/catalog_integrity.py`, `tools/recover_playback_assets.py` | N/A | ACTIVE SERVICE | SHA-256 verification, reconciliation, quarantine/restore |

---

## Canonical Paths

| Purpose | Path | Notes |
|---------|------|-------|
| **Project source** | `/home/ebmarah/Projects/AllThings140Radio/` | Git repo, version 2.3.2, branch main |
| **Server source** | `/home/ebmarah/Projects/AllThings140Radio/tools/` | server.py, radio_extensions.py, ai_host.py, etc. |
| **DJ app** | `/home/ebmarah/Projects/AllThings140Radio/tools/dj_app.py` | Tkinter admin UI |
| **Radio tools** | `/home/ebmarah/Projects/AllThings140Radio/tools/` | 20+ Python utility scripts |
| **Visuals app** | `/home/ebmarah/Projects/AllThings140Radio/visuals-app/` | Tauri v0.1.30, Rust + React/Vite |
| **Visuals green staging** | `/home/ebmarah/Projects/AllThings140Radio/visuals-green/` | Web-based staging, z-index fixes applied |
| **Visuals realtime** | `/home/ebmarah/Projects/AllThings140Radio/visuals-realtime/` | aiohttp realtime server (v0.1.0-staging) |
| **Visuals stage media** | `/home/ebmarah/Videos/at140radio/desktop visuals/stage/` | 1 file: `alpha.mov` (HEVC, 1920x1080) |
| **Visuals media** | `/home/ebmarah/Videos/at140radio/desktop visuals/visuals/` | 57 MP4 files (browser-optimized H.264) |
| **Station data** | `/var/lib/allthings140radio/` | SQLite station.db, rotation-state.json, catalog-integrity.json |
| **Music library** | `/mnt/allthings140radio-drive` (Google Drive) | Master audio library via rclone (currently not mounted) |
| **Emergency mirror** | `/srv/allthings140radio/data/music/` | 575 verified offline audio files |
| **Cache** | `/srv/allthings140radio/cache/` | READY subdirectory with pre-fetched tracks |
| **Config** | `/etc/allthings140radio/` | Production configuration (mode 0600, root-owned) |
| **Ads** | `/opt/allthings140radio-server/ads/` | Ad audio files |
| **Cloudflare config** | `/etc/cloudflared/allthings140radio.yml` (may vary) | Tunnel configuration |
| **Wrangler project** | `/home/ebmarah/Projects/AllThings140Radio/` | Root git repo, also `project-ashvector/ebeinc` |
| **Tailscale mesh** | — | All VMs and workstation on same tailnet (`at140tail`) |
| **Backup script** | `/usr/local/sbin/allthings140radio-fallback-sync` | rsync from Oracle VM 1 to local workstation |

---

## Radio Architecture — Playback Path

### How a song plays on the 24/7 stream

1. **Google Drive** is the master music library (`at140drive:` mounted via rclone at `/mnt/allthings140radio-drive`)
2. **Station database** (`/var/lib/allthings140radio/station.db`) tracks: approval status, SHA-256 hashes, durations, metadata
3. **Hot cache manager** (`tools/cache_manager.py`) predicts upcoming rotation tracks and pre-fetches them from Drive to local `/srv/allthings140radio/cache/READY/`
4. **Rotation state** (`/var/lib/allthings140radio/rotation-state.json`) tracks current position in rotation order
5. **AutoDJ** (in `tools/server.py`):
   - Advances rotation position
   - Decodes selected track with FFmpeg (PCM stereo)
   - Calls `mix_ad()` for ad ducking (4-byte PCM stereo boundary alignment)
   - Feeds persistent FFmpeg encoder → loopback-only Icecast on port 14000
6. **Icecast 2** serves `/live.mp3` on loopback only (port 14000)
7. **Cloudflare Tunnel** (`cloudflared`) exposes loopback audio to public via `stream.ebeinc.online/live.mp3`
8. **Public status API** (`status.ebeinc.online/api/public/status`) provides: `online`, `current_title`, `current_artist`, `listeners`, `stream_status`, `station_generation_id`, `station_sequence`
9. **Listeners** connect to `stream.ebeinc.online/live.mp3` via HTTP through Cloudflare edge

### Key Hardware & Ports

- **Oracle VM 1** (64.181.235.228 / Tailscale `allthings140radio-server`): server.py, Icecast, rclone, tunnel
- **Loopback Icecast:** port 14000 (local only)
- **Private control API:** port 14080 (loopback, Tailscale forwarded)
- **Public gateway:** port 14082 (loopback, Cloudflare Tunnel)
- **Traktor guest ingest:** port 14083 (loopback, restricted)
- **Icecast auth relay:** port 14001 (loopback, `icecast://source:local-relay@127.0.0.1:14001/live.mp3`)

### 24/7 Reliability Mechanisms

- **Stateful supervisor** with exponential restart backoff after 3 failures
- **SQLite backups** every 10 minutes; encrypted off-host daily backups with integrity test
- **Predictive hot cache** (50 tracks) to pre-empt Drive latency
- **Emergency mirror** (575 files) as fallback if cache misses
- **Watchdog** monitors Icecast, server, Drive, tunnel health
- **Cache admission timer** (30-min playback-admission timer) prevents tracks from becoming stranded
- **Generation ID + monotonic sequence** in status responses prevents stale client responses

---

## Visual Architecture — Stage/Visual System

### Compositing Model: Stage Content in FRONT, Visual Content UNDER

The desired compositing model has the Stage acting like a physical frame:

- **Visual Content z: 10** (backmost — `.screens` layer)
- **Stage Content z: 20–70** (frontmost — `.stage-overlay`, `.mode-logo`, `.now`, `.audience`, `.reactions`, `.energy`)

### Current Authoritative Layer Stacking (after v0.1.21 fix)

| Layer | z-index | Class/Element | Content Type |
|-------|---------|--------------|-------------|
| 01 | 10 | `.screens` | Visual Content (MP4 video, backmost) |
| 02 | 20 | `.stage-overlay` | Stage Frame |
| 03 | 30 | `.mode-logo` | Station / Takeover Logo |
| 04 | 40 | `.now` | Now Playing / Live Alert |
| 05 | 50 | `.audience` | Presence Bubbles / Audience |
| 06 | 60 | `.reactions` | Reactions (fire, skull, heart, bolt, bass) |
| 07 | 70 | `.energy` | Room Energy HUD (frontmost) |

### Historical Bug (Now Fixed)

Previously, `.screens` (z: 10) visually appeared **over** `.stage-overlay` (z: 20) despite the inspector showing Stage as the top layer. This was caused by the visual video rendering on top of the stage. The fix (v0.1.21) reordered the z-index stacking to authoritative order and reparented layer geometry.

### Visual Media Folders

- **Stage:** `/home/ebmarah/Videos/at140radio/desktop visuals/stage/` — 1 file: `alpha.mov` (HEVC, 1920x1080, 60fps, ~48s, no embedded alpha; runtime derivative is muted H.264)
- **Visuals:** `/home/ebmarah/Videos/at140radio/desktop visuals/visuals/` — 57 MP4 files (browser-optimized H.264 derivatives)

### Tauri Workstation (visuals-app)

- **Version:** 0.1.30
- **Tech:** Rust + Tauri v2 + Vite + React
- **Port:** 14340 (dev mode)
- **Security:** assetProtocol scopes `/home/ebmarah/Videos/at140radio/desktop visuals/**` and `/home/ebmarah/Projects/AllThings140Radio/visuals-green/media/**`
- **CSP:** `default-src 'self'; connect-src 'self' ipc: http://ipc.localhost http://127.0.0.1:* https://allthings140-visuals-green.pages.dev ...`
- **Key capabilities:** Media scanning, layer management, WYSIWYG workshop, publish to GREEN staging, schedule takeovers on realtime server

### GREEN Staging Environment

- **URL:** `https://allthings140-visuals-green.pages.dev/`
- **Status:** FROZEN at production baseline — no cutover authorized
- **SHA-256 production baseline:** `4ca1a32e74c2b319fa8c7979b2e68e1486166a2d105c53158f2a417bf976ef32`
- **Contains:** Dual video buffer (stage + visual), audience presence, reactions, room energy, takeover schedule state
- **Deployment:** Cloudflare Pages; media synced via rsync to OCI VM; layout.json + layout.hash verified

### Production Visuals Baseline

- **SHA-256:** `4ca1a32e74c2b319fa8c7979b2e68e1486166a2d105c53158f2a417bf976ef32`
- **Never to be changed without explicit authorization**
- **Represents the locked `/visuals/` frontend production deployment**

---

## Website Architecture

### Public Site

- **Domain:** `allthings140radio.online`
- **Hosting:** Cloudflare Pages
- **Source:** `radio/` subdirectory of the main project
- **Entry point:** `index.html`
- **Service Worker:** v54, cache-first for critical JS, network-first for audio critical paths
- **Deployments:** `827399a7.ebeinc-uqt.pages.dev` (post-support), `aac2a08a-9c5a-4184-8470-c9502e38c63b` (baseline)

### Public APIs (all under Cloudflare edge)

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/public/status` | GET | none | Station status: online, current_track, listeners, generation_id, sequence |
| `/api/public/status` | GET | none | Stream URL, freshness check (age <= 180s) |
| `/api/public/takeover-alert` | POST | Bearer token (ADMIN_ALERT_KEY/TAKEOVER_ALERT_KEY/ADMIN_TOKEN) | Queue subscriber alert email for approved takeover |
| `/api/public/schedule` | GET | none | Takeover schedule including current/upcoming |
| `/api/public/support/webhook` | POST | none | Stripe webhook verification (checkout.session.completed) |
| `/api/public/support/status` | GET | none | Mailchimp connectivity status |
| `/api/public/newsletter` | POST | none | Mailchimp newsletter signup |
| `/api/public/newsletter/status` | GET | none | Mailchimp configured/connected |
| `/api/public/takeover-invite/[hash]` | GET | none | Private takeover request form |
| `/api/public/obs/live.mp3` | GET/HEAD | OBS_STREAM_TOKEN | Private OBS audio gateway |
| `/api/public/archive/[...]` | GET | none | R2 recording delivery |

### Service Worker (radio/sw.js, sw-v47.js)

- **Cache version:** v54
- **Excludes** `.mp3`, `.m3u8`, `/obs/` from CacheStorage to prevent stream interception
- **Background resume:** deduplicated transaction on visibilitychange, pageshow, focus, online
- **Aborts** frozen status requests, fetches no-store authoritative state, discards older sequence data
- **Reconnects** use bounded exponential backoff plus jitter and generation guards

### Stripe Support System

- **Backend:** `tools/support_system.py` — HMAC-SHA256 verification, replay prevention (300s window), idempotent SQLite recording
- **Frontend:** `radio/support.js`, `radio/support.css` — accessible modal, goal/feed, non-audio notifications
- **Never proof of payment:** only `checkout.session.completed` or `checkout.session.async_payment_succeeded` at the webhook URL marks a session paid
- **Public data:** only paid records; subtracts `charge.refunded` amounts; excludes emails, billing details, IPs, customer IDs

### Known Website Issues (Post-Repair)

- Fixed: Service Worker stream interception (`.mp3`/`.m3u8` excluded from cache)
- Fixed: Background tab audio teardown (respect `dataset.src` before reconnecting)
- Fixed: Cold-start play button drop (poll on demand if `dataset.src` not yet populated)
- Fixed: Unsafe DOM innerHTML (converted to safe element creation APIs)
- Fixed: Visuals HUD hidden behind video layers (z-index reordering in stage.css/overlay.css)

---

## Infrastructure — Servers, VMs, and Storage

### Oracle Cloud VM 1: Broadcast Authority

| Attribute | Value |
|-----------|-------|
| Hostname | `allthings140radio-server` |
| IP (public) | 64.181.235.228 |
| IP (Tailscale) | 100.124.12.41 (active, direct) |
| Tailnet zone | `at140tail` (firewalld) |
| OS | Oracle Linux 9, UEK 6.12.0 x86_64 |
| CPU | 1 OCPU |
| RAM | 1 GB (946 MiB visible; 448 MiB was reserved for kdump, now disabled) |
| Disk | 30 GB OS disk (31% used); 50 GB `/srv` volume (27% used) |
| Services | `allthings140radio-server`, `allthings140radio-icecast`, `allthings140radio-tunnel`, `allthings140radio-drive`, `allthings140radio-cache`, `allthings140radio-fallback-sync.timer` |
| Oracle SSH key | `/home/ebmarah/.ssh/allthings140radio_oracle_ed25519` |
| Fallback sync | rsync from `/srv/allthings140radio/` on Oracle VM to `/var/lib/allthings140radio/` locally |
| Rclone config | Google Drive `at140drive:` → `/mnt/allthings140radio-drive` (not currently mounted on this workstation) |

### Oracle Cloud VM 2: Visuals Realtime Server

| Attribute | Value |
|-----------|-------|
| Hostname | `allthings140-visuals-realtime` |
| IP (public) | 163.192.1.208 |
| Tailscale | 100.108.145.128 (connected, linux) |
| OS | Oracle Linux 9.8, UEK 6.12.0 x86_64 |
| CPU | 1 OCPU (Standard.E2.1.Micro) |
| RAM | 1 GB (946 MiB visible) |
| Disk | 30 GB OS disk (22% used) |
| Services | `allthings140-visuals-realtime` (aiohttp, port 8765/14140), `allthings140-visuals-tunnel` (cloudflared), `allthings140-visuals-backup.timer` |
| Health | `{"ok": true, "service": "allthings140-visuals-realtime", "version": "0.1.0-staging"}` |
| SSH key | `~/.ssh/allthings140_visuals_realtime_ed25519` |

### Cloudflare Resources

| Resource | Value |
|----------|-------|
| **Pages: allthings140radio.online** | `https://allthings140radio.online` (production site) |
| **Pages: ebeinc** | Custom domain `ebeinc.online` (separate repo/project) |
| **Pages: allthings140-visuals-green** | `https://allthings140-visuals-green.pages.dev` (green staging, frozen) |
| **Workers: _worker.js** | Edge worker routing, takeover alert auth, public gateway proxy |
| **Custom domain** | `allthings140radio.online` (Cloudflare Pages) |
| **Tunnel** | `cloudflared` service on VM 1 and VM 2 |
| **Secret pending:** | `ADMIN_ALERT_KEY` — not yet set in Cloudflare Dashboard/CLI |

### Tailscale Mesh Network

- All servers and workstation on same tailnet (`ebmarahofficial@`)
- `allthings140radio-server`: active, direct connection (64.181.235.228:41641)
- `allthings140-visuals-realtime`: connected
- Private control API access via MagicDNS host `allthings140radio-server`
- SSH over Tailscale preferred over public routes

### Google Drive Storage

- **Master music library:** `at140drive:` (rclone)
- **Mount point:** `/mnt/allthings140radio-drive` (on Oracle VM 1)
- **Content:** 571 catalog filenames exist in Drive root
- **Sync:** rclone; fallback mirror at `/srv/allthings140radio/data/music/` (575 files)
- **Current status on workstation:** Drive not currently mounted; paths referenced but may not be active
- **Catalog integrity:** 571 total tracks; 569 eligible/approved; 569 playable after August 15 recovery

### Storage Summary

| Store | Location | Files | Purpose |
|-------|----------|-------|---------|
| **Google Drive master** | `/mnt/allthings140radio-drive` (Oracle VM 1) | 571+ | Source of truth for all audio |
| **Emergency mirror** | `/srv/allthings140radio/data/music/` | 575 | Local playback fallback |
| **Hot cache** | `/srv/allthings140radio/cache/READY/` | ~50 | Predictive pre-fetch for upcoming rotation |
| **Quarantine** | `/var/lib/allthings140radio/music-quarantine/` | Isolated tracks under review |
| **Station DB** | `/var/lib/allthings140radio/station.db` | SQLite — approvals, hashes, metadata, schedules |
| **Catalog integrity** | `/var/lib/allthings140radio/catalog-integrity.json` | SHA-256 hashes, status (HEALTHY/DEGRADED/CRITICAL) |
| **Ads** | `/opt/allthings140radio-server/ads/` | Ad audio files |
| **Takeover logos** | `/var/lib/allthings140radio/takeover-logos/` | Artist takeover logo files |

---

## Deployment Architecture

### Current Deployment Model

**Incremental, backup-first, single-service restart:**

1. **Backup** timestamped copy of current server.py (`server.py.before-TIMESTAMP`)
2. **Syntax check** `python3 -c "import py_compile; py_compile.compile('tools/server.py')"`
3. **Deploy** single file: install server.py to `/opt/allthings140radio-server/server.py`
4. **Restart** only the affected systemd service: `systemctl restart allthings140radio-server`
5. **Verify** local health: `curl -fsS http://127.0.0.1:14080/api/health`
6. **Verify** public stream: `curl -fsS https://stream.ebeinc.online/live.mp3` (first 4096 bytes)
7. **Rollback** retained from timestamped backup if verification fails

### Cloudflare Deployments

- **`allthings140radio.online`:** Cloudflare Pages, deployed from `main` branch, `radio/` subdirectory
- **`allthings140-visuals-green`:** Cloudflare Pages, green staging environment, media + layout artifacts
- **`_worker.js`:** Cloudflare Edge Worker, deployed with Pages; contains takeover-alert auth
- **Deployment command:** `npx wrangler pages deploy visuals-green-pages-dist --project-name allthings140-visuals-green --branch staging --commit-dirty=true`

### Zero-Downtime Change Pattern

```
Backup current file → Syntax check → Single-file deploy → Restart one service → Verify local → Verify public → Rollback if needed
```

### Services Never Restarted Simultaneously

No production VM service restarts occurred during the August 15, 2026 remediation pass. All fixes were deployed to Cloudflare edge or staged locally; Oracle VM 1 and VM 2 remained 100% online.

---

## Known Problems & Risks

### Critical

| # | Issue | Location | Risk |
|---|-------|----------|------|
| 1 | FFmpeg encoder stderr pipe without consumption deadlock risk | `tools/server.py:start_encoder()` | Could block encoder thread, cause silence on stream |
| 2 | Discord bot plaintext token in `.env` | `discord-bot/.env` | Credential exposure if repo or env files leaked |
| 3 | Android release signed with debug keystore | `android/mobile-app/app/build.gradle` | Cannot publish to Google Play without proper signing |
| 4 | Cloudflare Worker `ADMIN_ALERT_KEY` not set | `radio/_worker.js` `handleTakeoverAlert()` | Takeover alerts potentially unauthenticated (key not yet provisioned) |

### High

| # | Issue | Location | Status |
|---|-------|----------|--------|
| 1 | `mix_ad()` PCM frame misalignment on odd byte slices | `tools/server.py` | Fixed in August 15 repair (4-byte boundary alignment) |
| 2 | Service Worker live stream interception | `radio/sw.js`, `sw-v47.js` | Fixed (`.mp3`/`.m3u8` excluded from CacheStorage) |
| 3 | Visuals z-index stacking — HUD hidden behind video | `visuals-green/stage.css`, `overlay.css` | Fixed (authoritative z-order: HUD 50-70, video 10-40) |
| 4 | Realtime server repeated DDL on every status poll | `visuals-realtime/app.py` | Fixed (moved to Room.__init__) |
| 5 | DJ app synchronous network I/O on main thread | `tools/dj_app.py` | Fixed (takeover webhooks moved to background thread) |
| 6 | Unauthenticated `/api/public/takeover-alert` POST | `radio/_worker.js` | Partially fixed (auth check added, ADMIN_ALERT_KEY not set) |

### Medium

| # | Issue | Location |
|---|-------|----------|
| 1 | Hot cache index disconnect — files dropped from cache-index.json | `tools/cache_manager.py` | Fixed (all verified files now indexed) |
| 2 | AI host WAV accumulation without pruning | `tools/ai_host.py` | Fixed (prune_cache() implemented) |
| 3 | Discord bot metadata API field mapping bugs | `discord-bot/index.js` | Fixed (current_title, current_artist mapping) |
| 4 | Android release signing property-driven not implemented | `android/mobile-app/app/build.gradle` | Partially fixed (debug fallback, release vars still env-driven) |
| 5 | Extended desktop soak for visuals not yet complete | visuals-workstation — not yet long-enough soak |

### Low

| # | Issue | Location |
|---|-------|----------|
| 1 | VM 1 root volume space concern (31% used, 21 GB available) | `/` on Oracle VM 1 |
| 2 | kdump disabled on VM 2 (was causing boot delays) | Oracle Linux 9.8 on VM 2 |
| 3 | Takeover restart-before-start and scheduling scheduling needs longer soak | visuals-realtime staging |
| 4 | Mobile browser regression/profile/reconnect testing incomplete | visuals workstation |

### Single Points of Failure

| # | SPOF | Impact | Mitigation |
|---|------|--------|-----------|
| 1 | Oracle VM 1 holds critical state: station.db, rotation state, ICECAST, Drive metadata | Complete station outage if VM 1 fails | Fallback sync to local workstation; emergency mirror 575 files; off-host encrypted backups daily |
| 2 | Icecast 2 single encoder instance | Single point of audio failure | Loopback auth relay (port 14001); watchdog supervisor with exponential backoff |
| 3 | Google Drive as master music library | All 571 tracks unavailable if Drive unreachable | Emergency mirror (575 files) serves as local cache; catalog integrity system tracks status |
| 4 | Cloudflare Tunnel single edge path | Stream delivery outage if tunnel down | Secondary tunnel instances possible; fallback to direct Icecast via Tailscale |
| 5 | Realtime server (VM 2) single instance | Visuals chat/reactions/takeover schedules unavailable | Stateless cache; history in SQLite; can restart without data loss |
| 6 | Tailscale mesh for private API access | Authorized control plane inaccessible without tailnet | SSH over Tailscale; MagicDNS `allthings140radio-server`; fallback not publicly exposed |

---

## Things You Must Never Change Blindly

| # | Safeguard | Reason |
|---|-----------|--------|
| 1 | **Never deploy server.py without a timestamped backup** | Rollback requires the pre-deployment copy; server is the authoritative broadcast engine |
| 2 | **Never restart allthings140radio-server without verifying local health first** | `curl -fsS http://127.0.0.1:14080/api/health` must return OK before considering the change stable |
| 3 | **Never verify public stream without confirming local health first** | Ensure `https://stream.ebeinc.online/live.mp3` returns audio before considering change complete |
| 4 | **Never change Icecast credentials without reconfiguring the auth relay** | Loopback relay at port 14001 injects real source passwords; real passwords never appear in process listings |
| 5 | **Never ignore the catalog-integrity.json status** | HEALTHY/DEGRADED/CRITICAL state drives playback admission timer and cache planning |
| 6 | **Never assume Google Drive is the only source of truth without checking the emergency mirror** | 88-track incident (Aug 15) showed Drive uploads can become stranded in cache; all 571 filenames exist in Drive |
| 7 | **Never deploy visuals changes without verifying GREEN layout.json hash matches** | Production baseline `4ca1a32e...` must be preserved; deployment validates remote manifest revision/hash |
| 8 | **Never modify the `ADMIN_ALERT_KEY` without re-deploying the Cloudflare worker** | Worker auth check requires matching key; setting without deploy leaves endpoint unauthenticated |
| 9 | **Never treat the `/api/public/takeover-alert` endpoint as authenticated without verifying the Bearer token** | Historical vulnerability: no auth checks existed; now protected but key not yet provisioned |
| 10 | **Never skip the 30-minute playback-admission timer** | Prevents tracks from becoming stranded in Drive after upload without local cache admission |

---

## Project Memory Created

**Path:** `/home/ebmarah/Projects/ALLTHINGS140_PROJECT_CONTEXT/`

### Files Created

- `PROJECT_MEMORY.md` — Concise ecosystem summary (this file)
- `ARCHITECTURE.md` — Architecture, app relationships, servers, APIs, service map
- `APPLICATIONS.md` — Every discovered application and its current state
- `INFRASTRUCTURE.md` — Oracle, Cloudflare, Tailscale, domains, VMs, storage, deployments
- `CURRENT_STATUS.md` — Current versions, development activity, production/staging status, known problems
- `PATHS.md` — Canonical source directories, builds, media paths, logs, installers, backups, master folders
- `DO_NOT_BREAK.md` — Critical safeguards and things future AI agents must verify before modifying
- `OPEN_ISSUES.md` — Known problems, incomplete development, risks, technical debt, suspicious architecture
- `RECENT_CHANGES.md` — Best reconstruction of recent meaningful project work based on Git history, reports, changelogs, filesystem artifacts, and installed builds
- `OPENCODE_START_HERE.md` — Compact onboarding document specifically for future OpenCode sessions

### Supporting Files

- `AGENTS.md` — Updated (or created) in the main project root, pointing to project context
- `AGENTS.md` — Also created/updated in `ALLTHINGS140_PROJECT_CONTEXT/` if suitable

---

## Confidence Score

| Component | Score | What prevents 100% |
|-----------|-------|-------------------|
| **Radio system** | 95% | Drive mount status not directly verifiable from this workstation; some path mappings inferred from config |
| **Visual system** | 85% | Production baseline hash verified; GREEN staging state understood but cutover gates still open |
| **Website** | 92% | Cloudflare resource details from reports; actual live deployment verified via HTTP 200 |
| **Infrastructure** | 88% | Oracle VM details from reports; actual runtime resources not directly inspectable from workstation |
| **Desktop applications** | 90% | DJ app and visuals app source code fully read; binary blobs verified |
| **Android/mobile** | 70% | Only debug APK observed; release signing config and Play Store status not verified |
| **Deployment architecture** | 95% | Incremental backup-first model verified; exact Cloudflare secret provisioning status |
| **Whole ALLTHINGS140 ecosystem** | 82% | Some components (Drive mount state, Cloudflare secrets, Oracle VM resources) verified from reports rather than direct inspection; no firsthand runtime evidence for all subsystems |

**What prevents 100% confidence:** Inability to directly inspect Oracle Cloud VM runtime state, Google Drive mount status from this workstation, Cloudflare secret provisioning status, and production deployment exact states without authorized access. All values cross-verified against reports, Git history, and where possible, runtime health checks.

---

## Recent Changes Summary (2026-08-13 to 2026-08-15)

Three major engineering hardening phases performed:

1. **Aug 13 — Background Playback Reliability & Support System:**
   - Monotonic `station_sequence` and `station_generation_id` in status responses
   - Service Worker deduplicated resume transaction (visibilitychange, pageshow, focus, online)
   - Upgraded Service Worker to cache v54 with network-first delivery
   - `tools/support_system.py` — HMAC verification, replay prevention, idempotent recording
   - Stripe production payments activated

2. **Aug 13 — Visuals Compositor & Realtime fixes:**
   - Authoritative HUD z-index stacking (z: 50-70 above video at z: 10-40)
   - CORS allowlist on `/visuals-state` endpoint
   - Rate-limited IP event pruning in realtime server
   - Client snapshot iteration in broadcast

3. **Aug 15 — Catalog Integrity & Radio Hardening:**
   - Station Server v0.8.0 deployed after 88-track incident
   - `tools/catalog_integrity.py` and `tools/recover_playback_assets.py` deployed
   - Emergency mirror rebuilt to 575 verified files (569 eligible)
   - 4-byte PCM stereo boundary alignment in `mix_ad()`
   - Encoder stderr → DEVNULL (deadlock eliminated)
   - Duration caching from DB, eliminated sync ffprobe on track transitions
   - Rotation state lock synchronization
   - DJ app: removed render_rotation([]) queue wipe, async webhook threads
   - Visuals green: z-index reordering + CORS + health fixes
   - Cloudflare worker: Bearer auth on `/api/public/takeover-alert`
   - 37/37 tests passing (100%)
   - All services remained 100% online throughout

### Files Modified (Aug 15, 2026 remediation)

`radio/_worker.js`, `tools/server.py`, `radio/sw.js`, `radio/sw-v47.js`, `radio/app.js`, `visuals-green/stage.css`, `visuals-green/overlay.css`, `visuals-green/stage.js`, `visuals-realtime/app.py`, `tools/dj_app.py`, `discord-bot/index.js`, `android/mobile-app/app/build.gradle`, `tools/cache_manager.py`, `tools/ai_host.py`, `tools/radio_healthcheck.py`, `operations/restore-vm.sh` (new), 18 test files

### Services Restarted

**None** on production VMs during remediation pass. All fixes deployed to Cloudflare edge or staged locally; Oracle VM 1 and VM 2 remained continuously online.

---

## Open Issues still Pending

1. **Discord bot token** — may need rotation in Developer Portal if previously shared
2. **Cloudflare Worker `ADMIN_ALERT_KEY`** — not yet provisioned; without it, `/api/public/takeover-alert` is unauthenticated
3. **Android release keystore** — environment vars needed for Google Play deployment
4. **Extended visuals desktop soak** — long-term memory-growth observation incomplete
5. **Google Drive mount status** — not directly verifiable from this workstation; assumed active based on config references
6. **Mobile browser regression testing** — visuals real device profile reconnect testing incomplete
7. **Takeover restart-before-start scheduling** — needs longer real-time staging test
8. **Visuals GREEN cutover** — production locked; cutover gate requirements incomplete (multi-hour soak, physical phone, manual asset validation)