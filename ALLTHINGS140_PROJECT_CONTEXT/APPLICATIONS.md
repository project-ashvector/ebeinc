# ALLTHINGS140 RADIO — Applications

## Discoveries from Onboarding Pass (2026-08-16)

This document catalogues every ALLTHINGS140-related application discovered during the onboarding pass, with its current state, version, and key characteristics.

---

### 1. Station Broadcast Server

| Field | Value |
|-------|-------|
| **Name** | AllThings140Radio Server (or just "the Server") |
| **Path** | `/home/ebmarah/Projects/AllThings140Radio/tools/server.py` (source)<br>`/opt/allthings140radio-server/server.py` (installed on Oracle VM 1) |
| **Version** | 0.8.0 |
| **Tech Stack** | Python 3 (standard library: sqlite3, hashlib, threading, subprocess, http.server, json, uuid, os, re, time, uuid, ipaddress, base64, array, collections, http.server, socket, select, signal, traceback, urllib.error, urllib.parse, urllib.request, dataclasses, collections, defaultdict, deque, http.HTTPStatus, http.server, pathlib, typing)<br>FFmpeg (external)<br>Icecast 2 (external) |
| **Primary Purpose** | Authoritative 24/7 AutoDJ broadcast engine. Owns accounts, approved music library, AutoDJ process, review queue, settings, and the public listener page. |
| **Ports** | 14000 loopback Icecast<br>14080 private control API (loopback, Tailscale forwarded)<br>14082 loopback public gateway<br>14083 restricted Traktor guest ingest<br>14001 Icecast auth relay (loopback) |
| **Runtime Dependencies** | FFmpeg (binary, invoked via subprocess), SQLite3, Icecast 2, Google Drive (via rclone on VM), config.json |
| **Key Functions** | AutoDJ timeline, track scheduling, FFmpeg encoding, Ducking ad mixer, SQLite catalog management, public status API, Icecast auth relay, predictive hot cache, 30-min playback admission timer, catalog integrity verification |
| **Recent Fixes (Aug 15, 2026)** | • Encoder stderr → DEVNULL (deadlock eliminated)<br>• 4-byte PCM stereo boundary alignment in mix_ad()<br>• Duration caching from DB, eliminated sync ffprobe<br>• Rotation state lock synchronization<br>• Catalog integrity system deployed<br>• Emergency mirror rebuilt to 575 files (569 eligible) |
| **Health Check** | `curl -fsS http://127.0.0.1:14080/api/health` — must return OK<br>`curl -fsS https://stream.ebeinc.online/live.mp3` — must return audio<br>`tools/allthings140-diagnose.py` — full system check |
| **Current Status** | **ACTIVE PRODUCTION** — Uptime 3d 4h, load 0.69, memory 497M/946M, disk 31% used, 571 tracks in DB (569 approved), stream online, 2 listeners |
| **Critical Safeguards** | Never deploy without timestamped backup; never restart without verifying local health first; never ignore catalog-integrity.json status |

---

### 2. Desktop DJ Workstation

| Field | Value |
|-------|-------|
| **Name** | Desktop DJ Application |
| **Path** | `/home/ebmarah/Projects/AllThings140Radio/tools/dj_app.py` (source)<br>`/opt/allthings140radio-dj/dj_app.py` (installed on Oracle VM 1) |
| **Version** | 0.7.0 |
| **Tech Stack** | Python 3, Tkinter (ttk), urllib, json, sqlite3, pathlib, array |
| **Primary Purpose** | Administrative control application: catalog browsing, rotation inspection, ad scheduling, live takeover triggers, support transaction review, catalog integrity reports. |
| **Ports** | Private API port 14080 (loopback only, Tailscale forwarded) |
| **Runtime Dependencies** | station.db (SQLite), config.json, ai_host.py, support_system.py, catalog_integrity.py, radio_extensions.py |
| **Key Functions** | Catalog browsing + approval, rotation inspection + advancement, ad scheduling + batch insert, live takeover triggers, support transaction review, catalog integrity reports, track search + filter, artist cooldown management |
| **Recent Fixes (Aug 15, 2026)** | • Removed `render_rotation([])` queue wipe from `set_takeover_status()`<br>• Takeover alert HTTP dispatch moved to background daemon thread<br>• No more accidental queue wipe on takeover status change |
| **Health Check** | `python3 tools/radio_healthcheck.py` — full system check<br>`curl -fsS http://127.0.0.1:14080/api/health` — API reachability |
| **Current Status** | **ACTIVE TOOL** — Running as user process (PID 889217), UI active, private API accessible via Tailscale<br>**Known issue:** Plaintext Discord bot token in `discord-bot/.env` (separate repo, not part of radio app) |
| **Critical Safeguards** | Never operate on production station.db without backup; catalog integrity must be HEALTHY before making playlist changes |

