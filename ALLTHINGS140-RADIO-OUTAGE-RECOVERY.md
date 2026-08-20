# ALLTHINGS140 RADIO — OUTAGE RECOVERY REPORT

**Incident:** Station Outage / Player Stuck in "CONNECTING" / "Awaiting station uplink"  
**Time Detected:** 2026-08-18T09:48:00Z  
**Recovery Completed:** 2026-08-18T09:53:14Z  
**Status:** **100% RESTORED & BROADCASTING NORMALLY**  

---

### SYSTEM HEALTH & COMPONENT MATRIX

| Component | Layer | Result | Notes |
| :--- | :--- | :--- | :--- |
| **LOCAL VM1 SERVER** | AutoDJ / Engine | **PASS** | AutoDJ catalog rotation active (624 tracks ready) |
| **LOCAL ICECAST** | Audio Server (Port 14000) | **PASS** | Local `/live.mp3` generating continuous 128 kbps audio |
| **PUBLIC STATUS** | Origin (`status.ebeinc.online`) | **PASS** | `GET /api/public/status` returning HTTP 200 with active track JSON |
| **PUBLIC STREAM** | Stream (`stream.ebeinc.online`) | **PASS** | `https://stream.ebeinc.online/live.mp3` delivering continuous audio bytes |
| **CLOUDFLARE TUNNEL** | `allthings140radio-tunnel` | **PASS** | Cloudflared ingress routing to 14000 (Icecast) and 14082 (Status) |
| **RADIO `_worker.js`** | Edge Proxy | **PASS** | Properly proxies `/api/public/status` to `PUBLIC_API_ORIGIN` |
| **SERVICE WORKER** | Client Cache (`sw-v47.js`) | **PASS** | Correctly excludes `.mp3`, `.m3u8`, `/api/` from CacheStorage |

---

### INCIDENT FORENSICS

- **USER SYMPTOM:**
  Listeners visiting `https://allthings140radio.online/` saw the player stuck at "SYSTEM STATUS: CONNECTING", "Awaiting station uplink", and no audio was playing.

- **ROOT CAUSE:**
  The in-process public HTTP status gateway thread on VM1 (`server.py` port `14082`) became unresponsive under connection load, causing Cloudflare Tunnel (`cloudflared`) to log `i/o timeout` on `http://127.0.0.1:14082` when resolving `status.ebeinc.online`. Because the web client (`radio/app.js`) requires a successful `/api/public/status` response before attaching and unmuting the stream URL, listeners remained in the "CONNECTING" state.

- **EXACT CHANGE THAT CAUSED OUTAGE:**
  During the canary rollout, burst polling of `/api/public/status` from test scripts and active client sessions queued up in the single-process `PublicGatewayHandler` on VM1 port 14082, causing the status gateway thread to exhaust its connection backlog.

- **RECOVERY ACTION:**
  1. Connected to VM1 (`allthings140radio-server`) via Oracle SSH key.
  2. Verified local Icecast audio stream on port 14000 was generating valid 128kbps MP3 audio frames.
  3. Cleanly restarted `allthings140radio-server.service` on VM1.
  4. Verified port 14080 (health) and port 14082 (status gateway) immediately returned HTTP 200.
  5. Verified `https://status.ebeinc.online/api/public/status` and `https://allthings140radio.online/api/public/status` returned valid track JSON.
  6. Verified `https://stream.ebeinc.online/live.mp3` stream delivery via `ffprobe` (128 kbps).
  7. Confirmed in live browser that `#heroPlay` connects, audio plays, progress advances, and track metadata updates seamlessly.

- **SERVICES RESTARTED:**
  - `allthings140radio-server.service` (VM1)

- **CLOUDFLARE DEPLOYMENT ROLLED BACK:**
  - **NO** (Cloudflare Edge Worker and KV routing `{"chat":"legacy","visuals":"legacy"}` verified healthy and functional).

- **PUBLIC MUSIC RESTORED:**
  - **YES**

- **CURRENT TRACK:**
  - `BENZMIXER!!! — R28D (FAT4L EDIT)` (Next: `TECHNO TEAROUT_`)

- **15-MINUTE SOAK:**
  - **PASS** (Continuous MP3 stream streaming, natural track transitions observed, zero stream drops, 3–4 active listeners connected).

---

### VISUAL ROUTING INTEGRITY

- **Public Chat Visuals:** `legacy` (`#backgroundVideo` active, `#chatVisualRenderer` disabled)
- **Public Visuals Tab:** `legacy` (`/visuals/` untouched)
- **Production Activation:** **LOCKED**
