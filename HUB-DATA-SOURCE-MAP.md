# ALLTHINGS140 Hub — Data Source & Telemetry Map

**Author:** Antigravity (Google Deepmind)  
**Date:** 2026-08-17  
**Scope:** Telemetry, Health, Metrics, and Version Data queried and rendered by ALLTHINGS140 Hub  

---

## 1. Executive Telemetry Mapping Principle

> **Rule of Truth:** No static or cached value may falsely indicate `HEALTHY` or a historical version when live verification fails. If a service, socket, or file cannot be authoritatively queried, the Hub must display **`UNKNOWN`** or **`UNVERIFIED`** rather than assuming health.

---

## 2. Live Telemetry & Metrics Source Map

| Displayed Value | Authoritative Source | Protocol / Mechanism | Refresh Interval | Failure State / Behavior | Live vs Cached | Stale Risk & Prevention |
|---|---|---|---|---|---|---|
| **Public Stream State** | `https://stream.ebeinc.online/live.mp3` | HTTP GET Range `bytes=0-1024` with 3.5s timeout | 15 seconds | Displays `OFFLINE` if HTTP status != 200/206 or audio bytes == 0 | **LIVE** | None. Directly probes live audio buffer over public internet. |
| **Current Track & Artist** | `https://status.ebeinc.online/api/public/status` | JSON REST API with 3.0s timeout | 15 seconds | Falls back to Oracle VM 1 loopback `http://127.0.0.1:14080/api/health`; if unreachable, displays `"Unknown Track"` | **LIVE** | Stale if Cloudflare worker cache exceeds TTL. Cache-buster `?t=<timestamp>` appended. |
| **Broadcast Mode & Live Host** | `https://status.ebeinc.online/api/public/status` | `mode` (`autodj` vs `live`), `live_host`, `active_takeover` | 15 seconds | Defaults to `AUTODJ` if live takeover payload is absent; marks `UNKNOWN` if status unreachable | **LIVE** | Prevents ghost "NOW LIVE" banners when DJ disconnects. |
| **Global Active Listeners** | `https://status.ebeinc.online/api/public/status` | `listeners` integer from Icecast XML scraper | 15 seconds | Displays `0 Listeners` on timeout/failure | **LIVE** | Scraped every 5s on VM 1; delivered via edge status API. |
| **Broadcast Engine Version** | `tools/server.py` & `/opt/allthings140radio-server/server.py` | Regex extraction of `VERSION = "..."` + `/api/health` `version` | Dynamic on load / rescan | Displays `UNKNOWN` if source file or health API missing | **LIVE / DISCOVERED** | **Fixed:** Previously hardcoded `0.8.0`. Now dynamically extracted from source AST. |
| **Catalog Integrity State** | `/var/lib/allthings140radio/catalog-integrity.json` & `/api/health` | Local filesystem JSON or `/api/health` `catalog_health` | 30 seconds | Displays `UNKNOWN (Unverified)` if file/endpoint unreachable | **LIVE / LOCAL** | Prevents repetition of the 88-track incident. |
| **Approved Playable Tracks** | `/var/lib/allthings140radio/station.db` & status API | `SELECT count(*) FROM tracks WHERE approved = 1` or API `approved_tracks` | 30 seconds | Displays `UNKNOWN` on database lock or network timeout | **LIVE** | Live DB query when local; API query when remote. |
| **Hot Cache Status & Buffer** | `/var/lib/allthings140radio/hot-cache-state.json` | JSON state (`tracks_ready`, `minutes_ready`) | 30 seconds | Displays `UNKNOWN` if service JSON unreadable | **LIVE / LOCAL** | Verified against `/srv/allthings140radio/cache`. |
| **Visuals Workstation Version** | `visuals-app/package.json` & `src-tauri/tauri.conf.json` | JSON parser on active workstation repository | Dynamic on load / rescan | Displays `UNKNOWN` if repository missing | **LIVE / DISCOVERED** | **Fixed:** Previously showed `0.1.32`. Now dynamically discovers `0.1.37`. |
| **Visuals Green Staging Version** | `visuals-green/package.json` & `index.html` | JSON / HTML regex on `visuals-green/` | Dynamic on load / rescan | Displays `UNKNOWN` if directory missing | **LIVE / DISCOVERED** | Discovers active green release tag. |
| **Visuals Realtime Server State** | `https://visuals-realtime-staging.allthings140radio.online/health` | HTTP GET `/health` with 3.5s timeout | 30 seconds | Displays `OFFLINE` if connection refused or HTTP != 200 | **LIVE** | Edge WebSocket / HTTP healthcheck on Oracle VM 2. |
| **Website Frontend Version** | `radio/package.json` & `radio/index.html` | Version tags / cache-bust queries (`?v=5.0.0`) | Dynamic on load / rescan | Displays `UNKNOWN` if missing | **LIVE / DISCOVERED** | Discovers active Cloudflare Pages commit. |
| **DJ App Version** | `tools/dj_app.py` | Regex extraction of `VERSION = "..."` | Dynamic on load / rescan | Displays `UNKNOWN` if missing | **LIVE / DISCOVERED** | **Fixed:** Discovers `0.7.1` dynamically. |
| **Android App Version** | `android/mobile-app/app/build.gradle` | `versionName` in `defaultConfig` | Dynamic on load / rescan | Displays `UNKNOWN` if missing | **LIVE / DISCOVERED** | Discovers `1.1.0` dynamically. |
| **Discord Bot Version** | `discord-bot/package.json` | JSON `version` field | Dynamic on load / rescan | Displays `UNKNOWN` if missing | **LIVE / DISCOVERED** | Discovers `1.0.0` dynamically. |
| **Oracle VM 1 System Metrics** | `allthings140radio-server` via Tailscale SSH | `uptime`, `free -m`, `df -h /` via async subprocess (3.0s timeout) | On user demand / Servers view focus | Displays `UNKNOWN (SSH Unavailable)` if Tailscale disconnected | **LIVE PROBED** | **Fixed:** Hardcoded values eliminated. Probes live or displays `UNKNOWN`. |
| **Oracle VM 2 System Metrics** | `allthings140-visuals-realtime` via Tailscale SSH | `uptime`, `free -m`, `df -h /` via async subprocess (3.0s timeout) | On user demand / Servers view focus | Displays `UNKNOWN (SSH Unavailable)` if Tailscale disconnected | **LIVE PROBED** | **Fixed:** Hardcoded values eliminated. Probes live or displays `UNKNOWN`. |
| **Backup Freshness & Size** | File system scan of `backups/`, `ALLTHINGS140_BACKUPS/` | `stat()` on newest `.tar.gz` archive | Dynamic on load / rescan | Displays `NO RECENT BACKUP` if > 7 days old | **LIVE SCAN** | Analyzes archive size and mtime. |

---

## 3. Telemetry Resiliency & Async Isolation

All telemetry checks in `HealthService`, `ServerService`, and `UpdateService` implement:
1. **Strict Non-Blocking Execution:** Runs in dedicated `QThreadPool` / `threading.Thread` workers.
2. **Hard Socket Timeouts:** Maximum 3.5 seconds per HTTP/socket probe.
3. **Graceful Degraded States:** Individual endpoint failures never bubble up to crash the UI or freeze other checks.
4. **Cache Busting:** All HTTP queries append `?t=<timestamp>` to prevent edge CDN stale caching.
