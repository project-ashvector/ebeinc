# ALLTHINGS140 RADIO — Canonical Paths

## Project Source

| Purpose | Path | Notes |
|---------|------|-------|
| **Main project root** | `/home/ebmarah/Projects/AllThings140Radio/` | Git repo (origin: `https://github.com/project-ashvector/ebeinc.git`), branch `main`, version 2.3.2, 24 commits ahead of origin |
| **Git config** | `/home/ebmarah/Projects/AllThings140Radio/.git/` | Remote: `origin` (fetch/push); also tracked: `project-ashvector/ebeinc` GitHub repo |
| **Project index** | `/home/ebmarah/Projects/PROJECT_INDEX.md` | Master project index; per-project operation notes |
| **Project machine index** | `/home/ebmarah/Projects/projects.json` | Machine-readable project catalog |

## Server & Radio Tools

| Purpose | Path | Notes |
|---------|------|-------|
| **Server source** | `/home/ebmarah/Projects/AllThings140Radio/tools/server.py` | Python 3, ~190 KB; main Oracle broadcast engine |
| **Radio extensions** | `/home/ebmarah/Projects/AllThings140Radio/tools/radio_extensions.py` | AlertBus, ArchiveManager, FailureNotifier; imported by server.py |
| **AI host** | `/home/ebmarah/Projects/AllThings140Radio/tools/ai_host.py` | Ollama LLM + Piper TTS; scheduled radio breaks |
| **DJ app** | `/home/ebmarah/Projects/AllThings140Radio/tools/dj_app.py` | Tkinter admin UI (~138 KB); private API port 14080 |
| **Catalog integrity** | `/home/ebmarah/Projects/AllThings140Radio/tools/catalog_integrity.py` | SHA-256 verification, reconcile DB with Drive/mirror |
| **Recover assets** | `/home/ebmarah/Projects/AllThings140Radio/tools/recover_playback_assets.py` | Restore from Drive into emergency mirror (Aug 15 incident) |
| **Cache manager** | `/home/ebmarah/Projects/AllThings140Radio/tools/cache_manager.py` | Predictive hot cache, 50-track target, 120 min |
| **Support system** | `/home/ebmarah/Projects/AllThings140Radio/tools/support_system.py` | Stripe + Mailchimp, HMAC verification, idempotent recording |
| **Radio healthcheck** | `/home/ebmarah/Projects/AllThings140Radio/tools/radio_healthcheck.py` | CLI health monitor; `--visuals` flag added Aug 15 |
| **Server manager** | `/home/ebmarah/Projects/AllThings140Radio/tools/server_manager.py` | VM operations; backup management |
| **AI host** (dep) | `/opt/allthings140radio-server/ai_host.py` | Installed on Oracle VM 1 |

## DJ Application

| Purpose | Path | Notes |
|---------|------|-------|
| **DJ app (installed)** | `/opt/allthings140radio-dj/dj_app.py` | Running as PID 889217; Tkinter UI; private API 14080 |
| **DJ app backups** | `/opt/allthings140radio-dj/` (many .backup-*.py files) | 16 backup versions retained; never delete without archive |
| **DJ app service** | systemd: `allthings140radio-dj` (not a systemd service, standalone Python process) | Not managed by systemd as a service; runs as user process |

## Visual Systems