---

### 3. Web Listener Frontend

| Field | Value |
|-------|-------|
| **Name** | Web Listener Frontend (PWA) |
| **Path** | `/home/ebmarah/Projects/AllThings140Radio/radio/` (source)<br>Deployed to Cloudflare Pages: `allthings140radio.online` |
| **Version** | 1.6.1 |
| **Tech Stack** | HTML5, Vanilla CSS, Vanilla JavaScript, Service Worker v54, Service Worker v47 |
| **Primary Purpose** | Public listener interface: audio player, chat, Stripe support tip jar, mobile responsive UI, background playback recovery. |
| **Key Files** | `index.html`, `app.js`, `styles.css`, `sw.js`, `sw-v47.js`, `support.js`, `support.css`, `chat.js`, `promo.js`, `listener-controls.css`, `engagement.css`, `atomic-pressure.css` |
| **Ports** | None (frontend-only; APIs reachable via Cloudflare edge) |
| **Runtime Dependencies** | Cloudflare Pages, Cloudflare Tunnel, status.ebeinc.online, stream.ebeinc.online |
| **Key Features** | • Audio player with continuous MP3 stream<br>• Background playback recovery (visibilitychange, pageshow, focus, online)<br>• Chat interface (WebSocket via Durable Objects)<br>• Stripe support tip jar (one-time)<br>• Mobile responsive design<br>• Takeover schedule view<br>• Support goal/feed display<br>• Now Playing metadata |
| **Service Worker (sw.js / sw-v47.js)** | • Cache version v54<br>• Excludes .mp3, .m3u8, /obs/ from CacheStorage<br>• Background resume: deduplicated transaction on visibilitychange/online/freeze<br>• Aborts frozen status requests, fetches no-store authoritative state<br>• Discards older sequence data, rejoins live MP3 mount when media stale<br>• Bounded exponential backoff + jitter + generation guards on reconnect |
| **Recent Fixes (Aug 13-15, 2026)** | • Fixed stream interception (`.mp3`/`.m3u8` excluded from CacheStorage)<br>• Fixed background tab audio teardown (respect dataset.src before reconnecting)<br>• Fixed cold-start play button drop (poll on demand if dataset.src not yet populated)<br>• Converted renderHistory() and pill() from innerHTML to safe DOM nodes<br>• Fixed recover() condition to `desiredPlay && (audio.paused || stale)`<br>• Fixed toggle() to poll on demand |
| **Current Status** | **ACTIVE PRODUCTION** — Deployed to Cloudflare Pages, HTTP 200 OK, online listeners, stream healthy |
| **Confidence** | 92% — Fully verifiable from source and deployed state |

---

### 4. Visuals Desktop App (Tauri Workstation)

