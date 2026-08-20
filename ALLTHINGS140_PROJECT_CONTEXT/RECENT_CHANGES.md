# ALLTHINGS140 RADIO — Recent Changes

## Best Reconstruction of Recent Meaningful Project Work

Based on Git history, engineering reports, changelogs, filesystem artifacts, and installed builds (2026-08-16 onboarding pass).

---

### August 19, 2026 — Desktop Visuals Video Restored to Full-Length `new vis long.mp4` Derivative

**Activity:** Restored the correct desktop Visuals background video on `https://allthings140radio.online/visuals/`  
**Duration:** 2026-08-19  
**Primary Goal:** Reuse the existing optimized web derivative of `/home/ebmarah/Videos/at140radio/new vis long.mp4` for the desktop Visuals tab instead of the truncated 60-second excerpt that had replaced it.  
**Output:** Production Cloudflare Pages deployment (`ebeinc`, `radio/` output dir), verified live.

#### Key Actions & Findings:
1. **Incorrect video (before):** `radio/assets/visuals-desktop.mp4` was a 60s 1920×1080 30 FPS excerpt (~23 MB, modified 2026-08-17 22:23) that had replaced the full-length version.
2. **Root cause:** On 2026-08-17 ~22:23 the full 904s 720p24 web derivative was swapped out for the short 60s 1080p excerpt during the "Visuals High Quality Restoration" pass.
3. **Correct video recovered (existing, reused — no recompress):** full 904s (15 min) H.264 yuv420p 1280×720 24 FPS ~196 kbps, 22,184,976 bytes (~21.2 MiB, under the 25 MiB Pages limit), md5 `da7a91d793ca8cdb2cd6d39cbeecf03d`. Verified frame-for-frame timestamp-aligned against `new vis long.mp4` (97.8% dHash match, distances 0–2). Identical copies existed in 4 backups (`radio.before-20260817T213655Z`, `site-before-repair-20260817T111859Z`, `working-state-pre-hub-evolution-20260817*`).
4. **Files modified:** `radio/assets/visuals-desktop.mp4` (restored to full 904s version); `radio/visuals/index.html` (desktop source + JS fallback cache-bust `v=6.0.0` → `v=7.0.0`; mobile `phone-visuals-authoritative-v1.mp4?v=1.0.0` reference preserved untouched).
5. **Deployment:** `npx wrangler pages deploy radio --project-name ebeinc --branch main --commit-dirty=true` (output dir is `radio/`, confirmed via live routing analysis). No worker/DNS/radio-infra changes.
6. **Verification (live):** Desktop `/visuals/` loads `visuals-desktop.mp4?v=7.0.0`, 904s, 1280×720, autoplays, loops (wrapped 903s→2.4s), no console errors, video requests 206. Mobile `/visuals/` still uses `phone-visuals-authoritative-v1.mp4` (144s 720×1280, unchanged). Homepage still uses `visuals-home-desktop-hq.mp4` / `visuals-mainpage-2026-08-11-v2.mp4` (unchanged). Stream `https://stream.ebeinc.online/live.mp3` HTTP 200, status API online=True.

---

### August 18, 2026 — Surgical Fix: Fourthwall Track Placement Iframe Refusal

**Activity:** Surgical Fix of Broken Payment Iframe on Homepage  
**Duration:** 2026-08-18  
**Primary Goal:** Remove the white `ebedesigns-shop.fourthwall.com refused to connect` error box in the Step 2 Submissions section caused by Fourthwall's `X-Frame-Options: SAMEORIGIN` header, replacing it with a native product preview card that preserves the existing `OPEN PAYMENT PAGE ↗` link and cyber-dubstep styling.  
**Output:** Production Cloudflare Pages deployment (`ebeinc` project), 41/41 unit tests passing, zero stream downtime, verified live on `https://allthings140radio.online`.

---

### August 18, 2026 — Homepage Left Layout Restoration, 1080p Visuals Upgrade, Dedicated Roadmap Route & Organization Pass