| Purpose | Path | Notes |
|---------|------|-------|
| **Visuals app (Tauri)** | `/home/ebmarah/Projects/AllThings140Radio/visuals-app/` | Tauri v0.1.30; Rust + React/Vite; dev port 14340 |
| **Visuals green staging** | `/home/ebmarah/Projects/AllThings140Radio/visuals-green/` | Web-based staging; z-index fixes; frozen at production baseline |
| **Visuals realtime** | `/home/ebmarah/Projects/AllThings140Radio/visuals-realtime/` | aiohttp WS server (v0.1.0-staging); port 8765/14140 |
| **Visuals stage media** | `/home/ebmarah/Videos/at140radio/desktop visuals/stage/` | 1 file: `alpha.mov` (HEVC, 1920x1080, ~48s, no alpha; runtime H.264 convert) |
| **Visuals media** | `/home/ebmarah/Videos/at140radio/desktop visuals/visuals/` | 57 MP4 files (browser-optimized H.264 derivatives) |
| **Visuals workstation data** | `/home/ebmarah/.local/share/allthings140radio-visuals/` | Tauri data dir; workstation.json, media-index.json, media-cache/, logs/ |
| **Visuals package logs** | `/home/ebmarah/.local/share/allthings140radio-visuals/workstation.log` | Operation log; useful for debugging |
| **Visuals package state** | `/home/ebmarah/.local/share/allthings140radio-visuals/workstation.json` | Persisted layout state, presets, version |

## Website & Cloudflare

| Purpose | Path | Notes |
|---------|------|-------|
| **Website source** | `/home/ebmarah/Projects/AllThings140Radio/radio/` | HTML5/JS/CSS; deployed to Cloudflare Pages |
| **Service workers** | `/home/ebmarah/Projects/AllThings140Radio/radio/sw.js`, `sw-v47.js` | Cache v54; exclude .mp3/.m3u8/.obs/ |
| **Edge worker** | `/home/ebmarah/Projects/AllThings140Radio/radio/_worker.js` | Cloudflare Edge Worker; takeover alert auth, proxy routing |
| **Website HTML** | `/home/ebmarah/Projects/AllThings140Radio/index.html` | Public entry point; deployed to Pages |
| **Cloudflare config** | `/etc/cloudflared/allthings140radio.yml` (varies) | Tunnel config for VM 1 and VM 2 |
| **Wrangler config** | `/home/ebmarah/Projects/AllThings140Radio/archive-worker/wrangler.jsonc` | Worker/project config |

## Oracle Cloud VMs

| Purpose | Path | Notes |
|---------|------|-------|
| **VM 1 server** | `/opt/allthings140radio-server/` | server.py, icecast config, ads/, ai_host.py, backups/ |
| **VM 1 data** | `/var/lib/allthings140radio/` | station.db, rotation-state.json, catalog-integrity.json, music-quarantine/, trash/, backups/ |
| **VM 1 srv data** | `/srv/allthings140radio/` | Emergency mirror (575 files), data/music/, cache/ |
| **VM 1 rclone mount** | `/mnt/allthings140radio-drive` | Google Drive `at140drive:` (Oracle VM 1 only) |
| **VM 1 fallback sync** | `/usr/local/sbin/allthings140radio-fallback-sync` | rsync script from VM 1 /srv to local /var/lib |
| **VM 1 SSH key** | `/home/ebmarah/.ssh/allthings140radio_oracle_ed25519` | Root-owned, mode 0600 |
| **VM 1 systemd services** | `/etc/systemd/system/allthings140radio-*.service` | server, icecast, tunnel, drive, cache, fallback-sync, tunnel |
| **VM 1 cloud config** | `/etc/cloudflared/allthings140radio.yml` | Tunnel config |
| **VM 2 data** | `/var/lib/allthings140-visuals/` | realtime.db (messages, schedules, stats) |
| **VM 2 server** | `/opt/allthings140-visuals-realtime/` | app.py (aiohttp), realtime.py (possibly) |
| **VM 2 tunnel** | cloudflared service | Expose visuals origins to Cloudflare edge |
| **VM 2 SSH key** | `~/.ssh/allthings140_visuals_realtime_ed25519` | For Tauri publish_staging, schedule_takeover |
| **VM 2 OS disk** | 30 GB, 22% used | Oracle Linux 9.8 |
| **VM 2 data disk** | 30 GB, 27% used | /srv volume |

## Local Workstation