| Field | Value |
|-------|-------|
| **Name** | ALLTHINGS140Radio Visuals (Tauri workstation) |
| **Path** | `/home/ebmarah/Projects/AllThings140Radio/visuals-app/` (source & build)<br>Installed as desktop application |
| **Version** | 0.1.32 |
| **Tech Stack** | Rust (Tauri v2) + Vanilla JS / Vite (frontend)<br>package.json scripts: `dev` (vite --host 127.0.0.1 --port 14340), `build` (vite build), `tauri` (tauri cli)<br>Dependencies: @tauri-apps/api ^2.8.0, @tauri-apps/plugin-dialog ^2.4.0, sha2 ^0.10 |
| **Primary Purpose** | Live visual show-control workstation: 7-layer canvas compositing, aspect ratio transformation, media probing/transcoding, staging deployment, layer management, WYSIWYG workshop, independent scrolling shell, deterministic canonical geometry. |
| **Key Files** | `src-tauri/src/main.rs`, `src-tauri/src/lib.rs`, `src/main.js`, `src/style.css`, `package.json`, `tauri.conf.json`<br>Visual files: `/home/ebmarah/Videos/at140radio/desktop visuals/stage/alpha.mov`, `/home/ebmarah/Videos/at140radio/desktop visuals/visuals/` (57 MP4 files) |
| **Ports** | 14340 (dev mode, Vite HMR)<br>IPC: `ipc: http://ipc.localhost http://127.0.0.1:*` (Tauri plugin) |
| **Runtime Dependencies** | FFmpeg (binary, for media probing/transcoding), dirs (for data directory), ffprobe (for media info)<br>Tauri API for: shell (xdg-open), clipboard, dialog, file operations |
| **Key Features** | • Unified 16:9 canonical geometry engine shared across Workstation preview & Green staging<br>• Fully async non-blocking Rust backend (`spawn_blocking` + in-memory `sha2` hashing) eliminating UI thread freezes<br>• 3-column independent scroll layout with min-height: 0 protection across all resolutions<br>• Dedicated GREEN / STAGING workstation toolbar with live sync status pill & 1-click actions<br>• Multi-step modal progress workflow for testing visuals on Green<br>• 24/7 Visuals manager with instant search/filter, enable/disable toggle, reordering, and independent scroll<br>• Safe Playback Mode toggle (guards compositor to 2-buffer ping-pong engine)<br>• 7-layer canvas compositing (Stage Content z: 20-70 over Visual Content z: 10)<br>• Media scanning with ffprobe + runtime H.264 conversion<br>• Local TCP media server with registered route table<br>• Layer transform: x, y, width, height, scale, fit, opacity, visible, flipX, flipY<br>• Publish to GREEN staging: rsync media + layout.json + deploy via npx wrangler pages deploy<br>• App info with production-locked status |
| **Recent Fixes (Aug 16, 2026 - v0.1.32 Core Architecture Overhaul)** | • Replaced blocking CLI commands with async Rust tasks (`spawn_blocking`) and in-memory `sha2` hashing, totally resolving UI freeze / 'not responding' bug<br>• Unified Workstation and Green geometry engine with `#stageComposition` 16:9 container, eliminating coordinate distortion and percentage mismatches<br>• Removed hardcoded CSS positions from `stage.css` and `overlay.css` to allow canonical layout model to control all layer rectangles<br>• Automated 99-point geometry parity audit (`tests/test_geometry_parity.mjs`) verifying 0.00% delta across all viewports<br>• Full 48-point UI regression test suite (`tests/test_visuals_workstation_ui.mjs`) & 7 Rust unit tests passing<br>• Rebuilt and installed release `.deb` package to `~/.local/bin/allthings140radio-visuals` |
| **Health Check** | Launch app, verify media loads, check stage/visual selectors work, verify publish to GREEN succeeds<br>`cat /home/ebmarah/.local/share/allthings140radio-visuals/workstation.log` — operation log |
| **Current Status** | **ACTIVE WORKSTATION (v0.1.32)** — Installed in `~/.local/bin/allthings140radio-visuals`, desktop launcher verified, dock integration active, GREEN staging verified, live site locked |
| **Critical Safeguards** | Production `/visuals/` SHA-256 `4ca1a32e74c2b319fa8c7979b2e68e1486166a2d105c53158f2a417bf976ef32` must not change without authorization<br>GREEN staging must not be cut over without meeting all gates (multi-hour soak, physical phone, manual asset validation)<br>Never publish without verifying layout.json hash matches remote manifest |

---

### 5. Green Web Stage

