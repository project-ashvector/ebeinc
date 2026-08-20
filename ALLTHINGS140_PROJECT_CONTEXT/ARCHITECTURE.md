# ALLTHINGS140 RADIO — Architecture

## High-Level Service Map

```text
Listeners (web + mobile)
   |
   +-- Cloudflare Edge CDN
   |   |
   |   +-- status.ebeinc.online       (public status API, HTTP 200)
   |   +-- stream.ebeinc.online/live.mp3 (Icecast audio, HTTP 200/206)
   |   +-- visuals-realtime-staging.allthings140radio.online/health
   |   +-- visuals-media-staging.allthings140radio.online (byte-range video)
   |   +-- allthings140-radio.online   (public website, HTML5/PWA)
   |   +-- _worker.js                  (Edge Worker: auth, proxy, routing)
   |
   +-- Cloudflare Tunnel (cloudflared)
       |
       +-- Loopback Icecast → public edge mount
           +-- Port 14000 loopback only
           +-- Port 14082 public gateway (loopback)
           +-- Port 14083 Traktor guest (restricted, loopback)
           +-- Port 14001 auth relay (loopback, icecast://source:local-relay@127.0.0.1:14001/live.mp3)
           |
           +-- Tailscale MagicDNS: allthings140radio-server
               +-- Port 14080 private control API (loopback + Tailscale forwarded)
               +-- Port 14001 Icecast auth relay
               +-- Port 14083 Traktor guest ingest
```

## Operational Planes

### Plane 1: Public Listener & Community
- **Entry points:** `allthings140radio.online`, `status.ebeinc.online`, `stream.ebeinc.online`
- **Delivery:** Cloudflare CDN + Tunnel → loopback Icecast → listeners
- **Interaction:** Chat (Durable Objects), reactions, presence, newsletter (Mailchimp/Resend)
- **Takeovers:** Schedule API → subscriber alerts (auth-protected) → email via Mailchimp/Resend
- **Support:** Stripe Checkout → webhook → SQLite recording → public goal/feed

### Plane 2: 24/7 Broadcast Authority (Oracle VM 1)
- **Host:** `allthings140radio-server` (64.181.235.228 / Tailscale 100.124.12.41)
- **Core:** `tools/server.py` (Python, SQLite, FFmpeg, Icecast)
- **AutoDJ:** Timeline scheduler → FFmpeg decoder → mix_ad() ducking → persistent FFmpeg encoder
- **Icecast 2:** Loopback-only on port 14000; auth via loopback relay (port 14001)
- **Storage:** Google Drive (`at140drive:`) via rclone → `/mnt/allthings140radio-drive` (master)
- **Local cache:** `/srv/allthings140radio/cache/READY/` (predictive hot cache, ~50 tracks)
- **Emergency mirror:** `/srv/allthings140radio/data/music/` (575 verified files, offline fallback)
- **Database:** `/var/lib/allthings140radio/station.db` (SQLite — approvals, hashes, metadata, schedules)
- **Configuration:** `/etc/allthings140radio/config.json` (mode 0600, root-owned)
- **Supervisor:** stateful with exponential backoff after 3 failures
- **Timers:** fallback-sync (every 15 min), cache admission (30-min), drive sync

### Plane 3: Visuals & Realtime Server (Oracle VM 2)
- **Host:** `allthings140-visuals-realtime` (163.192.1.208 / Tailscale 100.108.145.128)
- **Realtime API:** `aiohttp` server (port 8765 / 14140), WebSocket-based
- **Endpoints:** `/health`, `/visuals-state`, `/admin/schedule` (Bearer auth), `/ws`
- **Data:** SQLite (`realtime.db`) — messages, schedules, stats (total_reactions)
- **Presence:** WebSocket clients → room state (energy, participant count, profiles)
- **Reactions:** fire(8), skull(7), heart(6), bolt(9), bass(10) → energy update + broadcast
- **Chat:** message type → SQLite + broadcast; rate-limited per client + per IP
- **Takeover scheduler:** server-authoritative start/end times; automatic start/end and normal playlist restoration
- **Static media:** `static_media_server.py` (port 20242), byte-range video streaming (RFC 7233)
- **Health:** `{"ok": true, "service": "allthings140-visuals-realtime", "version": "0.1.0-staging", "connections": N}`
- **Tunnel:** cloudflared → Cloudflare edge; public health at `visuals-realtime-staging.allthings140radio.online/health`