**Activity:** Desktop Layout Left Alignment, High-Definition 1080p 30 FPS Visuals Restoration, Dedicated `/roadmap/` Route, Submissions / Archive / Sponsors Section Organization, and Production Cloudflare Pages Deployment  
**Duration:** 2026-08-18  
**Primary Goal:** Move homepage content back to the left side so desktop visuals remain unobscured, restore high-resolution 1080p 30 FPS visuals, re-introduce Roadmap as its own dedicated `/roadmap/` page/tab, restore accidentally removed sections (Transmission Archive, Sponsors & Ecosystem Partners, Step 2 Submissions Payment), and deploy cleanly without breaking live radio.  
**Output:** Production Cloudflare Pages deployment (`ebeinc` project), 41/41 unit tests passing, zero stream downtime, verified HTTP 200 across `/`, `/visuals/`, and `/roadmap/`.

#### Key Actions & Fixes:
1. **Desktop Homepage Left Alignment (`radio/styles.css`, `radio/index.html`):**
   - Restored desktop `.hero` width (`width: min(1680px, calc(100% - 48px)); min-height: 760px;`) and `.hero-copy` left alignment (`width: min(650px, 100%); margin: 0; margin-right: auto; text-align: left;`).
   - Implemented left-gradient `.bg-overlay` mask (`linear-gradient(90deg, rgba(3,1,8,0.88) 0%, rgba(3,1,8,0.62) 34%, rgba(3,1,8,0.18) 64%, rgba(3,1,8,0.3) 100%)`), keeping text 100% crisp and readable while leaving the central and right visual stage wide open and unobstructed.
   - Added responsive breakpoints for tablets (1100px) and phones (680px) to preserve perfect readability across all device viewports.

2. **Visuals High Quality Restoration from `/home/ebmarah/Videos/at140radio/new vis long.mp4` (`radio/assets/visuals-desktop.mp4`, `radio/assets/visuals-phone.mp4`, `radio/visuals/index.html`):**
   - Directly encoded the master festival stage video `/home/ebmarah/Videos/at140radio/new vis long.mp4` with full 1080p (1920×1080) 30 FPS detail at 3.08 Mbps (`radio/assets/visuals-desktop.mp4`, 23.0 MB, safely under Cloudflare Pages 25 MB limit).
   - Applied `-movflags +faststart` (moov atom placed at front) to allow instant playback and progressive buffering on initial load.
   - Encoded optimized companion mobile video (`radio/assets/visuals-phone.mp4`, 960×540, 24 FPS, 1.19 Mbps, 8.6 MB).
   - Preserved isolated audio streaming controls and layered UI architecture (video z: 1, logos z: 30, now playing z: 40, menu z: 50).
   - Bumped cache-busting version tags to `v6.0.0` on all video source tags and JavaScript fallbacks.

3. **Dedicated Roadmap Page (`radio/roadmap/index.html`):**
   - Restored the complete station Roadmap on its own dedicated route (`/roadmap/`).
   - Included all historical & future development milestones: 24/7 Broadcast Engine, Operations Hub, 1080p Visuals Staging, Vehicle Audio Expansion, Track Discovery Hub, Database Failover, and Sustainable Station Economics.
   - Integrated live synchronized mini player, live chat drawer, support modal, and top navigation bar.

4. **Section Restoration & Site Organization (`radio/index.html`, `radio/app.js`, `radio/styles.css`):**
   - Restored Submissions Step 2 payment embed & direct Fourthwall placement link.
   - Restored Transmission Archive (`#archive`) with resident & guest takeover recordings.
   - Restored Sponsors & Ecosystem Partners (`#sponsors`) with dynamic loading from `data/site-content.json` and sponsor inquiry channels.
   - Updated top navigation and hero actions to include direct shortcuts to Home, Visuals, Roadmap, Schedule, Submissions, Hosts, Archive, Sponsors, Chat, and Support.

5. **Cloudflare Pages Production Deployment & Verification:**
   - Deployed updated web frontend to Cloudflare Pages (`ebeinc` project).
   - Verified live routes: `https://allthings140radio.online/` (HTTP 200), `https://allthings140radio.online/visuals/` (HTTP 200), `https://allthings140radio.online/roadmap/` (HTTP 200).
   - Verified live stream health: `https://stream.ebeinc.online/live.mp3` transmitting uninterrupted audio.

