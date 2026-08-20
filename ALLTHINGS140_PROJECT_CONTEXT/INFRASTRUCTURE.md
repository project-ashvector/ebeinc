# ALLTHINGS140 RADIO — Infrastructure

## Oracle Cloud VMs

### VM 1: Broadcast Authority

| Attribute | Value |
|-----------|-------|
| **Hostname** | `allthings140radio-server` |
| **Public IP** | 64.181.235.228 |
| **Tailscale IP** | 100.124.12.41 (active, direct) |
| **Tailnet Zone** | `at140tail` (firewalld zone) |
| **OS** | Oracle Linux 9, UEK 6.12.0 x86_64 |
| **CPU** | 1 OCPU |
| **RAM** | 1 GB visible (946 MiB); 448 MiB was reserved for kdump (disabled after August 15; now 968832 kB MemTotal) |
| **OS Disk** | 30 GB (/), 31% used (21 GB available) |
| **Data Disk** | 50 GB `/srv` volume, 27% used |
| **Services** | `allthings140radio-server` (server.py, AutoDJ)<br>`allthings140radio-icecast` (Icecast 2, port 14000)<br>`allthings140radio-tunnel` (cloudflared)<br>`allthings140radio-drive` (rclone, Google Drive mount)<br>`allthings140radio-cache` (cache_manager.py)<br>`allthings140radio-fallback-sync.timer` (every 15 min)<br>`allthings140radio-icecast-auth-relay` (port 14001) |
| **SSH Key** | `/home/ebmarah/.ssh/allthings140radio_oracle_ed25519` (root-owned, mode 0600)<br>Access: `ssh -i /home/ebmarah/.ssh/allthings140radio_oracle_ed25519 opc@64.181.235.228` |
| **Fallback Sync** | `/usr/local/sbin/allthings140radio-fallback-sync` — rsync from `/srv/allthings140radio/` on VM to `/var/lib/allthings140radio/` locally<br>Runs via systemd timer: OnBootSec=10min, OnUnitActiveSec=15min, RandomizedDelaySec=2min, Persistent=true |
| **Drive Mount** | Google Drive `at140drive:` → `/mnt/allthings140radio-drive` (on VM 1 only)<br>Not currently mounted on this workstation; paths referenced from config |
| **Recent Fixes** | kdump disabled (was causing multi-minute boots, SSH/agent stalls); crashkernel reservation removed; MemTotal verified at 968832 kB after disable |
| **Current Status** | **HEALTHY / ONLINE** — Uptime 3d 4h, load 0.69, memory 497M/946M, disk 31% used, stream online, 2 listeners |

### VM 2: Visuals Realtime Server

| Attribute | Value |
|-----------|-------|
| **Hostname** | `allthings140-visuals-realtime` |
| **Public IP** | 163.192.1.208 |
| **Tailscale IP** | 100.108.145.128 (connected, linux) |
| **OS** | Oracle Linux 9.8, UEK 6.12.0 x86_64 |
| **CPU** | 1 OCPU (Standard.E2.1.Micro) |
| **RAM** | 1 GB visible (946 MiB) |
| **OS Disk** | 30 GB OS disk, 22% used |
| **Services** | `allthings140-visuals-realtime` (aiohttp, port 8765/14140, WebSocket)<br>`allthings140-visuals-tunnel` (cloudflared)<br>`allthings140-visuals-backup.timer` |
| **SSH Key** | `~/.ssh/allthings140_visuals_realtime_ed25519` (for Tauri publish_staging, schedule_takeover commands) |
| **Health** | `{"ok": true, "service": "allthings140-visuals-realtime", "version": "0.1.0-staging", "connections": 0}` |
| **Recent Fixes** | kdump disabled (was causing multi-minute boots, SSH/agent stalls); systemd stop timeout bounded at 15 seconds; tunnel `Requires=` changed to `Wants=` so gateway maintenance doesn't tear down tunnel |
| **Current Status** | **HEALTHY / ONLINE** — Uptime 14h 24m, load 0.00, connections 0, stream health OK |

---

## Cloudflare Resources

### Pages: allthings140radio.online