| Field | Value |
|-------|-------|
| **Name** | ALLTHINGS140Radio Green Web Stage |
| **Path** | `/home/ebmarah/Projects/AllThings140Radio/visuals-green/` (source)<br>Deployed: `https://allthings140-visuals-green.pages.dev/` |
| **Version** | N/A (web/HTML5, based on visuals-app v0.1.30 logic) |
| **Tech Stack** | HTML5, CSS, JavaScript, Cloudflare Pages |
| **Primary Purpose** | Staging environment for visual shows: dual video buffer (stage + visual), audience presence, reactions, room energy, takeover schedule support, WYSIWYG preview. |
| **Key Files** | `index.html`, `stage.css`, `overlay.css`, `stage.js`, `layout.json`, `playlist.json`, `config.js`, `media/` (stage + visual MP4 files) |
| **Ports** | None (web); realtime at `visuals-realtime-staging.allthings140radio.online` (WS) |
| **Runtime Dependencies** | visuals-realtime-staging instance (aiohttp WS server)<br>Cloudflare Pages deployment<br>Tauri workstation media pipeline logic |
| **Key Features** | • Dual video buffer: Stage video + Visual Content video<br>• 7-layer z-index stacking (audience z: 50, reactions z: 60, energy z: 70)<br>• Presence bubbles + avatars + dance animation<br>• Reactions (fire/skull/heart/bolt/bass) → room energy update<br>• Room energy HUD with bar visualization<br>• Takeover schedule state (automatic start/end, normal playlist restoration)<br>• Chat history + messages<br>• Profile system (orb-purple, orb-cyan, orb-pink, orb-green, orb-fire)<br>• WYSIWYG layers for station logo and Now-Live metadata card<br>• Layer selection, duplication, deletion, bring forward/send backward<br>• Screen target positioning and mask<br>• Media role separation (stage vs visual explicit types)<br>• Normal/takeover test-state switching |
| **Recent Fixes (Aug 13-15, 2026)** | • Authoritative z-index stacking: HUD at z: 50-70 above video at z: 10-40<br>• CORS allowlist added on `/visuals-state` endpoint<br>• Multiple resume/online events treated as idempotency guard (green client)<br>• Client now treats OPEN and CONNECTING sockets as idempotency guard<br>• Systemd stop timeout bounded at 15 seconds<br>• kdump disabled on Oracle Linux 9.8 (was causing multi-minute boots)<br>• Tunnel `Requires=` changed to `Wants=` so gateway maintenance doesn't tear down tunnel<br>• Media role separation: explicit `mediaType` values (`stage` vs `visual`); derivatives inherit logical source role<br>• 57 visual entries with explicit mediaType values<br>• Production baseline hash preserved: `4ca1a32e74c2b319fa8c7979b2e68e1486166a2d105c53158f2a417bf976ef32` |
| **Current Status** | **ACTIVE STAGING** — URL: `https://allthings140-visuals-green.pages.dev/`<br>**Status:** FROZEN at production baseline — no cutover authorized<br>**Cutover gates still open:**<br>• Extended desktop soak and memory-growth observation incomplete<br>• Mobile browser regression/profile/reconnect testing incomplete<br>• Full manual takeover asset-package validation not done<br>• Physical-phone regression testing not done<br>• GREEN health check + remote manifest verification gate<br>• Takeover restart-before-start and scheduling scheduling need longer real-time staging test |
| **Production Baseline** | SHA-256: `4ca1a32e74c2b319fa8c7979b2e68e1486166a2d105c53158f2a417bf976ef32`<br>Never change production `/visuals/` without preserving this hash |

---

### 6. Visuals Realtime Server

| Field | Value |
|-------|-------|
| **Name** | ALLTHINGS140Radio Visuals Realtime Server |
| **Path** | `/home/ebmarah/Projects/AllThings140Radio/visuals-realtime/app.py` (source)<br>Running on Oracle VM 2 |
| **Version** | 0.1.0-staging |
| **Tech Stack** | Python 3, aiohttp, WebSockets, SQLite |
| **Primary Purpose** | Real-time room: presence, chat history, live reaction aggregation, energy calculation, takeover schedule state. |
| **Port** | 8765 (WebSocket), 14140 (alternative/configured) |
| **Key Files** | `app.py` (full aiohttp server with all routes)<br>Config: `config.example.env` (ENVIRONMENT=staging, REALTIME_HOST=127.0.0.1, REALTIME_PORT=14140, DATABASE_PATH=./realtime.db, etc.) |
| **Database** | SQLite (`realtime.db`) — tables: messages, schedules, stats |
| **Key Functions** | • WebSocket connection management (join, message, reaction, ping/pong)<br>• Chat message storage + broadcast with rate limiting + replay prevention (event_id dedup)<br>• Reaction aggregation → energy calculation (decay: energy -= dt * 1.4)<br>• Takeover schedule state (server-authoritative start/end, automatic normal playlist restoration)<br>• Health endpoint: `/health`<br>• Visual state endpoint: `/visuals-state` (with CORS allowlist)<br>• Schedule administration: `POST /admin/schedule` (Bearer token auth)<br>• Session rate limiting per IP + per client<br>• Bounded pruning of ip_events dictionary (stale entries > 120s removed)<br>• Safely snapshot client dictionaries in broadcast (iterate copy, not live dict) |
| **Recent Fixes (Aug 13-15, 2026)** | • Moved table/index creation to `Room.__init__()` (was on every request)<br>• Added session rate-limit cleanup in `ws_handler` finally block<br>• Dictionary pruning in `Room.allow()` (stale IP events removed)<br>• Safely iterate client dictionaries in `Room.broadcast()` (snapshot before iteration)<br>• Added allowlisted CORS on `/visuals-state`<br>• Multiple resume/online events treated as idempotency guard in green client<br>• Health URL derived from REALTIME_HOST/REALTIME_PORT env vars (not hardcoded)<br>• Extended soak/restart repetition remains a cutover gate |
| **Current Status** | **ACTIVE STAGING** — Running on Oracle VM 2, health OK, version 0.1.0-staging<br>Connections: 0 (no active WebSocket clients currently)<br>Health: `{"ok": true, "service": "allthings140-visuals-realtime", "version": "0.1.0-staging", "connections": 0}` |
| **Health Endpoint** | `GET https://visuals-realtime-staging.allthings140radio.online/health` — HTTP 200, JSON ok<br>`GET http://127.0.0.1:14140/health` — local equivalent |
| **Takeover Scheduler** | Server-authoritative: schedules have start_at, end_at, enabled fields; only one active at a time; automatic restoration to normal playlist when takeover ends |