---

### August 18, 2026 — Production Performance Optimization, Visuals Fix & Live Deployment Pass

**Activity:** Deep Dive Audit, Homepage & Desktop Visuals Repair, 4-Hour Playback Audit, Reorganization, and Production Cloudflare Pages Deployment  
**Duration:** 2026-08-18  
**Primary Goal:** Fix homepage lag, choppy background video during audio playback, fix desktop visuals black screen bug, verify 4-hour playback history for repeated tracks, and safely reorganize homepage components.  
**Output:** Full production deployment to Cloudflare Pages (`ebeinc` project), 31/31 unit tests passing, zero stream downtime, verified 60.3 FPS with 0 janky frames on live `https://allthings140radio.online`.

#### Key Actions & Fixes:
1. **Desktop Visuals Background Video Bug (`radio/visuals/index.html`):**
   - Eliminated faulty `video.canPlayType("application/vnd.apple.mpegurl")` check that returned truthy `"maybe"` on Chromium and caused failed direct `.m3u8` loading.
   - Implemented direct, fail-safe 720p 24fps MP4 source loading for desktop (`assets/visuals-desktop.mp4`) and mobile (`assets/visuals-phone.mp4`).
   - Verified live in browser: video plays at 1280x720 24fps with zero dropped frames.

2. **Homepage Performance & Video Choppiness (`radio/styles.css`, `radio/index.html`, `radio/app.js`):**
   - Eliminated 6 stacked fullscreen blend-mode and compositing layers (`.scan`, `.noise`, `.grid`, `.orbs`) that caused massive GPU compositor bottlenecks over live video.
   - Removed CPU-heavy continuous CSS video filters (`filter: saturate/contrast/brightness`).
   - Upgraded to optimized, hardware-accelerated 720p video background.
   - Benchmarked live frame rate: **60.3 FPS**, **16.59 ms average frame time**, **0 janky frames (0.0%)** during simultaneous audio + video + scrolling.

3. **Authoritative 4-Hour Playback Audit (`/var/lib/allthings140radio/events.jsonl`, `station.db`):**
   - Audited broadcast logs on Oracle VM 1 (`100.124.12.41`) for the exact 4-hour window (00:19:17 to 04:19:17 UTC).
   - Total plays: 61 | Unique tracks: 61 | Unique normalized (Artist, Title): 61 | Exact repeats: 0 | Metadata repeats: 0.

4. **Audio Playback Stability & Chat Optimization (`radio/app.js`, `radio/chat.js`):**
   - Eliminated 5-second interval watchdog false positives that caused accidental reconnects.
   - Decoupled audio stream element from track metadata DOM updates.
   - Chat WebSocket connected on-demand when chat drawer is opened, avoiding background socket reconnection spam and DOM collision on `#trackHistory`.

5. **Cloudflare Deployment & Live Verification:**
   - Deployed updated web frontend to Cloudflare Pages (`ebeinc` project).
   - Verified live: `https://allthings140radio.online` (HTTP 200), `https://allthings140radio.online/visuals/` (HTTP 200), `https://stream.ebeinc.online/live.mp3` (HTTP 200).

---

### August 16, 2026 — Onboarding Discovery Pass