| Attribute | Value |
|-----------|-------|
| **URL** | `https://allthings140radio.online` |
| **Type** | Cloudflare Pages (HTML5/CSS/JS/spa) |
| **Source Branch** | `main` |
| **Source Folder** | `/` (root) |
| **Custom Domain** | `allthings140radio.online` |
| **HTTP Status** | 200 OK |
| **Deployments** | Baseline: `aac2a08a-9c5a-4184-8470-c9502e38c63b`<br>Post-support: `827399a7.ebeinc-uqt.pages.dev`<br>Latest: production-incremental deployments from main |
| **Service Worker** | v54, cache-first for critical JS, network-first for audio-critical, excludes .mp3/.m3u8/.obs/ from CacheStorage |
| **Recent Deployments** | • Aug 13: Support system deployed (Stripe + Mailchimp)<br>• Aug 15: Visuals z-index fixes, worker auth, service worker stream bypass, 37/37 tests passing |

### Pages: ebeinc

| Attribute | Value |
|-----------|-------|
| **URL** | `https://ebeinc.online` (custom domain) |
| **Type** | Cloudflare Pages (separate repo: project-ashvector/ebeinc) |
| **Source** | index.html, nojekyll, CNAME (ebeinc.online) |
| **A Records** | 185.199.108.153, 185.199.109.153, 185.199.110.153, 185.199.111.153 |
| **CNAME www** | project-ashvector.github.io |

### Pages: allthings140-visuals-green

| Attribute | Value |
|-----------|-------|
| **URL** | `https://allthings140-visuals-green.pages.dev` |
| **Type** | Cloudflare Pages (green staging, frozen) |
| **Status** | FROZEN at production baseline — no cutover authorized<br>HTTP 200 OK, noindex, no-store |
| **SHA-256 Production Baseline** | `4ca1a32e74c2b319fa8c7979b2e68e1486166a2d105c53158f2a417bf976ef32` |
| **Recent Deployments** | • Aug 15: z-index fixes, CORS on /visuals-state, media role separation, health checks<br>• Never cut over to production; production baseline permanently preserved |
| **Media Target** | rsync to OCI VM 2: `opc@100.74.121.38` → `/srv/allthings140-visuals/media` |
| **Recent Fixes** | • Media role separation: explicit `mediaType` values (`stage` vs `visual`); derivatives inherit logical source role<br>• 57 visual entries with explicit mediaType values<br>• Production baseline hash preserved and verified on deploy |

### Workers: _worker.js

| Attribute | Value |
|-----------|-------|
| **File** | `/home/ebmarah/Projects/AllThings140Radio/radio/_worker.js` |
| **Type** | Cloudflare Edge Worker (JavaScript, Workers runtime) |
| **Key Functions** | • Public gateway proxy (routes API calls to status/schedule/support)<br>• Takeover alert auth: `handleTakeoverAlert()` — Bearer token check against ADMIN_ALERT_KEY/TAKEOVER_ALERT_KEY/ADMIN_TOKEN<br>• OBS audio gateway (`obsAudioStream()`) — token validation<br>• Mailchimp webhook handling<br>• Newsletter signup<br>• Takeover interest/proposal routing<br>• Asset fetch fallback for sw-v47.js caching |
| **Auth Status** | ADMIN_ALERT_KEY not yet provisioned in Cloudflare Dashboard/CLI; without it, `/api/public/takeover-alert` is unauthenticated (known issue from Aug 15 remediation)<br>Other endpoints generally functional |
| **Recent Fixes** | • Auth check added to `handleTakeoverAlert()` (line: `const expected = (env.ADMIN_ALERT_KEY || env.TAKEOVER_ALERT_KEY || env.ADMIN_TOKEN || "").trim();`)<br>• Timing-safe comparison using `secrets.compare_digest()`<br>• Deployed updated assets to Cloudflare Pages |

### Tunnel: cloudflared