### Plane 4: Management & Workstation
- **Desktop DJ:** `tools/dj_app.py` (Tkinter, private API port 14080, loopback only, Tailscale forwarded)
- **Visuals workstation:** Tauri app (v0.1.30, port 14340 dev mode), canvas compositor, layer management
- **Green staging:** `visuals-web/` → Cloudflare Pages `allthings140-visuals-green.pages.dev`
- **Discord bot:** `/nowplaying`, `/radio`, `/invite`, `/announce` (Node.js, plaintext token in .env)
- **AI host:** `tools/ai_host.py` (Ollama LLM + Piper TTS, scheduled breaks 4–7 songs)
- **Android app:** Media3 ExoPlayer, Android Auto, debug-signed APK
- **Hot cache manager:** `tools/cache_manager.py` (predictive pre-fetch, 50-track target, 120 min target)

## Stage/Visual Compositing Architecture

**Authoritative model:** Stage Content in FRONT, Visual Content UNDER the Stage

The Stage acts like a physical frame with the central screen area transparent, allowing Visual Content underneath to show through.

### Layer Stacking (z-index authoritative, from back to front):

| Layer | z-index | Identifier | Content Type |
|-------|---------|------------|-------------|
| 01 | 10 | `.screens` | Visual Content — MP4 video (backmost) |
| 02 | 20 | `.stage-overlay` | Stage Frame |
| 03 | 30 | `.mode-logo` | Station / Takeover Logo |
| 04 | 40 | `.now` | Now Playing / Live Alert |
| 05 | 50 | `.audience` | Presence Bubbles / Audience avatars |
| 06 | 60 | `.reactions` | Reactions (fire/skull/heart/bolt/bass) |
| 07 | 70 | `.energy` | Room Energy HUD (frontmost) |

### Historical Bug (Fixed v0.1.21)

Previously, `.screens` (z: 10) visually appeared **over** `.stage-overlay` (z: 20) despite the inspector showing Stage as the top layer. Root cause: video render order conflict. Fix: authoritative z-index reconstruction in stage.css/overlay.css, clamped dynamic layout z-indices (`visualZ <= 40`, `stageZ <= 30`), `.stage-overlay` with `object-fit: cover`.

### Tauri Workstation Media Pipeline

1. User selects media folder (Stage: `/home/ebmarah/Videos/at140radio/desktop visuals/stage/`, Visuals: `/home/ebmarah/Videos/at140radio/desktop visuals/visuals/`)
2. `scan_layer_media()` discovers video files, runs ffprobe for codec/duration/width/height
3. `probe_media_cached()` caches probe results in `media-index.json`; runtime conversions cached in `media-cache/by-source/`
4. `start_media_server()` starts local TCP media server (127.0.0.1:random-port) with registered route table
5. Media routes keyed by **source file fingerprint** (not layer ID), guaranteeing duplicated layers remain isolated
6. Converted runtimes generated via ffmpeg: HEVC/MOV → H.264 `libx264` + `yuv420p` + `faststart`
7. Route table maps `routeId` (source fingerprint) → `runtimePath` (converted file)
8. Layer visual uses `<video class="layer">` with direct `<video>` geometry path — same model for Stage and Visual Content
9. Publish to GREEN: rsync media + layout.json + layout.hash → Cloudflare Pages `allthings140-visuals-green.pages.dev`

## Website API Map

| Path | Method | Auth | Purpose |
|------|--------|------|---------|
| `/api/public/status` | GET | none | Station status (online, current_title, current_artist, listeners, generation_id, sequence, stream_status, stream_url, updated_at) |
| `/api/public/takeover-alert` | POST | Bearer token | Queue subscriber alert for approved takeover (auth check: token must match ADMIN_ALERT_KEY/TAKEOVER_ALERT_KEY/ADMIN_TOKEN) |
| `/api/public/schedule` | GET | none | Takeover schedule including current/upcoming takeovers |
| `/api/public/support/webhook` | POST | none | Stripe webhook: checkout.session.completed / async_payment_succeeded |
| `/api/public/support/status` | GET | none | Mailchimp connectivity (configured + connected) |
| `/api/public/newsletter` | POST | none | Mailchimp newsletter signup (pending status, tags: Takeover Reminders) |
| `/api/public/newsletter/status` | GET | none | Mailchimp ping + connectivity status |
| `/api/public/takeover-invite/[hash]` | GET | none | Private takeover request form (14-day expiry) |
| `/api/public/obs/live.mp3` | GET/HEAD | OBS_STREAM_TOKEN | Private OBS audio gateway (token validation) |
| `/api/public/archive/[/audio/waveform]` | GET | none | R2 recording delivery |
| `/api/public/newsletter/webhook` | POST | none | Mailchimp webhook: verify subscribe action + welcome tag |

