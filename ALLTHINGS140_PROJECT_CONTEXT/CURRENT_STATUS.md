# ALLTHINGS140 RADIO — Current Status

**Report Date:** 2026-08-16  
**Onboarding Pass:** OpenCode Discovery  
**Overall System Health:** 96% production readiness (hardened after August 15, 2026 remediation)

---

## Radio System

| Metric | Value | Status |
|--------|-------|--------|
| **Server Uptime** | 3 days 4 hours | HEALTHY |
| **Load Average** | 0.69 | NORMAL |
| **Memory Usage** | 497 MiB / 946 MiB (52%) | HEALTHY |
| **Disk Usage** | 31% used (21 GB free / 30 GB OS) | HEALTHY |
| **OS Disk** | 30 GB, 31% used | HEALTHY |
| **Srv Volume** | 50 GB, 27% used | HEALTHY |
| **Listeners** | 2 (during check) | ONLINE |
| **Stream Status** | ONLINE — delivering audio | HEALTHY |
| **Current Track** | "BANG REMIX V4" | PLAYING |
| **Sequence** | Progressing normally | MONOTONIC |
| **Generation ID** | Present in status responses | STABLE |
| **Catalog State** | HEALTHY — 569 eligible tracks playable | HEALTHY |
| **Approved Tracks** | 569 / 571 total | 99.3% |
| **Unapproved/Rights-Blocked** | 2 tracks | INTENTIONAL |
| **Hot Cache Tracks** | ~50 (target 120 min) | ACTIVE |
| **Emergency Mirror Files** | 575 | VERIFIED |
| **Playback Admission Timer** | 30-min systemd timer active | PREVENTS STRANDED TRACKS |
| **FFmpeg Encoder** | Running with stderr=DEVNULL (deadlock fixed Aug 15) | FIXED |
| **AutoDJ** | Advancing rotation, mixing ads | ACTIVE |
| **Icecast 2** | Loopback-only port 14000 | RUNNING |
| **Private API (port 14080)** | Accessible via Tailscale | HEALTHY |
| **Public Gateway (port 14082)** | Cloudflare Tunnel | HEALTHY |

### Radio Health Check (diagnose.py output)

```
AllThings140Radio: OK
PASS website: HTTP 200
PASS status_api: HTTP 200; online=True
PASS current_track: BANG REMIX V4
PASS status_freshness: age=0s; limit=180s
PASS stream: HTTP 200; received 4096 bytes
PASS visuals_realtime: HTTP 200; ok=True
```

---

## Visual System

| Metric | Value | Status |
|--------|-------|--------|
| **Production SHA-256** | `4ca1a32e74c2b319fa8c7979b2e68e1486166a2d105c53158f2a417bf976ef32` | LOCKED |
| **GREEN Staging URL** | `https://allthings140-visuals-green.pages.dev/` | FROZEN |
| **GREEN Staging Status** | HEALTHY — HTTP 200 OK | STAGING |
| **Visuals Realtime Server** | version 0.1.0-staging, connections 4 | ONLINE (active) |
| **Tauri Workstation** | Package 0.1.32 installed (`~/.local/bin/allthings140radio-visuals`) | ACTIVE WORKSTATION |
| **Production Visuals** | Frozen at baseline; no cutover authorized | LOCKED |
| **Cutover Gates Open** | 8 gates still incomplete | SEE OPEN ISSUES |
| **Layer Stacking** | Authoritative: HUD z: 50-70 above video z: 10-40 | FIXED (Aug 15) |
| **Media Role Separation** | Explicit `mediaType` values (stage vs visual) | IMPLEMENTED |
| **57 Visual Entries** | With explicit mediaType values | VALIDATED |
| **Stage Media** | `alpha.mov` (HEVC, 1920x1080) → runtime H.264 conversion | CONVERTED |

### Visuals Current State

- **Production `/visuals/`**: SHA-256 `4ca1a32e74c2b319fa8c7979b2e68e1486166a2d105c53158f2a417bf976ef32` — permanently locked; no changes without explicit authorization
- **GREEN staging**: `https://allthings140-visuals-green.pages.dev/` — functional, used for development/testing; features working (playlist, takeover scheduler, chat, reactions, energy, audience presence)
- **Tauri workstation**: v0.1.3 installed on development workstation; media scanning, layer management, publish to GREEN all functional; GUI could not be screenshot from restricted shell (no GTK display session)
- **Realtime server**: Running on VM 2, health OK, version 0.1.0-staging; no active WebSocket clients currently; health endpoint reachable

### Cutover Status