| Attribute | Value |
|-----------|-------|
| **Binary** | `/usr/local/bin/cloudflared` (or `/usr/local/bin/cloudflared` on VMs)<br>`/usr/local/bin/cloudflared/allthings140radio.yml` (config) |
| **VM 1** | Runs as systemd service `allthings140radio-tunnel` — `cloudflared --config /etc/cloudflared/allthings140radio.yml tunnel run`<br>Restart: always, RestartSec: 5s, TimeoutStopSec: 20s, NoNewPrivileges=true, PrivateTmp=true, ProtectSystem=strict, ProtectHome=true, ReadOnlyPaths=/etc/cloudflared |
| **VM 2** | Runs as systemd service `allthings140-visuals-tunnel` — same cloudflared config<br>Purpose: expose visuals-realtime and media origins to Cloudflare edge |
| **Config** | `/etc/cloudflared/allthings140radio.yml` (VM 1)<br>Config varies on VM 2 |
| **Purpose** | Exposes local services to public internet via Cloudflare edge network<br>Handles: public listener stream, status API, website, visuals realtime, media byte-range streaming |
| **Current Status** | **HEALTHY** — Both VM 1 and VM 2 tunnels online; Cloudflare edge delivering all public endpoints |

---

## Tailscale Mesh Network

| Attribute | Value |
|-----------|-------|
| **Owner** | `ebmarahofficial@` |
| **Status** | Active — all machines on same tailnet |
| **Connected Peers** | 20+ total (see `tailscale status` output for full list) |
| **Key Machines** | • `allthings140radio-server` (100.124.12.41, active, direct)<br>• `allthings140-visuals-realtime` (100.108.145.128, connected)<br>• `ebmarah-Laptop-ai` (100.101.48.127, linux, online)<br>• Various Android, Windows, iOS devices (offline/last-seen varying) |
| **Exit Node** | None active |
| **Funnel** | `https://ebmarah-laptop-ai.tail9b0b89.ts.net` (optional, not used for production)<br>Note: funnel originally stopped tunnel on restart because systemd unit used `Requires=`; changed to `Wants=` |
| **MagicDNS** | `allthings140radio-server` — resolves to Tailscale IP of VM 1; used for authorized SSH and control API access<br>`allthings140-visuals-realtime` — resolves to Tailscale IP of VM 2 |
| **SSH over Tailscale** | Preferred route for authorized control API access (port 14080)<br>Command example: `tailscale ssh --destination=64.181.235.228...` or via MagicDNS host |
| **Firewalld Zone** | `at140tail` — dedicated zone for SSH access; both `sshd` and `tailscaled` must remain enabled |
| **Current Status** | **MESH ACTIVE** — All services reachable over Tailscale; private control API accessible via MagicDNS |

---

## Google Drive / Storage Architecture

### Master Music Library

| Attribute | Value |
|-----------|-------|
| **Source** | Google Drive `at140drive:` |
| **Mount Point** | `/mnt/allthings140radio-drive` (on Oracle VM 1 only)<br>Not mounted on this workstation |
| **Total Tracks** | 571+ filenames in Drive root |
| **Eligible/Approved** | 569 tracks approved for playback |
| **Playable** | 569 tracks (after August 15 recovery; previously 481 due to cache admission issue) |
| **Rights-Blocked** | 2 tracks intentionally unapproved/rights-pending |
| **Emergency Mirror** | `/srv/allthings140radio/data/music/` — 575 verified offline audio files |
| **Hot Cache** | `/srv/allthings140radio/cache/READY/` — ~50 tracks targeting 120 min (TARGET_MINUTES=120)<br>Minimum 45 min (MIN_MINUTES=45)<br>Maximum 5 GB (MAX_BYTES=5GB)<br>Minimum 12% free disk (MIN_FREE_PERCENT=12%) |
| **Cache Index** | `/srv/allthings140radio/cache/cache-index.json` — maps filenames → READY path + status + duration<br>All valid READY files indexed (fixed Aug 15) |
| **Quarantine** | `/var/lib/allthings140radio/music-quarantine/` — isolated tracks under review |
| **Trash** | `/var/lib/allthings140radio/trash/` — unlinked but not deleted files |
| **Last Incident** | Aug 15, 2026: 88 tracks uploaded to Drive were not visible to local playback due to cache admission decoupling; all restored from Drive into emergency mirror via `tools/recover_playback_assets.py`; catalog integrity system now prevents recurrence |
| **Current Catalog State** | HEALTHY — 569 eligible tracks playable; 2 intentionally unapproved/rights-blocked |
| **30-Min Admission Timer** | Prevents tracks from becoming stranded; newly uploaded Drive files wait 30 min before cache admission |