---

### 7. Android Mobile App

| Field | Value |
|-------|-------|
| **Name** | AllThings140Radio Mobile App |
| **Path** | `/home/ebmarah/Projects/AllThings140Radio/android/mobile-app/` (source)<br>APK at various build outputs |
| **Version** | 1.1.0 (versionCode: 13) |
| **Tech Stack** | Android API 35, Java 11, AndroidX Media3 (ExoPlayer) |
| **Primary Purpose** | Native Android listener app with background playback foreground service and Android Auto / Automotive media library integration. |
| **Key Files** | `app/build.gradle`, `app/src/main/AndroidManifest.xml`, `java/com/allthings140/radio/` source files<br>Gradle signing config |
| **Ports** | Same continuous MP3 stream (consumed via ExoPlayer from `stream.ebeinc.online/live.mp3`) |
| **Runtime Dependencies** | ExoPlayer (Media3), Android SDK 35, Google Play services (optional) |
| **Recent Fixes (Aug 15, 2026)** | • Release signing configuration property-driven with debug fallback<br>• Debug certificate SHA-256: `53710e5f9cfff64a64baf9e8a156b917b2a11ab95ed88f7270a96c0996bb3271` (debug only; do not claim GP production signing readiness)<br>• Media3 MediaLibraryService with single listener-safe LIVE RADIO item for Android Auto/Automotive |
| **Current Status** | **ACTIVE ARTIFACT** — v1.1.0, debug-signed APK, release build config with env/property-driven signing<br>**Known issues:**<br>• Debug keystore used for release builds (cannot publish to Google Play without proper signing)<br>• Release signing vars: KEYSTORE_FILE, KEYSTORE_PASSWORD, KEY_ALIAS, KEY_PASSWORD — not yet provided<br>• Android Auto integration functional but explicitly pending physical/DHU/Automotive target validation |
| **Confidence** | 70% — Only debug APK observed; release signing and Play Store status not verified |

---

### 8. Discord Bot

| Field | Value |
|-------|-------|
| **Name** | ALLTHINGS140Radio Discord Bot |
| **Path** | `/home/ebmarah/Projects/AllThings140Radio/discord-bot/` (source) |
| **Version** | N/A (standalone bot) |
| **Tech Stack** | Node.js (>=20), discord.js v14 |
| **Primary Purpose** | Discord community bot: `/nowplaying`, `/radio`, `/invite`, `/announce` commands; welcome messages; status posting. |
| **Key Files** | `index.js`, `.env` (contains bot token — **plaintext, should be rotated**) |
| **Ports** | None (standalone Node process) |
| **Runtime Dependencies** | Discord API, Node.js >=20, dotenv |
| **Key Commands** | `/nowplaying` — reports current track<br>`/radio` — radio status<br>`/invite` — bot invite link<br>`/announce` — send announcement to Discord |
| **Recent Fixes (Aug 15, 2026)** | • Status field mapping corrected: `data.current_title`, `data.current_artist`, `data.active_takeover`<br>• Previously looked for `data.track.title` (bug)<br>• Host metadata parsing updated |
| **Known Issues** | • **Plaintext bot token** in `.env` — must be regenerated in Discord Developer Portal if ever shared or exposed<br>• `.gitignore` properly ignores `.env`, but token rotation recommended |
| **Current Status** | **STANDALONE BOT** — Source present; token handling improved but not yet rotated<br>**Confidence:** 85% — Source fully read; token rotation is a developer operation |
| **Critical Safeguards** | Never commit `.env` to git (already ignored)<br>Regenerate token in Discord Developer Portal if ever exposed<br>Do not share bot token in public channels |

---

### 9. AI Host Generator

