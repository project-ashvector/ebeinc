# ALLTHINGS140 Ecosystem — Application Responsibility & Ownership Map

**Author:** Antigravity (Google Deepmind)  
**Date:** 2026-08-17  
**Scope:** Whole-ecosystem audit of workstations, VMs, Cloudflare projects, databases, and services  

---

## 1. Single Authoritative Ownership Matrix

| System Component | Authoritative Owner | Location / Runtime | Primary Responsibilities | Data Stores & Config Owned | What It Must NOT Do |
|---|---|---|---|---|---|
| **ALLTHINGS140 Hub** | **Hub Operations Center** (`hub/`) | Zorin OS Workstation (`allthings140-hub`) | Central control plane: Health & telemetry, App inventory, Git tracking, AI agent launcher, Prompt library, Engineering handoffs, Report reader, Backups overview, VM monitoring, Website CMS (Sponsors, Partners, Takeovers, Announcements, Roadmap, Media Library), Cloudflare Deployments | `~/.config/allthings140-hub/`, `radio/data/site-content.json`, `radio/assets/` | Must NOT run the 24/7 radio process. Must NOT act as the live audio stream encoder. Must NOT duplicate 7-layer canvas compositing. |
| **Desktop DJ Workstation** | **Desktop DJ App** (`tools/dj_app.py`) | Zorin OS Workstation (`/opt/allthings140radio-dj`) | Music track catalog review, AutoDJ rotation weights, playlist inspection, emergency track insertion, local takeover audio triggers, broadcast diagnostics | Local station SQLite mirror, DJ session logs | Must NOT manage public website sponsors/partners/roadmap. Must NOT deploy Cloudflare Pages. |
| **Visuals Show-Control** | **Visuals Workstation** (`visuals-app/`) | Zorin OS Workstation (`allthings140radio-visuals`) | 7-layer canvas compositing, 16:9 canonical geometry engine, stage overlays, visual video loop selection, Green staging synchronization | `visuals-app/src/`, `visuals-green/`, canonical `layout.json` | Must NOT manage radio audio rotation or server-side Icecast. Must NOT host public website CMS. |
| **Station Broadcast Authority** | **Server Engine** (`tools/server.py`) | Oracle Cloud VM 1 (`allthings140radio-server`) | 24/7 continuous broadcast engine, AutoDJ sequence generator, Icecast 2 stream encoder (`stream.ebeinc.online`), loopback API (:14080) | `/var/lib/allthings140radio/station.db`, `/srv/allthings140radio/data/music/` (575 files) | Must NOT rely on desktop Hub or DJ GUI being open. Must run headless under systemd. |
| **Predictive Hot Cache** | **Hot Cache Daemon** (`tools/hot_cache.py`) | Oracle Cloud VM 1 (`allthings140radio-cache.service`) | Pre-fetches next 50 rotation tracks (120m buffer) into memory/fast NVMe | `/var/lib/allthings140radio/hot-cache-state.json`, `/srv/allthings140radio/cache` | Must NOT alter track approval states or database schema. |
| **Catalog Integrity System** | **Integrity Scanner** (`tools/catalog_integrity.py`) | Oracle Cloud VM 1 | Daily SHA-256 verification, duration parsing, and 30-minute admission gate enforcement | `/var/lib/allthings140radio/catalog-integrity.json` | Must NOT delete master audio files without admin confirmation. |
| **Visuals Realtime Server** | **Realtime App** (`visuals-realtime/app.py`) | Oracle Cloud VM 2 (`allthings140-visuals-realtime.service`) | WebSocket hub (:14140), room presence, audio energy dispatch, realtime takeover synchronization | VM 2 socket state, realtime room cache | Must NOT manage audio playback or broadcast authority. |
| **Web Listener Frontend** | **PWA Website** (`radio/`) | Cloudflare Pages (`allthings140radio.online`) | Public web player, synchronized HLS background video, live chat iframe, sponsor/partner showcase, takeover archive, support links | `radio/` static assets, Service Worker (`sw.js`) | Must NOT store station master audio or private secrets. |
| **Android Listener App** | **Mobile App** (`android/mobile-app/`) | Android Devices (APK/AAB) | Native mobile playback, Media3 ExoPlayer background foreground service, lockscreen media controls | Local Android app sandbox | Must NOT run server administrative functions. |
| **Community Discord Bot** | **Discord Bot** (`discord-bot/`) | Workstation / VM Node.js daemon | `/nowplaying`, `/radio`, `/invite`, automated live takeover announcements in Discord channels | `discord-bot/config.json`, `.env` (gitignored) | Must NOT touch station SQLite database directly. |
| **Cloudflare Edge Workers** | **Edge Workers** (`_worker.js`, `chat-worker/`) | Cloudflare Edge Network | Edge caching for `/api/public/status`, proxy to Oracle VM 1, admin alert authentication | Cloudflare KV / D1 / Worker Secrets | Must NOT hardcode static secrets in source control. |

---

## 2. Duplicate Functionality & Conflict Resolution

### 1. Website / Site Control Disconnect (Resolved)
- **Problem:** Previously considered creating a standalone "Site Control" application, which would fragment management and duplicate Hub logic.
- **Resolution:** Integrated the **Website / Site Control Plane** directly into the ALLTHINGS140 Hub (`hub/ui/views/site_*.py` and `hub/services/site_content_service.py`), keeping all operational controls in one unified interface without creating new apps.

### 2. Takeover Schedule Authority (Resolved)
- **Problem:** Potential desynchronization between live broadcast takeover triggers (owned by `server.py`/`dj_app.py`) and public website promotional banners.
- **Resolution:** `server.py` and the station database remain the single authoritative source of **live broadcast state** (`active_takeover`, `live_host`). The Hub's Site Control manages **public website promotional metadata and historical archive** (`bio`, `links`, `replay_url`, `flyer_image`), syncing via `site-content.json` which the web frontend consumes seamlessly.

### 3. Version Drift (Resolved)
- **Problem:** Hardcoded version numbers (e.g. `0.1.32` vs `0.1.37` in Visuals, `0.7.0` vs `0.7.1` in DJ App).
- **Resolution:** Replaced all static version string constants in the Hub with live file-based discovery (`package.json`, `tauri.conf.json`, AST parsing).

### 4. Zero-Code-Deploy Site Content Updates (Resolved)
- **Problem:** Updating a sponsor logo or adding a past takeover previously required modifying `index.html` and running a full Cloudflare deployment.
- **Resolution:** Built a structured JSON content engine (`radio/data/site-content.json`) with asset management in `radio/assets/`. The website dynamically renders sponsors, partners, takeovers, and announcements from this clean data model, enabling instant content updates without code refactoring.