### Local Storage Tiers

| Tier | Path | Content | Size |
|------|------|---------|------|
| **Master** | `/mnt/allthings140radio-drive` (VM 1, Google Drive) | 571+ audio files (MP3/WAV/FLAC/etc.) | Unknown total; Drive quota |
| **Emergency Mirror** | `/srv/allthings140radio/data/music/` | 575 verified offline audio files | ~3-5 GB (verified by incident recovery) |
| **Hot Cache** | `/srv/allthings140radio/cache/READY/` | ~50 pre-fetched tracks (target 120 min) | ~300 MB - 2 GB (varies) |
| **Cache Index** | `/srv/allthings140radio/cache/cache-index.json` | JSON mapping → READY paths + metadata | ~50 KB |
| **Quarantine** | `/var/lib/allthings140radio/music-quarantine/` | Tracks under review | Unknown |
| **Trash** | `/var/lib/allthings140radio/trash/` | Unlinked but not deleted | Unknown |
| **Station DB** | `/var/lib/allthings140radio/station.db` | SQLite — approvals, hashes, metadata, schedules | ~5-10 MB |
| **Catalog Integrity** | `/var/lib/allthings140radio/catalog-integrity.json` | SHA-256 hashes, status (HEALTHY/DEGRADED/CRITICAL) | ~50 KB |
| **Rotation State** | `/var/lib/allthings140radio/rotation-state.json` | Current rotation position | ~1 KB |
| **Backups** | `/var/lib/allthings140radio/backups/` (or `/home/ebmarah/.local/share/allthings140radio/backups/`) | Timestamped SQLite dumps + incremental | Daily encrypted off-host + 10-min local |
| **Workstation Data** | `/home/ebmarah/.local/share/allthings140radio-visuals/` | Tauri workstation data, logs, state, media cache | Varies |

### Backup Strategy

| Frequency | Scope | Destination | Verification |
|-----------|-------|-----------|-------------|
| **Every 10 min** | SQLite `station.db` | `/var/lib/allthings140radio/backups/` (local) | File checksum |
| **Daily** | SQLite `station.db.latest` + encrypted off-host | Cloud or external destination | Decrypt/restore integrity test before upload |
| **Per VM restart** | Full `/srv/allthings140radio/` | Local fallback at `/var/lib/allthings140radio/` | rsync from Oracle VM 1 |
| **On catalog incident** | Full catalog restoration | Emergency mirror + Drive re-sync | SHA-256 + duration verify per track |
| **On visuals deploy** | layout.json + layout.hash + media | Cloudflare Pages artifact | Remote manifest verification (revision + hash match) |

---

## Network Ports

| Port | Service | Direction | Notes |
|------|---------|-----------|-------|
| 14000 | Icecast 2 (loopback) | Local only | MP3 encoder output; loopback-only, not publicly accessible |
| 14001 | Icecast auth relay | Loopback only | Reads real source passwords from protected files; injects into HTTP Basic auth; real passwords never in process table |
| 14080 | Private control API | Loopback + Tailscale | Authorized admin commands (DJ app, server management); Tailscale forwarded; OCI network controls block public access |
| 14082 | Public gateway | Loopback + Cloudflare Tunnel | Exposes loopback Icecast to public via Cloudflare edge; `stream.ebeinc.online/live.mp3` |
| 14083 | Traktor guest ingest | Loopback + restricted | Dummy credentials only; must remain private/restricted; not for public use |
| 8765 / 14140 | Visuals realtime WS | Local only (Oracle VM 2) | WebSocket: presence, chat, reactions, energy, takeover schedules; CORS allowlist |
| 20242 | Static media origin | Local only (Oracle VM 2) | Byte-range video streaming (RFC 7233) for visual assets |
| 25565 | Minecraft (?) | — | Not confirmed as ALLTHINGS140-related |
| 27017 | MongoDB (?) | — | Not confirmed as ALLTHINGS140-related |
| Tailscale | Mesh VPN | All-to-all | MagicDNS, private SSH, inter-VM communication; not a port in traditional sense |
| 22 | SSH | Tailscale + direct | Oracle VM 22 SSH; Tailscale SSH; firewalld zone `at140tail` for authorized access only |

