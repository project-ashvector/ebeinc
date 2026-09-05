# ALLTHINGS140 production state

Verified directly on 2026-09-04/05. No services were restarted and no production configuration was changed.

## Broadcast authority (Oracle)

- Host: `allthings140radio-vnic` (`64.181.235.228`)
- Server: 0.8.0, active
- Deployed server: `/opt/allthings140radio-server/server.py`
- Working state/database: `/var/lib/allthings140radio`
- Live database: `/var/lib/allthings140radio/station.db`
- Music master mount: `/mnt/allthings140radio-drive` (`at140drive:` via rclone)
- Emergency mirror: `/srv/allthings140radio/data/music`
- Public status: online, stream status online, version 0.8.0
- Active services: server, Icecast, tunnel, Drive mount, cache, Discord radio bot
- Active timers: health/backup, playback admission, daily encrypted off-host backup

The deployed `server.py`, `radio_supervisor.py`, `cache_manager.py`, `catalog_integrity.py`, and Discord `index.js` hashes exactly match current local files.

## Website / Cloudflare

- Public URL: `https://allthings140radio.online/`
- Stream: `https://stream.ebeinc.online/live.mp3`
- Status: `https://status.ebeinc.online/api/public/status`
- Local web source: `radio/`
- `radio/app.js` and `radio/sw.js` are byte-identical to public production.
- Public `index.html` differs only through Cloudflare email-obfuscation rewriting of the source `mailto:` link and decoder injection.
- A live stream GET delivered 364,000 bytes before the bounded audit timeout.

## Visuals / Green Room realtime host

- Host: `allthings140-visuals-realtime` (`35.252.139.220` SSH target)
- Runtime health version: `0.3.0-workstation`
- Deployed source: `/opt/allthings140-visuals-realtime/app.py`
- State: `/var/lib/allthings140-visuals/realtime.db`
- Loopback service port: 8765
- Active services: realtime gateway and Cloudflare tunnel
- Active timer: daily state backup
- Deployed `app.py`, requirements, backup/restore scripts, and service unit exactly match local `visuals-realtime/` files.
- Version warning: checked-in/deployed `VERSION.txt` says `0.2.0-staging`, while `app.py` runtime reports `0.3.0-workstation`.

## Android

- Current local source: 1.3.9 / versionCode 25
- Current local release outputs: September 2, 2026 APK/AAB under `android/mobile-app/app/build/outputs/`
- Verified Google Play Internal state from project continuity evidence: 1.3.7 / versionCode 23
- Google Play Production: not published
- Validation: `testReleaseUnitTest bundleRelease` passed, including lint-vital and bundle signing
- Classification: local source/build is newer than the tested Play deployment

## Desktop/workstation applications

Installed packages include Hub 1.2.1, Visuals 0.1.43, DJ 0.7.0, Server package 0.7.1, Track Scout 0.1.0, and `at140radiocs` 0.1.1. The installed Server desktop package is not broadcast authority; Oracle runs source version 0.8.0. No ALLTHINGS140 local workstation service/process was active during capture.

## Google Drive

- Mounted live on Oracle at `/mnt/allthings140radio-drive`
- 2,509 files, 21,732,660,288 bytes
- 2,483 audio files: 2,172 MP3, 309 WAV, 2 FLAC
- 26 `.enc` files: encrypted state backups
- No source trees, plaintext configs, Android builds, or plaintext DB exports detected
- Authority: `MEDIA_MASTER` plus `BACKUP`/`RELEASE_ARCHIVE` for encrypted state packages

## Production validation

| Check | Result |
|---|---|
| Website | PASS |
| Public status/API | PASS |
| Stream bytes | PASS |
| Oracle server/AutoDJ service | PASS |
| Icecast service | PASS |
| Drive mount | PASS |
| Catalog DB integrity | PASS |
| Visuals realtime health | PASS |
| Visuals backup timer | PASS |
| Android source tests/build | PASS |
| Python pytest suite | WARN — pytest environment missing; syntax validation passed |
| Tailscale client on workstation | WARN — local tailscaled not running; direct SSH succeeded |
| Extended real-device auth/alert entitlement | WARN — prior evidence only; not destructively retested |