| Field | Value |
|-------|-------|
| **Name** | AI Host (TTS + LLM radio breaks) |
| **Path** | `/home/ebmarah/Projects/AllThings140Radio/tools/ai_host.py` (source) |
| **Version** | N/A (integrated extension, no standalone version) |
| **Tech Stack** | Python 3, Ollama LLM (llama3.2:3b at 127.0.0.1:11434), Piper TTS |
| **Primary Purpose** | Synthesizes conversational voice interstitials (station IDs, promos, takeover announcements, listener roasts, fake infomercials) between songs. |
| **Key Functions** | • `AIConfig` — enabled flag, humor level, voice mode, Ollama URL/model, weights, break intervals<br>• `AnnouncementScheduler` — song-count gate: 4–7 songs between AI breaks (never controls playback)<br>• `VoiceLibrary.discover()` — reads voice profiles from directory<br>• `PersonaLibrary.discover()` — reads persona system prompts<br>• `Takeover_context()` — extracts upcoming takeover metadata for context<br>• `AIHost.generate()` — requests text from Ollama, validates with `safe_comedy()`, stores in history<br>• `AIHost.synthesize()` — sends text to Piper TTS, outputs WAV, prunes cache<br>• `AIHost.prune_cache()` — automated cleanup of disposable speech WAV files (>50 files, older than 7 days)<br>• `AIReadyQueue` — invalidates event-bound announcements when facts change<br>• `safe_comedy()` — blocks prohibited terms (suicide, bomb, slurs, etc.) |
| **Voice Modes** | SINGLE_HOST, RANDOM_HOST, WEIGHTED_HOST, EVENT_SPECIFIC_HOST |
| **Announcement Types** | STATION_ID, SHARE_THE_STATION, WEBSITE_PROMO, LISTENER_ROAST, FAKE_INFOMERCIAL, ARTIST_TAKEOVER_PROMO, ARTIST_TAKEOVER_TODAY, ARTIST_TAKEOVER_STARTING, ARTIST_TAKEOVER_ACTIVE, ARTIST_TAKEOVER_ENDING, ARTIST_SHOUTOUT, TRACK_SUBMISSION_PROMO, SPECIAL_EVENT, RANDOM_HOST_BIT |
| **Humor Levels** | CLEAN, NORMAL, EDGY, UNHINGED |
| **Recent Fixes (Aug 15, 2026)** | • `prune_cache()` — automated cleanup of disposable TTS WAV files (max 50, max age 7 days)<br>• `context_signature()` — hash-based invalidation when context facts change<br>• `next_ready()` — pop from queue by signature<br>• `generate()` — timeout 45s, fail-open (return None → music continues normally)<br>• TTS failures return None; playback always continues (fail-open design) |
| **Current Status** | **INTEGRATED EXTENSION** — Part of server.py ecosystem; not a standalone service<br>**Health:** Fails open safely; if Ollama or Piper unavailable, returns None; music playback continues normally<br>**Known issues:**<br>• Unbounded disk accumulation of generated WAVs (fixed with prune_cache())<br>• Ollama model `llama3.2:3b` must be running for TTS to work<br>• Piper TTS model must be available at configured path |
| **Confidence** | 80% — Source fully read; runtime not directly observed but design is fail-open |

---

### 10. Hot Cache Manager

| Field | Value |
|-------|-------|
| **Name** | Hot Cache Manager |
| **Path** | `/home/ebmarah/Projects/AllThings140Radio/tools/cache_manager.py` (source) |
| **Version** | N/A (service, no version string) |
| **Tech Stack** | Python 3, sqlite3, hashlib, ffprobe (subprocess), rclone (conceptual, not invoked from this script) |
| **Primary Purpose** | Predictive rolling pre-fetcher: downloads upcoming rotation tracks from Google Drive to local NVMe storage before AutoDJ needs them. |
| **Key Configuration** | `HOT_CACHE_TARGET_MINUTES` (default 120), `HOT_CACHE_MIN_MINUTES` (default 45), `HOT_CACHE_MAX_GB` (default 5), `HOT_CACHE_MIN_FREE_PERCENT` (default 12%), `HOT_CACHE_MAX_TRACKS` (default 50) |
| **Key Files** | `cache-state.json`, `cache-index.json`, `READY/` subdirectory (pre-fetched tracks), `TEMP/` subdirectory (partial downloads) |
| **Key Functions** | • `tracks()` — reads approved tracks from station.db<br>• `planned()` — applies rotation state, returns tracks targeting ~120 min<br>• `cache_name()` — generates filename from track ID + hash + extension<br>• `stage()` — copies/links from Drive emergency mirror or READY into `READY/`<br>• `evict()` — removes least-used tracks when over size limit (5 GB) or free percent < 12%<br>• `run_once()` — execute one cycle; returns summary payload<br>• `main()` — CLI: once/status/run commands |
| **Recent Fixes (Aug 15, 2026)** | • All valid files in `READY` now indexed in `cache-index.json` (previously dropped if outside 50-track window)<br>• `evict()` protects tracks just staged in current cycle<br>• Emergency track count reported in summary payload<br>• Drive connection status reported (connected/offline)<br>• Summary includes `minutes_ready`, `target_minutes`, `min_minutes` |
| **Current Status** | **ACTIVE SERVICE** — Runs on Oracle VM 1 via systemd timer or cron; 30-minute cycle<br>**Health:** `tools/cache_manager.py status` — JSON summary payload<br>**Summary example:** `{"status": "healthy", "tracks_ready": 48, "minutes_ready": 118.5, "target_minutes": 120, "cache_bytes": 3.2G, "max_bytes": 5G, "emergency_tracks": 575, "drive": "connected"}` |
| **Confidence** | 90% — Source fully read; service active on VM1; summary payload structure verified |

