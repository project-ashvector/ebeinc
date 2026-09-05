# ALLTHINGS140 Radio — Oracle Hardware Decommission Maintenance (2026-09)

## INSTANCE

- Name: `allthings140radio-server`
- Region: US West (San Jose), `us-sanjose-1`
- Compartment: `AllThings140Radio (root)`
- Availability domain: AD-1
- Fault domain: FD-1
- Shape: `VM.Standard.E2.1.Micro` (1 OCPU, 1 GB)
- Lifecycle state after maintenance: Running
- Instance OCID: recorded in OCI Console; intentionally redacted here
- Private IP: `10.0.0.220`
- Public IP: `64.181.235.228`
- Tailscale IP: `100.124.12.41`
- Local NVMe: none indicated; paravirtualized boot and remote data volumes

Maintenance due window: 2026-09-18 06:31:42 UTC to 2026-09-19 06:31:42 UTC

OCI maintenance action: **Reboot migration**

Recommended customer action: proactively reboot migrate before the mandatory evacuation deadline.

Proactive migration supported: YES (standard VM; normal graceful reboot is the documented trigger).

## PRE-MAINTENANCE AUDIT

All production units were enabled and active before the action: broadcast mic, Discord radio relay, cache, drive, Icecast auth relay, Icecast, radio server, and Tailscale tunnel. No tmux/screen/PM2 dependency was present. `/srv/allthings140radio` was mounted from `/dev/sdb` (XFS), and `/etc/fstab` uses `nofail` for the music volume. No NFS mounts or local NVMe were present.

Baseline health: Icecast online, live source connected, AutoDJ running, current music playing, metadata/API healthy, raw stream delivered 245,760 bytes in 8 seconds, public IP/Tailscale identity stable.

Scoped rollback backup:

`/var/backups/allthings140radio/maintenance-20260902T184348Z`

Key SHA-256 values: `fstab` `5626a2012a48bb8b9f40b792c159aae6e9ff600d8a0934b5765f2934c79cb761`; `server.py` `6a9ad3d80cb46e731960cdcbf5d0601a0b5258b4959741648f4aa92e2b96b448`; `station.db` `3ca5385a70abd39a36038f59cfc7719e8fe7d6ab7e5e0a41547a7b09c94ed2a9`.

## MIGRATION

- Proactive migration performed: YES
- Method: OCI Console graceful reboot request followed by graceful guest `systemctl reboot`; no force reset, termination, replacement VM, or volume detach
- Start: 2026-09-02 19:07:30 UTC (reboot broadcast)
- New boot: 2026-09-02 19:08:36 UTC
- Raw Icecast source resumed: 2026-09-02 19:10:05 UTC
- Approximate radio outage: ~2 minutes 35 seconds (based on source restart)
- Maintenance event state immediately after reboot: **Processing** (OCI control-plane confirmation still pending at report time)
- Host migration: guest reboot completed; OCI event processing must be rechecked until it reports cleared

## STORAGE

- Boot volume: PASS (paravirtualized; system booted normally)
- Attached data volume: PASS (`/dev/sdb` mounted at `/srv/allthings140radio`)
- fstab: PASS; persistent music mount has `nofail`
- Data loss: NONE observed

## SERVICES BEFORE / AFTER

| Service | Before | After |
|---|---|---|
| allthings140radio-icecast.service | active, enabled | active, enabled |
| allthings140radio-server.service (AutoDJ/API) | active, enabled | active, enabled |
| allthings140-discord-radio.service | active, enabled (historical crash/restart issue) | active, enabled; health OK, reconnects 0 since boot |
| allthings140radio-cache/drive/tunnel/auth-relay | active, enabled | active, enabled |
| allthings140-broadcast-mic.service | active, enabled | active, enabled |

## RADIO

- Icecast: PASS
- AutoDJ: PASS; catalog rotation running, `ad_playing=false`
- Encoder/source: PASS
- Raw stream: PASS (post-reboot sample delivered 245,760 bytes/8 seconds)
- Metadata/API: PASS
- Website listening endpoint: PASS (public stream endpoint reachable)
- Android listening: stream endpoint available; physical-device test not performed in this maintenance window
- Discord relay: PASS immediately after boot (`voice=ready`, `audio=playing`, `stream=connected`)
- Discord voice playback: PASS; relay health endpoint returned OK

The Discord relay had a pre-existing historical `ERR_STREAM_PREMATURE_CLOSE` restart pattern (systemd `Restart=always`, historical `NRestarts=1419`). It was stable during the pre-migration watch and after reboot; this remains a follow-up reliability item, not an OCI migration failure.

## NETWORK

- Public IP preserved: YES (`64.181.235.228`)
- Private IP preserved: YES (`10.0.0.220`)
- Tailscale: PASS (`100.124.12.41`)
- DNS/stream URL behavior: PASS; no DNS or Cloudflare changes made

## BOOT PERSISTENCE

- All critical production services enabled: PASS
- Manual terminal dependencies remaining: NO
- Systemd failed units after boot: `mcelog.service` only (unrelated host warning); no critical radio unit failed
- Non-fatal boot warnings: auditd sendmail notice and existing rclone config permission warning; radio storage/backup remained healthy

## ORACLE MAINTENANCE

- Maintenance before: Scheduled, Mandatory, Evacuation, Reboot migration
- Maintenance after: Processing at the time of this report; verify later for Cleared/Completed
- Outstanding maintenance action: OCI control-plane processing confirmation pending

## FINAL RESULT

- ALLTHINGS140 reboot-migrated to healthy Oracle hardware: **PASS for guest reboot/migration trigger; OCI event-clear confirmation pending**
- 24/7 operation restored: **PASS**
- No data loss: **PASS**
- Alert-ad repair changed: **NO**; no global account-sensitive injector was re-enabled
- Payments/subscriptions: **UNCHANGED / FROZEN**

This report must be updated once OCI changes the event from Processing to its final cleared/completed state and after a longer stability observation.