| Purpose | Path | Notes |
|---------|------|-------|
| **AllThings140 project context** | `/home/ebmarah/Projects/ALLTHINGS140_PROJECT_CONTEXT/` | This folder — project memory documentation |
| **EBE Dock** | `/home/ebmarah/Projects/EBEDock/` | Related but separate project; symlink `ebe-dock -> /home/ebmarah/Projects/EBEDock` |
| **EBE Dock AI releases** | `/home/ebmarah/EBE-Dock-AI-Releases/` | AI-related release artifacts |
| **EBE Dock AI source** | `/home/ebmarah/.cache/...` / EBE-Dock-AI-Source-*.zip | AI source distributions |
| **Home directory** | `/home/ebmarah/` | User workspace; contains COMPUTER_MAP.md, various project dirs |
| **Projects parent** | `/home/ebmarah/Projects/` | All project directories |
| **Videos** | `/home/ebmarah/Videos/` | Contains `at140radio/desktop visuals/`, other media |
| **Music** | `/home/ebmarah/Music/` | Personal music; NOT the radio catalog |
| **Downloads** | `/home/ebmarah/Downloads/` | Downloads folder |
| **Archive** | `/home/ebmarah/Archive/` | Archived/duplicate material (needs review) |
| **Inbox to sort** | `/home/ebmarah/Inbox-To-Sort/` | Needs manual sorting |

## Configuration

| Purpose | Path | Notes |
|---------|------|-------|
| **Production config** | `/etc/allthings140radio/config.json` | Mode 0600, root-owned; secrets outside Git |
| **Support env** | `/etc/allthings140radio/support.env` | Stripe live keys; mode 0600, root-owned; backup at `support.env.test-mode-backup-20260813` |
| **Rclone config** | Not found on this workstation | Configured on Oracle VM 1 only (`at140drive:` → `/mnt/allthings140radio-drive`) |
| **Cloudflare tunnel config** | `/etc/cloudflared/allthings140radio.yml` (VM 1)<br>varies on VM 2 | cloudflared tunnel configuration |
| **.env example** | `/home/ebmarah/Projects/AllThings140Radio/.env.example` | Create protected runtime config from this; never commit |
| **Tailscale auth** | `tailscale status` output | Mesh network status; all machines on `ebmarahofficial@` tailnet |
| **Firewalld zone** | `at140tail` | Dedicated SSH zone; both `sshd` and `tailscaled` must remain enabled |

## Backup & Recovery

| Purpose | Path | Notes |
|---------|------|-------|
| **Local backups** | `/var/lib/allthings140radio/backups/` | SQLite dumps every 10 min |
| **Cloud primary backup** | `/var/lib/allthings140radio/backups/cloud-primary.db` | Daily encrypted off-host backup |
| **Fallback sync script** | `/usr/local/sbin/allthings140radio-fallback-sync` | rsync from Oracle VM 1 → local workstation |
| **Pre-deployment rollback** | `/opt/allthings140radio-server/server.py.before-*.py` | Timestamped before-deployment copies; 15+ backups retained |
| **Catalog incident backup** | `/srv/allthings140radio/backups/catalog-incident-20260815T111250Z/` | Aug 15 incident evidence |
| **Pre-deploy integrity backup** | `/srv/allthings140radio/backups/predeploy-integrity-20260815T121447Z/` | Aug 15 pre-deployment rollback point |
| **Workstation backup** | `/home/ebmarah/.local/share/allthings140radio/backups/` | User-level backups |
| **Visuals diagnostics** | `/home/ebmarah/.local/share/allthings140radio-visuals/diagnostic-*.json` | Export reports from Tauri app |

## Media Paths