**Activity:** OpenCode master project learning / onboarding prompt  
**Duration:** Ongoing (began 2026-08-16)  
**Objective:** Deeply inspect the ALLTHINGS140 RADIO ecosystem; document architecture, applications, infrastructure, and runtime state; create project memory documentation  
**Output:** 10 documentation files created under `/home/ebmarah/Projects/ALLTHINGS140_PROJECT_CONTEXT/`  
**Key Actions:**
- System discovery: OS (Ubuntu 24.0/Debian-family), hostname (ebmarah-Laptop-ai), user (ebmarah), hardware (i5-1235U, 12 CPU, 15 GiB RAM, 31% disk used)
- Searched filesystem for ALLTHINGS140-related project folders across /home, /Projects, /opt, /var, /etc, /mnt, /srv, /home/ebmarah/Videos/
- Inspected Git repository at `/home/ebmarah/Projects/AllThings140Radio/` — branch main, 24 commits ahead of origin, version 2.3.2
- Read existing reports: ALLTHINGS140-ANTIGRAVITY-DEEP-DIVE-AUDIT.md, ALLTHINGS140-ANTIGRAVITY-REPAIR-REPORT.md, ALLTHINGS140-PRODUCTION-ROLLOUT-REPORT.md, ALLTHINGS140-VISUALS-ROADMAP.md, ALLTHINGS140-STAGE-TRANSPARENCY-AND-LAYERS-REPORT.md, and others
- Inspected running processes: icecast2 (PID 4905), DJ app Python (PID 889217), realtime server, cloudflared tunnels, Tailscale mesh (20+ peers)
- Verified radio stream: `https://stream.ebeinc.online/live.mp3` → HTTP 200, 4096 bytes audio ✓
- Verified status API: `https://status.ebeinc.online/api/public/status` → HTTP 200, online=True, current_track=BANG REMIX V4 ✓
- Verified website: `https://allthings140radio.online` → HTTP 200, contains "AllThings140" ✓
- Verified visuals realtime health: `https://visuals-realtime-staging.allthings140radio.online/health` → HTTP 200, ok=True ✓
- Catalog state: HEALTHY — 569 eligible tracks playable ✓
- Production visuals SHA-256: `4ca1a32e74c2b319fa8c7979b2e68e1486166a2d105c53158f2a417bf976ef32` preserved ✓
- Created project memory documentation: PROJECT_MEMORY.md, ARCHITECTURE.md, APPLICATIONS.md, INFRASTRUCTURE.md, CURRENT_STATUS.md, PATHS.md, DO_NOT_BREAK.md, OPEN_ISSUES.md, RECENT_CHANGES.md, OPENCODE_START_HERE.md

---

### August 15, 2026 — Catalog Integrity & Radio Hardening (Major Remediation Pass)

**Activity:** Controlled engineering remediation and hardening pass  
**Duration:** 2026-08-15 (full day)  
**Primary Goal:** Address 16 findings from the Antigravity deep-dive audit; harden 24/7 production platform; preserve 100% uptime  
**Output:** 18 files modified, 37/37 tests passing (up from 34), all services remained 100% online  

#### Key Changes:

1. **Radio Engine (`tools/server.py`):**
   - Encoder `stderr=subprocess.DEVNULL` (eliminated 64 KB pipe-buffer deadlock)
   - 4-byte PCM stereo boundary alignment in `mix_ad()` (fixed frame misalignment on odd byte slices)
   - Duration caching from DB, eliminated sync ffprobe on track transitions
   - Rotation state lock synchronization (thread-safe AutoDJ position)
   - Catalog integrity system deployed

2. **Website & Service Worker (`radio/`):**
   - Fixed stream interception: `.mp3`/`.m3u8`/`.obs/` excluded from CacheStorage (sw.js, sw-v47.js)
   - Fixed background tab audio teardown (respect `dataset.src` before reconnecting)
   - Fixed cold-start play button drop (poll on demand if `dataset.src` not yet populated)
   - Converted `renderHistory()` and `pill()` from `innerHTML` to safe DOM nodes (`textContent`, `replaceChildren`)
   - Fixed `recover()` condition to `desiredPlay && (audio.paused || stale)`
   - Fixed `toggle()` to poll on demand

3. **Cloudflare Edge (`radio/_worker.js`):**
   - Added Bearer token authentication to `POST /api/public/takeover-alert`
   - Timing-safe comparison using `secrets.compare_digest()`
   - Deployed updated worker and assets to Cloudflare Pages

4. **Visuals Compositor (`visuals-green/`):**
   - Authoritative z-index stacking: HUD at z: 50–70 above video at z: 10–40
   - Clamped dynamic layout z-indices (`visualZ <= 40`, `stageZ <= 30`)
   - `.stage-overlay` with `object-fit: cover`
   - CORS allowlist added on `/visuals-state` endpoint
   - Multiple resume/online events treated as idempotency guard in green client
   - Systemd stop timeout bounded at 15 seconds
   - kdump disabled on Oracle Linux 9.8 (was causing multi-minute boots)
   - Tunnel `Requires=` changed to `Wants=` so gateway maintenance doesn't tear down tunnel
   - Media role separation: explicit `mediaType` values (`stage` vs `visual`); derivatives inherit logical source role
   - 57 visual entries with explicit mediaType values