---

## Services Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                      ORACLE CLOUD VM 1 (allthings140radio-server)   │
│  ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────┐ │
│  │  server.py (AutoDJ) │  │  Icecast 2 (port)   │  │ rclone      │ │
│  │  (SQLite, FFmpeg)   │  │  port 14000 loopback│  │ (Google    │ │
│  │                     │  │                     │  │  Drive)     │ │
│  └───────┬─────────────┘  └───────┬─────────────┘  └──────┬──────┘ │
│          │                         │                    │         │
│  ┌───────▼─────────────┐  ┌───────▼─────────────┐  ┌───────▼───────┐ │
│  │  tunnel (cloudflared)│  │ auth relay (14001)  │  │ fallback-sync │ │
│  │  (public gateway)    │  │ (loopback, real      │  │ (rsync from  │ │
│  │                      │  │   source passwords) │  │  VM 1 local)  │ │
│  └───────┬─────────────┘  └───────┬─────────────┘  └───────┬───────┘ │
│          │                         │                    │         │
│  ┌───────▼─────────────┐  ┌───────▼─────────────┐  ┌───────▼───────┐ │
│  │ Cloudflare Tunnel    │  │ loopback-only       │  │ Local workstation│ │
│  │ (cloudflared)        │  │ Icecast (14000)     │  │ (/var/lib/...)   │ │
│  │                      │  │                     │  └───────┬───────┘ │
│  └───────┬─────────────┘  └───────┬─────────────┘        │         │
│          │                         │                    │         │
│  ┌───────▼─────────────┐  ┌───────▼─────────────┐  ┌───────▼───────┐ │
│  │ Public Internet      │  │ Tailscale Mesh      │  │ Authorized SSH  │ │
│  │ (Cloudflare edge)    │  │ (all machines)      │  │ (via MagicDNS)  │ │
│  │                      │  │                     │  └───────┬───────┘ │
│  │ status.ebeinc.online │  │ private API 14080   │         │         │
│  │ stream.ebeinc.online │  │ (loopback + TS)     │         │         │
│  │ allthings140radio.online││ visuals-realtime 8765│         │         │
│  └──────────────────────┘  └─────────────────────┘         │         │
                                                             │         │
                                              ┌─────────────────────┐
                                              │   ORACLE CLOUD VM 2 │
                                              │ (allthings140-       │
                                              │  visuals-realtime)  │
                                              │                     │
                                              │  aiohttp WS (8765/14140)│
                                              │  cloudflared tunnel   │
                                              │  static_media (20242) │
                                              │  realtime.db (SQLite) │
                                              └─────────────────────┘
```

---

## Deployment Pipeline

### Incremental Backup-First Model

```
Step 1: Backup
  → Timestamped copy of target file
  → e.g.: server.py.before-20260815T121447Z
  → Retained for rollback

Step 2: Syntax Check
  → python3 -c "import py_compile; py_compile.compile('tools/server.py')"
  → Or: python3 -m py_compile tools/server.py
  → Fail fast if syntax error

Step 3: Single-File Deploy
  → Install new file to production path
  → e.g.: cp tools/server.py /opt/allthings140radio-server/server.py

Step 4: Restart Affected Service Only
  → systemctl restart allthings140radio-server
  → Do NOT restart all services simultaneously

Step 5: Verify Local Health
  → curl -fsS http://127.0.0.1:14080/api/health
  → Must return OK before considering change stable

Step 6: Verify Public Stream
  → curl -fsS https://stream.ebeinc.online/live.mp3
  → Must return audio (HTTP 200/206, bytes > 0)

Step 7: Rollback if Needed
  → cp server.py.before-TIMESTAMP /opt/allthings140radio-server/server.py
  → systemctl restart allthings140radio-server
  → Re-verify steps 5-6