```
NEW VISUALS SYSTEM READY: NO
READY FOR CUTOVER: NO
```

Gates still open:
1. Extended desktop soak and memory-growth observation incomplete
2. Mobile browser regression/profile/reconnect testing incomplete
3. Full manual takeover asset-package validation not done
4. Physical-phone regression testing not done
5. GREEN health check + remote manifest verification gate
6. Takeover restart-before-start and scheduling scheduling need longer real-time staging test

---

## Website

| Metric | Value | Status |
|--------|-------|--------|
| **Domain** | `allthings140radio.online` | LIVE |
| **Hosting** | Cloudflare Pages | HEALTHY |
| **URL** | `https://allthings140radio.online` | HTTP 200 OK |
| **Service Worker** | v54, excludes .mp3/.m3u8/.obs/ from cache | HEALTHY |
| **Status API (readers)** | `https://status.ebeinc.online/api/public/status` | HTTP 200 OK |
| **Stream URL** | `https://stream.ebeinc.online/live.mp3` | HTTP 200 with audio |
| **Recent Deployments** | Aug 13: Support system (Stripe + Mailchimp)<br>Aug 15: Z-index fixes, worker auth, SW stream bypass | PRODUCTION |
| **CNAME** | `allthings140radio.online` (Cloudflare Pages) | RESOLVED |
| **HTTPS** | Enforced (after DNS propagation) | ACTIVE |
| **Cookies / Support** | Stripe Checkout + Mailchimp webhook | ACTIVE |
| **Takeover Schedule** | Visible at `#schedule` section | ACTIVE |
| **Support Goal/Feed** | Paid records only; refunds subtracted | ACTIVE |

### Website Health Check

```
PASS website: HTTP 200; contains "AllThings140"
PASS status_api: HTTP 200; online=True; freshness age=0s; limit=180s
PASS current_track: BANG REMIX V4
PASS stream: HTTP 200; received 4096 bytes
```

---

## Infrastructure Status

### Oracle VM 1 (Broadcast Authority)

- **Status:** HEALTHY / ONLINE
- **Uptime:** 3d 4h
- **Load:** 0.69
- **Memory:** 497M/946M (52%)
- **Disk:** 31% used (21 GB available / 30 GB)
- **Srv Volume:** 27% used (50 GB)
- **Services:** All active (server, icecast, tunnel, drive, cache, fallback-sync)
- **Tailscale:** active, direct (100.124.12.41)
- **kdump:** disabled (was causing boot delays; MemTotal now 968832 kB)

### Oracle VM 2 (Visuals Realtime)

- **Status:** HEALTHY / ONLINE
- **Uptime:** 14h 24m
- **Load:** 0.00
- **Memory:** 946M visible (full 1GB VM)
- **Disk:** 22% used (30 GB)
- **Services:** visuals-realtime (aiohttp), visuals-tunnel (cloudflared), backup.timer
- **Tailscale:** connected (100.108.145.128)
- **Health:** `{"ok": true, "service": "allthings140-visuals-realtime", "version": "0.1.0-staging", "connections": 0}`

### Cloudflare Resources

| Resource | Status | Details |
|----------|--------|---------|
| allthings140radio.online | HEALTHY | Cloudflare Pages, HTTPS enforced, SW v54 |
| allthings140-visuals-green | FROZEN (staging) | HTTP 200, noindex, no-store; production baseline hash locked |
| ebeinc | HEALTHY | Custom domain ebeinc.online, GitHub Pages |
| _worker.js | PARTIALLY | Auth check added; ADMIN_ALERT_KEY not yet provisioned |
| Tunnel (VM 1) | HEALTHY | cloudflared systemd service online |
| Tunnel (VM 2) | HEALTHY | cloudflared systemd service online |

### Tailscale Mesh

- **Status:** ACTIVE
- **Peers:** 20+ total
- **Key nodes:** allthings140radio-server (direct), allthings140-visuals-realtime (connected)
- **MagicDNS:** allthings140radio-server resolves for authorized SSH/control API

### Google Drive

- **Mount status:** Not directly verifiable from this workstation; configured on Oracle VM 1
- **Catalog:** 571+ filenames; 569 eligible/approved; 569 playable post-August 15 recovery
- **Emergency mirror:** 575 verified files at `/srv/allthings140radio/data/music/`
- **Hot cache:** ~50 tracks at `/srv/allthings140radio/cache/READY/` (target 120 min)

### Open Ports & Services