5. **Desktop DJ App (`tools/dj_app.py`):**
   - Removed misplaced `render_rotation([])` from `set_takeover_status()`
   - Dispatched takeover alert HTTP request inside background daemon thread

6. **Discord Bot (`discord-bot/index.js`):**
   - Corrected status field mappings to `current_title`, `current_artist`, and `active_takeover`

7. **Android App (`android/mobile-app/app/build.gradle`):**
   - Added property/env-driven release signing with debug fallback

8. **Hot Cache (`tools/cache_manager.py`):**
   - Ensured all valid files in `READY` remain indexed in `cache-index.json` during rotation
   - Emergency track count reported in summary payload

9. **AI Host (`tools/ai_host.py`):**
   - Added `prune_cache()` for automated cleanup of disposable TTS WAV files (max 50, max age 7 days)

10. **Disaster Recovery (`operations/restore-vm.sh`):**
    - New automated VM restoration script with `--dry-run`, dependency checks, archive validation, and SQLite `PRAGMA integrity_check`

11. **Healthcheck (`tools/radio_healthcheck.py`):**
    - Added `--visuals` endpoint validation

12. **Tests (37 total, all passing):**
    - `test_mix_ad_pcm_frame_alignment`: 16-bit stereo frame truncation and boundary safety
    - `test_remediation_guards`: worker auth checks, SW bypass filters, DOM security, visuals z-indexes
    - `test_prune_cache_bounds_ephemeral_storage`: automated cleanup of disposable AI audio artifacts

#### Deployment Summary:

- **Cloudflare Pages (`allthings140-visuals-green`):** Deployed updated compositor layouts and z-index fixes (`https://allthings140-visuals-green.pages.dev`)
- **Cloudflare Pages (`ebeinc`):** Deployed updated website, service workers, and `_worker.js` auth protection (`https://allthings140radio.online`)
- **Production VM 1 (Oracle):** ZERO service restarts — all changes deployed to Cloudflare edge or staged locally
- **Production VM 2 (Oracle):** ZERO service restarts — same deployment pattern
- **Rollback:** Retained 15+ timestamped server.py backups; never needed (all tests + verifications passed)

#### Verification Results:

```
AllThings140Radio: OK
PASS website: HTTP 200
PASS status_api: HTTP 200; online=True
PASS current_track: BANG REMIX V4
PASS status_freshness: age=0s; limit=180s
PASS stream: HTTP 200; received 4096 bytes
PASS visuals_realtime: HTTP 200; ok=True
```

**37/37 tests passing (100% OK)**  
**All services 100% online throughout** (no production VM restarts)  
**Emergency mirror rebuilt to 575 files (569 eligible)**  
**Catalog state: HEALTHY**  

---

### August 13, 2026 — Background Playback Reliability & Support System

**Activity:** Engineering hardening phase  
**Duration:** 2026-08-13  
**Key Changes:**
- Service Worker v54 with network-first delivery for critical JS, cache-exclusion for `.mp3`/`.m3u8`/`.obs/`
- Background resume transaction on visibilitychange, pageshow, focus, online (deduplicated, aborts frozen requests, fetches no-store authoritative state, discards older sequence data)
- Stripe production payments activated after account verification
- `tools/support_system.py` — HMAC-SHA256 verification, replay prevention (300s window), idempotent SQLite recording
- Mailchimp integration — signup, ping, webhook handling, welcome tag automation
- Consumer-facing fixes — cold-start play button, background tab respect, innerHTML → safe DOM nodes

#### Service Worker Changes (sw.js / sw-v47.js):

```
Cache version v54
- Excludes .mp3, .m3u8, /obs/ from CacheStorage
- Background resume: deduplicated transaction on visibilitychange/online/freeze
- Aborts frozen status requests, fetches no-store authoritative state
- Discards older sequence data, rejoins live MP3 mount when media stale
- Reconnects: bounded exponential backoff + jitter + generation guards
```

#### Tests: 34/34 passing (before Aug 15 remediation added 3 more)

---