---

### 11. Catalog Integrity System

| Field | Value |
|-------|-------|
| **Name** | Catalog Integrity System |
| **Path** | `/home/ebmarah/Projects/AllThings140Radio/tools/catalog_integrity.py`, `/home/ebmarah/Projects/AllThings140Radio/tools/recover_playback_assets.py` |
| **Version** | N/A (tools, no version strings) |
| **Tech Stack** | Python 3, sqlite3, hashlib, json, pathlib |
| **Primary Purpose** | Verifies SHA-256 hashes, reconciles database rows with physical Drive/mirror files, performs non-destructive quarantine and restore. |
| **Key Files** | `catalog_integrity.py` — scan, verify, report<br>`recover_playback_assets.py` — restore from Drive into emergency mirror, verify by SHA-256 and duration |
| **Recent Fixes (Aug 15, 2026)** | • Full deployment after 88-track incident (Aug 15)<br>• All 88 affected approved tracks restored from Drive into emergency mirror<br>• Verified by SHA-256 and duration<br>• 569 eligible tracks now playback-ready<br>• 2 remaining rows intentionally unapproved/rights-blocked<br>• Read-only integrity monitor drives HEALTHY/DEGRADED/CRITICAL catalog state<br>• 30-minute playback-admission timer prevents future Drive-only uploads from becoming stranded |
| **Current Status** | **ACTIVE SERVICE** — Proven during August 15 incident; all catalog state now HEALTHY |
| **Catalog State** | HEALTHY — 569 eligible tracks playable; 2 intentionally unapproved/rights-blocked |
| **Confidence** | 95% — Proven incident recovery; fully documented in audit report |

---

## Summary Table: All Applications

| # | Application | Version | Status | Tech Stack | Critical Safeguard |
|---|-------------|---------|--------|------------|-------------------|
| 1 | Station Broadcast Server | 0.8.0 | ACTIVE PRODUCTION | Python, FFmpeg, Icecast, SQLite | Backup before deploy; verify health; never ignore catalog integrity |
| 2 | Desktop DJ Workstation | 0.7.0 | ACTIVE TOOL | Python, Tkinter | Backup station.db; HEALTHY catalog before changes |
| 3 | Web Listener Frontend | 1.6.1 | ACTIVE PRODUCTION | HTML5, JS, Service Worker v54 | SW excludes .mp3/.m3u8; background resume logic |
| 4 | Visuals Desktop App | 0.1.30 | ACTIVE DEV/WORKSTATION | Tauri v2, Rust, Vite/React | Production SHA-256 locked; GREEN cutover gates |
| 5 | Green Web Stage | N/A | ACTIVE STAGING (frozen) | HTML5, CSS, JS, Cloudflare Pages | Production hash locked; cutover gates open |
| 6 | Visuals Realtime Server | 0.1.0-staging | ACTIVE STAGING | Python, aiohttp, WS, SQLite | CORS allowlist; admin token; rate limiting |
| 7 | Android Mobile App | 1.1.0 | ACTIVE ARTIFACT | Android API 35, Java, Media3/ExoPlayer | Release signing required for GP |
| 8 | Discord Bot | N/A | STANDALONE BOT | Node.js, discord.js v14 | Rotate token if exposed; .env not git-tracked |
| 9 | AI Host Generator | N/A | INTEGRATED EXTENSION | Python, Ollama, Piper TTS | Fail-open; TTS failure → music continues |
| 10 | Hot Cache Manager | N/A | ACTIVE SERVICE | Python, SQLite, ffprobe | Evict LRU when over 5 GB or <12% free |
| 11 | Catalog Integrity System | N/A | ACTIVE SERVICE | Python, SQLite, SHA-256 | Read-only monitor; 30-min admission timer |