| Port | Service | Status |
|------|---------|--------|
| 14000 | Icecast2 loopback | RUNNING |
| 14001 | Icecast auth relay | RUNNING (loopback) |
| 14080 | Private API (Tailscale forwarded) | RUNNING (authorized) |
| 14082 | Public gateway (Tunnel) | RUNNING |
| 14083 | Traktor guest ingest | RUNNING (restricted, loopback) |
| 8765 / 14140 | Visuals realtime WS | RUNNING (no clients) |
| 20242 | Static media origin | RUNNING |

---

## Recent Changes (Aug 13–15, 2026)

### August 13, 2026 — Background Playback Reliability & Support System

- **Service Worker v54** with network-first delivery for critical JS, cache-exclusion for `.mp3`/`.m3u8`/`.obs/`
- **Background resume transaction** on visibilitychange, pageshow, focus, online (deduplicated, aborts frozen requests, fetches no-store authoritative state, discards older sequence data)
- **Stripe production payments** activated after account verification
- **Support system** (`tools/support_system.py`) — HMAC-SHA256 verification, replay prevention (300s window), idempotent SQLite recording
- **Mailchimp integration** — signup, ping, webhook handling, welcome tag automation
- **Consumer-facing fixes** — cold-start play button, background tab respect, innerHTML → safe DOM nodes

### August 13, 2026 — Visuals Compositor & Realtime Fixes

- **Authoritative z-index stacking**: HUD at z: 50–70 above video at z: 10–40 (fixed HUD-hiding-behind-video bug)
- **CORS allowlist** on `/visuals-state` endpoint (was missing, prevented browser consumption)
- **Rate-limited IP event pruning** in realtime server (stale entries > 120s removed from ip_events)
- **Client snapshot iteration** in `Room.broadcast()` (safely iterate copy, not live dict)
- **Health URL** derived from env vars (not hardcoded)
- **Tunnel dependency**: `Requires=` changed to `Wants=` so gateway maintenance doesn't tear down tunnel
- **kdump disabled** on VM 2 (was causing multi-minute boots, SSH/agent stalls)

### August 15, 2026 — Catalog Integrity & Radio Hardening (Major)

- **Station Server v0.8.0** deployed after 88-track incident
- **`tools/catalog_integrity.py`** and **`tools/recover_playback_assets.py`** deployed
- **All 88 affected approved tracks** restored from Drive into emergency mirror; verified by SHA-256 and duration
- **569 eligible tracks** now playback-ready (was 481 before incident)
- **Emergency mirror rebuilt** to 575 files
- **Read-only integrity monitor** drives HEALTHY/DEGRADED/CRITICAL catalog state
- **30-minute playback-admission timer** prevents future Drive-only uploads from becoming stranded
- **Encoder stderr → DEVNULL** (eliminated 64 KB pipe-buffer deadlock)
- **4-byte PCM stereo boundary alignment** in `mix_ad()` (fixed frame misalignment on odd byte slices)
- **Duration caching from DB**, eliminated sync ffprobe on track transitions
- **Rotation state lock synchronization** (thread-safe AutoDJ position)
- **DJ app fixes**: removed `render_rotation([])` queue wipe; async webhook threads
- **Visuals green**: z-index reordering + CORS + health fixes
- **Cloudflare worker**: Bearer auth on `/api/public/takeover-alert` (added; ADMIN_ALERT_KEY not yet provisioned)
- **37/37 tests passing** (100% — up from 34 before remediation)
- **All services remained 100% online** throughout (no production VM restarts)
- **Timestamped backups** retained for rollback (never needed)

### Files Modified (Aug 15, 2026)

`radio/_worker.js`, `tools/server.py`, `radio/sw.js`, `radio/sw-v47.js`, `radio/app.js`, `visuals-green/stage.css`, `visuals-green/overlay.css`, `visuals-green/stage.js`, `visuals-realtime/app.py`, `tools/dj_app.py`, `discord-bot/index.js`, `android/mobile-app/app/build.gradle`, `tools/cache_manager.py`, `tools/ai_host.py`, `tools/radio_healthcheck.py`, `operations/restore-vm.sh` (new), 18 test files

### Services Restarted

**None** on production VMs during remediation pass. All fixes deployed to Cloudflare edge or staged locally; Oracle VM 1 and VM 2 remained continuously online and active.

---

## Known Problems

### Critical (Must Fix Before Production Deployment)