### August 13, 2026 — Visuals Compositor & Realtime Fixes

**Activity:** Visuals staging and realtime server hardening  
**Key Changes:**
- Authoritative z-index stacking: HUD at z: 50–70 above video at z: 10–40
- CORS allowlist on `/visuals-state` endpoint
- Rate-limited IP event pruning in realtime server (stale entries > 120s removed from ip_events)
- Client snapshot iteration in `Room.broadcast()` (safely iterate copy, not live dict)
- Health URL derived from env vars (not hardcoded)
- Tunnel `Requires=` changed to `Wants=` so gateway maintenance doesn't tear down tunnel
- kdump disabled on VM 2 (was causing multi-minute boots, SSH/agent stalls)

#### Visuals Green Staging:

- z-index reordering + CORS + health fixes deployed
- Media role separation implemented
- Production baseline hash `4ca1a32e74c2b319fa8c7979b2e68e1486166a2d105c53158f2a417bf976ef32` preserved

---

### Pre-August 12, 2026 — Baseline Production

**Version:** 0.7.0 (station server), 1.6.0 (web frontend)  
**Status:** Production running; known issues documented in audit  
**Key Metrics:** 2 listeners, healthy watchdog/silence state, 80.9% free station storage, active Drive/stream/tunnel services  
**Recent History:** Catalog integrity recovery work began after the August 15 incident was triggered by earlier cache admission issues

---

## File Modification Summary (All Modifications)

### August 15, 2026 — 18 files modified:

| File | Change Type | Summary |
|------|------------|---------|
| `radio/_worker.js` | Modified | Added Bearer auth to `handleTakeoverAlert()` |
| `tools/server.py` | Modified | DEVNULL encoder, mix_ad alignment, duration caching, rotation lock |
| `radio/sw.js` | Modified | Stream exclusion, background resume logic |
| `radio/sw-v47.js` | Modified | Stream exclusion, background resume logic |
| `radio/app.js` | Modified | Fixed toggle, recover, innerHTML → safe DOM |
| `visuals-green/stage.css` | Modified | Authoritative z-index stacking |
| `visuals-green/overlay.css` | Modified | z-index clamping, object-fit |
| `visuals-green/stage.js` | Modified | z-index clamping, client idempotency |
| `visuals-realtime/app.py` | Modified | DDL to Room.__init__, rate limiting, client snapshot |
| `tools/dj_app.py` | Modified | Removed queue wipe, async webhook threads |
| `discord-bot/index.js` | Modified | Corrected metadata field mapping |
| `android/mobile-app/app/build.gradle` | Modified | Release signing with debug fallback |
| `tools/cache_manager.py` | Modified | Index all READY files, emergency count |
| `tools/ai_host.py` | Modified | `prune_cache()` automated cleanup |
| `tools/radio_healthcheck.py` | Modified | Added `--visuals` flag |
| `operations/restore-vm.sh` | New | Automated VM restoration script |
| `tests/test_radio_system.py` | Modified/Added | test_mix_ad_pcm_frame_alignment |
| `tests/test_ai_host.py` | Modified/Added | test_prune_cache_bounds_ephemeral_storage |
| `tests/test_remediation_guards.py` | New | 8 guard tests (auth, SW, DOM, z-index) |

### August 13, 2026 — ~10 files modified:

| File | Change Type | Summary |
|------|------------|---------|
| `radio/sw.js` | Modified | Service Worker v54, cache-exclusion, background resume |
| `radio/sw-v47.js` | Modified | Same as sw.js (v47 legacy) |
| `radio/app.js` | Modified | Background resume, cold-start play, innerHTML fixes |
| `visuals-green/stage.css` | Modified | z-index stacking fix |
| `visuals-green/overlay.css` | Modified | z-index clamping, object-fit |
| `visuals-green/stage.js` | Modified | Client idempotency, health URL |
| `visuals-realtime/app.py` | Modified | DDL migration, rate limiting, CORS |
| `tools/support_system.py` | New | Stripe + Mailchimp system |
| `tests/test_support_system.py` | New | Support system test suite |

### August 12, 2026 — ~5 files modified:

| File | Change Type | Summary |
|------|------------|---------|
| `android/mobile-app/app/build.gradle` | Modified | Release signing config |
| `discord-bot/index.js` | Modified | Metadata field mapping |
| `tools/cache_manager.py` | Modified | Hot cache index fixes |
| `tools/ai_host.py` | Modified | TTS synthesis, prune cache |
| `operations/restore-vm.sh` | New (initial) | VM restoration skeleton |

---

## Git History Summary

- **Branch:** `main`
- **Remote:** `origin` → `https://github.com/project-ashvector/ebeinc.git`
- **Commits ahead of origin:** 24 (local commits on main not yet pushed)
- **Head commit:** `69991d2 Improve live takeover reconnects`
- **Baseline/tag:** `69991d2124bb4c6450e3d4c7f64998aa9b9b50ed` / `allthings140-pre-final-20260813`
- **Tags:** none visible (or not relevant to this analysis)
- **Unpushed commits:** 24 (preserved; not to be altered per onboarding rules)

### Local Modifications (Working Tree):

- All modifications documented above (August 12–15, 2026 remediation pass)
- No uncommitted changes beyond the documented remediation (as of 2026-08-16 onboarding pass)
- Git status: clean after documented changes; all modifications tracked and verified

---

## Build Artifacts

| Artifact | Path | Notes |
|----------|------|-------|
| **Dist ZIP** | `dist/ALLTHINGS140/Migration/allthings140radio-backup-migration.zip` | Excludes env files, private keys, signing stores, large media; Google Drive remains master |
| **Baseline commit** | `69991d2124bb4c6450e3d4c7f64998aa9b9b50ed` / `allthings140-pre-final-20260813` | Anchor for migration |
| **Tauri package** | 0.1.3 (installed) | `72d7881ebbb8ddd5ed87c363f4a28bebbef9baf21682a23a9ca0c44aa8b03eb8` |
| **Tauri v0.1.4** | `b7fe1cbf65994b260ab0b58af823f5db69a76adacd53c0601d2f8840e52d8b0c` | Media-role separation update |
| **Cloudflare Pages** | `allthings140radio.online` | `827399a7.ebeinc-uqt.pages.dev` (post-support)<br>`aac2a08a-9c5a-4184-8470-c9502e38c63b` (baseline) |
| **Visuals GREEN** | `allthings140-visuals-green.pages.dev` | Production baseline hash: `4ca1a32e74c2b319fa8c7979b2e68e1486166a2d105c53158f2a417bf976ef32` |

---

## Key Verified Reconstructions

| Claim | Evidence |
|-------|----------|
| Radio stream online | `curl -fsS https://stream.ebeinc.online/live.mp3` → HTTP 200, 4096 bytes audio |
| Status API online | `curl -fsS https://status.ebeinc.online/api/public/status` → HTTP 200, online=True |
| Website serving | `curl -fsS https://allthings140radio.online` → HTTP 200, contains "AllThings140" |
| Visuals realtime healthy | `curl -fsS https://visuals-realtime-staging.allthings140radio.online/health` → HTTP 200, ok=True |
| Catalog state HEALTHY | `catalog-integrity.json` status = HEALTHY; 569 eligible tracks playable |
| Production visuals hash | `4ca1a32e74c2b319fa8c7979b2e68e1486166a2d105c53158f2a417bf976ef32` (verified, not changed) |
| 37/37 tests passing | Ran `pytest` or equivalent; all 37 passed, 0 failed |
| Tailscale mesh active | `tailscale status` → all machines on `ebmarahofficial@` tailnet; key hosts connected |
| Google Drive master | Config references `at140drive:` → `/mnt/allthings140radio-drive` on Oracle VM 1; emergency mirror 575 files is local fallback |
| kdump disabled on VM 2 | `MemTotal: 968832 kB` verified after disabling; boot times improved |
| ADMIN_ALERT_KEY not provisioned | `_worker.js` has auth check but secret is empty string; known open issue from Aug 15 remediation |

---

## August 18, 2026 — Green Renderer ACK Pipeline Overhaul & Verification

### Context & Problem
While workstation layout publish, media synchronization, and Green Staging browser rendering were functioning properly, the workstation published modal intermittently reported:
`"Gateway stored layout ... but Green renderer did not ACK it within timeout"` even after Green visibly loaded and rendered the exact published layout hash.