---

## Data Flow Maps

### Radio Playback Path

```
Google Drive (master)
       |
       v
rclone on Oracle VM 1
       |
       v
 /mnt/allthings140radio-drive  (mounted on Oracle VM 1)
       |
       v
station.db (SQLite) — approval, hash, metadata
       |
       v
cache_manager.py — predictive pre-fetch to /srv/allthings140radio/cache/READY/
       |
       v
rotation-state.json — current position in rotation order
       |
       v
tools/server.py AutoDJ:
  - Advance rotation position
  - FFmpeg decode selected track → PCM stereo
  - mix_ad() — ad ducking (4-byte PCM boundary alignment)
  - Persistent FFmpeg encoder → loopback Icecast (port 14000)
       |
       v
Icecast 2 — serves /live.mp3 loopback only
       |
       v
Cloudflare Tunnel (cloudflared)
       |
       v
stream.ebeinc.online/live.mp3 — public listeners
       |
       v
status.ebeinc.online/api/public/status — monitoring API
```

### Visual Data Flow

```
User selects folder
       |
       v
scan_layer_media() → ffprobe → probe_media_cached() → route table
       |
       v
Converted runtime (H.264 .mp4) in media-cache/by-source/
       |
       v
Tauri workstation local TCP media server (127.0.0.1:port)
       |
       v
<video class="layer content|stage"> with transform geometry
       |
       v
CSP + assetProtocol scopes — asset: http/https/asset: urls
       |
       v
Render: Stage Content z: 20-70 OVER Visual Content z: 10
       |
       v
Cloudflare Pages deployment (green staging)
       |
       v
layout.json + layout.hash — verified on deploy (SHA-256 mismatch = deploy abort)
```

### Takeover Alert Flow

```
DJ app or admin triggers takeover alert
       |
       v
POST /api/public/takeover-alert (Cloudflare edge)
       |
       v
Auth check: Bearer token must match ADMIN_ALERT_KEY / TAKEOVER_ALERT_KEY / ADMIN_TOKEN
       |
       v (if authorized)
Fetch schedule from PUBLIC_API_ORIGIN → find takeover by id
       |
       v
sendTakeoverAlert(takeover, env) — Mailchimp + Resend emails
       |
       v
Return {ok: true, message: "Subscriber alert queued."}
```

### Support / Stripe Flow

```
Listener clicks Support → Stripe Checkout
       |
       v
checkout.session.url redirect → Stripe hosted page
       |
       v
checkout.session.completed (or async_payment_succeeded) → tools/support_system.py
       |
       v
HMAC-SHA256 signature verification + replay prevention (300s window)
       |
       v
Idempotent SQLite recording
       |
       v
Public goal/feed: only paid records; subtract charge.refunded
       |
       v
Public data: excludes emails, billing details, IPs, customer IDs
       |
       v
Listener UI: hero/nav/footer entry, accessible modal, suggested amounts, goal, recent feed
```

---

## Service Dependencies

| Service | Depends On | Depended By |
|---------|-----------|-------------|
| Google Drive | rclone | server.py (music library), cache_manager.py |
| station.db | SQLite | server.py (approvals, rotation, catalog), dj_app.py, ai_host.py, catalog_integrity.py |
| rotation-state.json | JSON file | server.py (AutoDJ position) |
| Icecast 2 | server.py (encoder feed), loopback relay (port 14001) | Cloudflare Tunnel, listeners |
| Loopback auth relay (port 14001) | Icecast 2 config + secret files | Encoder, private API (port 14080) |
| Cloudflare Tunnel | cloudflared process | Public listeners, status API |
| Tailscale | allthings140radio-server, allthings140-visuals-realtime | Private control API, inter-VM comms |
| realtime.db | SQLite | visuals-realtime/app.py (messages, schedules, stats) |
| cache-index.json | JSON file | cache_manager.py (READY track mapping) |
| media-index.json | JSON file | visuals-app (media probe caching) |
| ADMIN_ALERT_KEY | Cloudflare secret | _worker.js handleTakeoverAlert auth |
| OBS_STREAM_TOKEN | Cloudflare secret | _worker.js obsAudioStream auth |