| Purpose | Path | Content |
|---------|------|---------|
| **Google Drive master** | `/mnt/allthings140radio-drive` (VM 1) | 571+ audio files (MP3/WAV/FLAC/etc.) |
| **Emergency mirror** | `/srv/allthings140radio/data/music/` | 575 verified offline audio files |
| **Hot cache READY** | `/srv/allthings140radio/cache/READY/` | ~50 pre-fetched tracks (target 120 min) |
| **Cache index** | `/srv/allthings140radio/cache/cache-index.json` | JSON: filename → READY path + status + duration |
| **TEMP partials** | `/srv/allthings140radio/cache/TEMP/` | Partial downloads before atomic move to READY |
| **Quarantine** | `/var/lib/allthings140radio/music-quarantine/` | Tracks under review; isolated from playback |
| **Trash** | `/var/lib/allthings140radio/trash/` | Unlinked but not deleted files |
| **Stage source** | `/home/ebmarah/Videos/at140radio/desktop visuals/stage/` | `alpha.mov` (HEVC, 1920x1080, ~48s, no alpha) |
| **Visuals source** | `/home/ebmarah/Videos/at140radio/desktop visuals/visuals/` | 57 MP4 files (browser-optimized H.264) |
| **Ad audio** | `/opt/allthings140radio-server/ads/` | Ad files for AutoDJ mix_ad() |
| **Takeover logos** | `/var/lib/allthings140radio/takeover-logos/` | Artist takeover logo files |

## Systemd Services

| Service | Path | Description |
|---------|------|-------------|
| `allthings140radio-server` | `/etc/systemd/system/allthings140radio-server.service` | Oracle broadcast server (server.py); **OVERRIDE** at `/etc/systemd/system/allthings140radio-server.service.d/ads.conf` (ads dir env) |
| `allthings140radio-icecast` | `/etc/systemd/system/allthings140radio-icecast.service` | Icecast 2 (port 14000 loopback) |
| `allthings140radio-tunnel` | `/etc/systemd/system/allthings140radio-tunnel.service` | cloudflared tunnel (public gateway) |
| `allthings140radio-drive` | `/etc/systemd/system/allthings140radio-drive.service` | rclone Google Drive mount |
| `allthings140radio-cache` | (derived) | cache_manager.py service |
| `allthings140radio-fallback-sync` | `/etc/systemd/system/allthings140radio-fallback-sync.service` + timer | Every 15 min rsync from VM 1 /srv to local /var/lib |
| `allthings140radio-icecast-auth-relay` | (internal port 14001) | Auth relay; reads source passwords from protected files |
| `allthings140-visuals-realtime` | `/etc/systemd/system/allthings140-visuals-realtime.service` | aiohttp WS server on VM 2 |
| `allthings140-visuals-tunnel` | `/etc/systemd/system/allthings140-visuals-tunnel.service` | cloudflared tunnel on VM 2 |
| `allthings140radio-fallback-sync.timer` | `/etc/systemd/system/allthings140radio-fallback-sync.timer` | OnBootSec=10min, OnUnitActiveSec=15min, RandomizedDelaySec=2min, Persistent=true |

## Release Artifacts

| Artifact | Path | Notes |
|----------|------|-------|
| **Migration ZIP** | `dist/ALLTHINGS140/Migration/allthings140radio-backup-migration.zip` | Excludes env files, private keys, signing stores, large media; Google Drive remains master |
| **Baseline commit** | `69991d2124bb4c6450e3d4c7f64998aa9b9b50ed` / `allthings140-pre-final-20260813` | Tag/anchor for migration |
| **Cloudflare deployment** | `827399a7.ebeinc-uqt.pages.dev` (post-support)<br>`aac2a08a-9c5a-4184-8470-c9502e38c63b` (baseline) | Pages URLs |
| **Visuals production hash** | `4ca1a32e74c2b319fa8c7979b2e68e1486166a2d105c53158f2a417bf976ef32` | Never change without authorization |
| **Tauri package** | `0.1.3` | Installed workstation package; SHA-256: `72d7881ebbb8ddd5ed87c363f4a28bebbef9baf21682a23a9ca0c44aa8b03eb8` (v0.1.3)<br>or `b7fe1cbf65994b260ab0b58af823f5db69a76adacd53c0601d2f8840e52d8b0c` (v0.1.4) |

---

## Key Symlinks

| Symlink | Target | Notes |
|---------|--------|-------|
| `~/ebe-dock` | `/home/ebmarah/Projects/EBEDock` | EBE Dock symlink; separate project |
| **All paths above** | **Verified from filesystem inspection** | Not assumed; each validated from actual machine state |