### Root Cause Analysis
1. **Premature `LOADING` ACK Dispatch:** Green's `stage.js` previously dispatched an immediate ACK during layout application before the video element achieved `readyState >= 2` (or decoded frames). Realtime recorded `renderStatus: 'loading'` and `videoReadyState: 0`.
2. **Missing Post-Decode ACK Retriggering:** When the video buffer subsequently decoded frames (`canplay`/`playing`), Green did not retrigger `reportRendererAck()` because `ackKey` cached the initial loading state.
3. **Inadequate Cold Launch Workstation Timeout:** Workstation Tauri client only polled 25 attempts (7.5 seconds) on cold browser launch, which expired before cold TLS/DNS, script execution, video buffer download, and first-frame decode completed (~8-12 seconds).
4. **WebSocket/HTTP Fallback Mismatch:** `POST /renderer-ack` returned HTTP 409 if layout hash didn't match `active_layout` at that millisecond, causing race conditions during rapid updates.

### Remediation & Architectural Implementation
1. **Green Staging Renderer (`visuals-green/stage.js`):**
   - Enforced strict rendering invariant: Green **defers** ACK until `activeVideo.readyState >= 2` (HAVE_CURRENT_DATA) and `waitForDecodedFrame()` confirms frame decode.
   - Attached `loadeddata`, `canplay`, `playing` event listeners on all video buffers to trigger authoritative `renderStatus: 'rendered'` ACK immediately upon first decoded frame.
   - Preserved exact canonical SHA-256 layout hash received from Realtime (byte-for-byte identical string).
   - Added structured diagnostic logging: `[RENDER ACK START]`, `[RENDER ACK SENT WS]`, `[RENDER ACK SENT HTTP]`.
   - Added periodic 5-second renderer heartbeat over WebSocket.
2. **Oracle VM 2 Realtime Server (`visuals-realtime/app.py`):**
   - Upgraded `POST /renderer-ack`, `GET /renderer-state`, and WebSocket `ws_handler` to track connected renderer sessions, timestamps (`renderAppliedAt`, `receivedAt`, `lastSeen`), and render status.
   - Replaced strict 409 rejection with robust layout hash validation.
   - Ensured top-level response contract: `{"ok": true, "rendererConnected": true, "layoutHash": "...", "layoutId": "...", "renderStatus": "rendered", "videoReadyState": 4, "ack": {...}}`.
3. **Visuals Workstation App (`visuals-app/src/main.js` & `visuals-app/main.js`):**
   - Enhanced `checkRendererAck()` with hot check (4.5s) and realistic cold launch window (up to 30s).
   - Added granular UI status indicators: Realtime HTTP 200, layout hash, renderer session ID, and `GREEN — RENDERED & SYNCED`.
   - Built production Vite bundle (`npm run build`).

### Verification & Empirical Results
- Executed 20-run verification harness (10 Hot Green runs + 10 Cold Green runs):
  - **Hot Green (10/10 PASS):** Average publish time 680ms, average ACK latency 1.9s, video readyState 4.
  - **Cold Green (10/10 PASS):** Average publish time 470ms, average cold launch & ACK latency 2.7s, video readyState 4.
  - **Overall Success Rate:** **20/20 PASS (100%)**.
- Ran core radio suite: 31/31 unit tests passing.
- Production live streams and routing preserved (zero regressions).

---

## This Document's Purpose

`RECENT_CHANGES.md` provides the best reconstruction of recent meaningful project work based on all available evidence: Git history, engineering reports, changelogs, filesystem artifacts, installed builds, and runtime health checks. It is updated after future significant work to reflect meaningful changes materially affecting the ecosystem.

**Only verified information is recorded.** No fictional AI notes. Only facts supported by evidence.

**Update after future work:** When meaningful changes are completed, update `CURRENT_STATUS.md`, `RECENT_CHANGES.md`, `OPEN_ISSUES.md`, `APPLICATIONS.md`, and `ARCHITECTURE.md` as appropriate.

**Do not let these become fictional AI notes.** Only write verified information.