---

## Application Communication Map

### Which Apps Talk to Which

| From → To | Protocol/Endpoint | Direction | Purpose |
|-----------|-------------------|-----------|---------|
| **Listener → status.ebeinc.online** | HTTP GET | Client → Public API | Station status, stream health |
| **Listener → stream.ebeinc.online** | HTTP GET | Client → Stream | Continuous MP3 audio |
| **Website → _worker.js** | HTTP | Browser → Cloudflare Edge | Proxy routing, takeover alert auth, OBS gateway |
| **DJ app → 127.0.0.1:14080** | HTTP | Admin → Private API | Catalog control, rotation, ads, takeovers, support |
| **DJ app → station.db** | SQLite | Admin → Local DB | Read/write approvals, rotation, metadata |
| **Server.py → Google Drive** | rclone | Backend → Master library | Music library source of truth |
| **Server.py → Icecast 2** | SHOUTcast | Encoder → Audio output | Loopback-only port 14000 |
| **Server.py → loopback relay 14001** | Icecast auth | Encoder → Real credentials | Injects source passwords into HTTP Basic auth headers |
| **Cache manager → Google Drive** | rclone | Background → Pre-fetch | Predictive hot cache (50 tracks, 120 min target) |
| **Realtime server → SQLite** | SQL | Server → Persistence | Messages, schedules, stats, energy |
| **Realtime server → WebClients** | WS | Server → Browser | Presence, chat, reactions, energy, takeover schedules |
| **Visuals workstation → media server** | TCP localhost | Local → Media files | Stage + Visual video playback |
| **Visuals workstation → realtime server** | WS | Local → Room state | Presence, schedules, energy for canvas |
| **Visuals workstation → Cloudflare Pages** | HTTPS | Local → GREEN staging | Publish layout + media via rsync + wrangler |
| **AI host → Ollama** | HTTP | Local → LLM | Text generation for radio breaks |
| **AI host → Piper** | Subprocess | Local → TTS | WAV synthesis for radio breaks |
| **Discord bot → Discord API** | WS | Bot → Community | Commands, status, announcements |
| **Support system → Stripe** | HTTPS | Backend → Payments | Checkout, webhook verification, idempotent recording |
| **Support system → Mailchimp** | HTTPS | Backend → Newsletter | Signup, welcome tags, subscriber management |
| **Tailscale → all services** | Mesh | Infrastructure | Private API access (14080), inter-VM SSH, MagicDNS |

### Data Flow Summary

```
Listeners                       Cloudflare Edge
       |                              |
       v                              v
status.ebeinc.online         _worker.js (auth, proxy, routing)
       |                              |
       +---- stream.ebeinc.online ---+--- Icecast (port 14000) ---- Oracle VM 1 ---- Google Drive (master)
       |                              |          AutoDJ (server.py)        |
       |                              |                          |----------> Cache (READY, 50 tracks)
       |                              +---------- Tunnel (cloudflared) 
       |
   Web frontend (radio/)        Support (Stripe/Mailchimp)
       |                              |
       v                              v
Service Worker v54            support_system.py
```

---

## Application Status Summary

| Category | Count | ACTIVE | STAGING | DEV/ARTIFACT | INACTIVE/UNKNOWN |
|----------|-------|--------|---------|--------------|------------------|
| Broadcast & Radio | 3 | 2 | 0 | 1 | 0 |
| Visuals & Stage | 4 | 0 | 3 | 1 | 0 |
| Website & API | 3 | 2 | 0 | 1 | 0 |
| Mobile & Chat | 3 | 0 | 0 | 2 | 1 |
| Tooling & Infrastructure | 3 | 2 | 0 | 0 | 1 |
| **Total** | **16** | **6** | **3** | **5** | **2** |

**Production:** Station Broadcast Server (0.8.0), Web Listener Frontend (1.6.1) — both 100% online, 24/7
**Staging:** Green Web Stage (frozen), Visuals Realtime Server (0.1.0-staging), Visuals Desktop App — all staged but production locked
**Development/Artifact:** Visuals Desktop App (0.1.30, active workstation), Android App (1.1.0, debug APK), Discord Bot
**Unknown/Needs Verification:** Google Drive mount status from this workstation, Cloudflare secret provisioning, Oracle VM runtime resources