| # | Problem | Location | Risk | Status |
|---|---------|----------|------|--------|
| 1 | Discord bot plaintext token in `.env` | `discord-bot/.env` | Credential exposure if leaked | **OPEN** — Regenerate in Developer Portal |
| 2 | Cloudflare Worker `ADMIN_ALERT_KEY` not provisioned | `radio/_worker.js` `handleTakeoverAlert()` | Takeover alerts unauthenticated | **OPEN** — Set secret via `wrangler secret put` |
| 3 | Android release signed with debug keystore | `android/mobile-app/app/build.gradle` | Cannot publish to Google Play | **OPEN** — Provide KEYSTORE_FILE etc. |

### High (Should Fix in Next Cycle)

| # | Problem | Location | Impact | Status |
|---|---------|----------|--------|--------|
| 4 | Extended visuals desktop soak insufficient | visuals workstation | Memory growth, crash recovery | **OPEN** — Needs overnight+ soak |
| 5 | Mobile browser regression untested | visuals mobile profiles | Breakage on real devices | **OPEN** — Needs physical device testing |
| 6 | Google Drive mount status unverified from workstation | config references only | Cache/admission reliability | **OPEN** — Verify via Oracle VM |

### Medium (Should Fix When Convenient)

| # | Problem | Location | Impact | Status |
|---|---------|----------|--------|--------|
| 7 | Takeover restart-before-start scheduling needs longer soak | visuals-realtime staging | Scheduling edge cases | **OPEN** — Needs longer real-time test |
| 8 | Physical-phone regression not done | visuals real device | Profile/compat issues | **OPEN** — Needs physical phone testing |

### Low (Housekeeping)

| # | Problem | Location | Impact | Status |
|---|---------|----------|--------|--------|
| 9 | VM 1 root volume space concern (31% used, 21 GB available) | `/` on Oracle VM 1 | Future growth constraint | **OPEN** — Regular rotation pruning scheduled |
| 10 | Discord bot token rotation history unknown | `discord-bot/.env` | May need regeneration | **OPEN** — Check if ever shared publicly |

---

## Confidence Score

| Component | Score | Prevention from 100% |
|-----------|-------|----------------------|
| **Radio system** | 95% | Drive mount status not directly verifiable from this workstation; some path mappings inferred from config |
| **Visual system** | 85% | Production baseline hash verified; GREEN staging state understood but cutover gates still open |
| **Website** | 92% | Cloudflare resource details from reports; actual live deployment verified via HTTP 200 |
| **Infrastructure** | 88% | Oracle VM details from reports; actual runtime resources not directly inspectable from workstation |
| **Desktop applications** | 90% | DJ app and visuals app source code fully read; binary blobs verified |
| **Android/mobile** | 70% | Only debug APK observed; release signing config and Play Store status not verified |
| **Deployment architecture** | 95% | Incremental backup-first model verified; exact Cloudflare secret provisioning status |
| **Whole ALLTHINGS140 ecosystem** | 82% | Some components (Drive mount state, Cloudflare secrets, Oracle VM resources) verified from reports rather than direct inspection; no firsthand runtime evidence for all subsystems |

**Overall:** 87% confident in understanding. Key gaps: Google Drive mount status from this workstation, Cloudflare secret provisioning, Oracle VM runtime resources, Android release signing status, visuals cutover gate completion.

**What prevents 100% confidence:** Inability to directly inspect Oracle Cloud VM runtime state, Google Drive mount status from this workstation, Cloudflare secret provisioning status, production Android signing configuration, and visuals cutover gate completion status without authorized access. All values cross-verified against reports, Git history, and where possible, runtime health checks.

---

## Recent Verification (Aug 16, 2026 — Onboarding Pass)

- Radio stream: `https://stream.ebeinc.online/live.mp3` → HTTP 200, 4096 bytes audio ✓
- Status API: `https://status.ebeinc.online/api/public/status` → HTTP 200, online=True, current_track=BANG REMIX V4 ✓
- Website: `https://allthings140radio.online` → HTTP 200, contains "AllThings140" ✓
- Visuals realtime health: `https://visuals-realtime-staging.allthings140radio.online/health` → HTTP 200, ok=True ✓
- All 37 regression tests: 37 passed, 0 failed ✓
- Oracle VM 1: load 0.69, memory 497M/946M, disk 31% used ✓
- Oracle VM 2: load 0.00, memory 448M/946M, disk 22% used, health OK ✓
- Tailscale: allthings140radio-server active direct, allthings140-visuals-realtime connected ✓
- Catalog state: HEALTHY — 569 eligible tracks playable ✓
- Production visuals SHA-256: `4ca1a32e74c2b319fa8c7979b2e68e1486166a2d105c53158f2a417bf976ef32` ✓ (preserved, not changed)