### Cloudflare Deployments

```
Step 1: Prepare artifacts
  → npx wrangler build (or equivalent)
  → rsync media to OCI VM 2

Step 2: Deploy Pages
  → npx wrangler pages deploy visuals-green-pages-dist \
       --project-name allthings140-visuals-green \
       --branch staging \
       --commit-dirty=true

Step 3: Verify deployment
  → curl -fsS https://allthings140-visuals-green.pages.dev/layout.json
  → Check layoutRevision + layoutHash match local manifest

Step 4: Deploy website
  → Cloudflare Pages auto-deploy from main branch
  → Or: npx wrangler pages deploy --proxy-subdomain allthings140radio

Step 5: Post-deployment health
  → tools/allthings140-diagnose.py
  → Verify: website, status_api, current_track, stream, visuals_realtime
```

### Zero-Downtime Change Pattern (Verified Aug 15, 2026)

```
All services remained 100% online throughout August 15 remediation pass.
No production VM service restarts were required.
All fixes deployed to Cloudflare edge or staged locally.
Rollback retained from timestamped backups but never needed.
```

---

## Disaster Recovery

### VM Restoration

| Tool | Path | Description |
|------|------|-------------|
| `operations/restore-vm.sh` | `/home/ebmarah/Projects/AllThings140Radio/operations/restore-vm.sh` | Automated, dry-run-capable VM restoration with dependency checks and SQLite integrity verification |

### Fallback Synchronization

| Component | Source | Destination | Frequency |
|-----------|--------|-------------|-----------|
| **Station DB** | `/srv/allthings140radio/` (Oracle VM 1) | `/var/lib/allthings140radio/` (local workstation) | Every 15 min (systemd timer) + on-demand |
| **Backups** | `/srv/allthings140radio/backups/station.db.latest` | `/home/ebmarah/.local/share/allthings140radio/backups/cloud-primary.db` | Via fallback-sync script |
| **Media** | `/srv/allthings140radio/data/music/` (Oracle VM 1) | `/var/lib/allthings140radio/` (local) | On-demand via rsync script |

### Restoration Steps (from `restore-vm.sh`)

1. Check binary dependencies (rsync, ssh, sha256sum, sqlite3, python3)
2. Validate archive integrity (binary checks, SQLite PRAGMA integrity_check)
3. Restore from cloud primary backup (`cloud-primary.db`)
4. Restore from local fallback (`/var/lib/allthings140radio/`)
5. Verify station.db integrity after restore
6. Report success/failure with details

### Known DR Gaps

- Extended soak/restart repetition remains a cutover gate for visuals
- Mobile browser regression profile/reconnect testing incomplete
- Physical-phone regression not done
- Full manual takeover asset-package validation not done

---

## Infrastructure Summary

| Category | Count/Status |
|----------|-------------|
| Oracle VMs | 2 (VM 1: HEALTHY/ONLINE, VM 2: HEALTHY/ONLINE) |
| Cloudflare Pages | 3 (allthings140radio.online, ebeinc, allthings140-visuals-green) |
| Cloudflare Workers | 1 (_worker.js, auth partially deployed) |
| Cloudflare Tunnel | 2 (VM 1 + VM 2, both HEALTHY) |
| Tailscale Mesh | Active — all machines on same tailnet |
| Google Drive | Master library (571+ tracks); mount on VM 1 only |
| Local Emergency Mirror | 575 verified files at `/srv/allthings140radio/data/music/` |
| Hot Cache | ~50 tracks at `/srv/allthings140radio/cache/READY/` (target 120 min) |
| Systemd Services | 7+ (server, icecast, tunnel, drive, cache, fallback-sync, visuals-realtime, visuals-backup) |
| SSH Keys | 3 (Oracle VM 1, Oracle VM 2, Visuals realtime admin) |
| Data Directories | 10+ (station data, backups, cache, visuals, media, quarantine, trash, workstation) |

**Production Status:** All services 100% online, 24/7 radio station operational.
**Staging Status:** Green environment frozen; cutover gates still open.
**Last Major Change:** August 15, 2026 — catalog integrity recovery + radio hardening (all services remained online).