# Oracle VM Audit

| Field | Value |
|-------|-------|
| Hostname | `allthings140radio-vnic` |
| OS | Oracle Linux 9 UEK 6.12 |
| Uptime | 11 days |
| Tailscale IP | `100.124.12.41` |
| Public IP | `64.181.235.228` |
| SSH user | `opc` (key: `allthings140radio_oracle_ed25519`) |

## Resources

| Resource | Value | Notes |
|----------|-------|-------|
| RAM | 946 MiB total, 558 MiB used | **WARN** — tight for ffmpeg + python + icecast |
| Swap | 363 MiB used / 2.9 GiB | indicates memory pressure |
| Root disk | 34% of 30G | OK |
| Data disk `/srv` | 43% of 50G | OK |
| Inodes | 2% | OK |
| Load | 0.82 | OK |

## Active services (broadcast plane)

- `allthings140radio-server` — ACTIVE
- `allthings140radio-icecast` — ACTIVE
- `allthings140radio-icecast-auth-relay` — ACTIVE
- `allthings140radio-tunnel` — ACTIVE
- `allthings140radio-cache` — ACTIVE
- `allthings140radio-drive` — ACTIVE
- `allthings140-discord-radio` — ACTIVE
- `allthings140-broadcast-mic` — ACTIVE
- `tailscaled` — ACTIVE

## Failed units

- `mcelog.service` — failed (hardware exception logging; non-broadcast)

## Timers

- `allthings140radio-healthcheck.timer` — every ~1 min
- `allthings140radio-backup.timer` — ~10 min
- `allthings140radio-playback-admission.timer` — ~20 min
- `allthings140radio-offhost-backup.timer` — daily encrypted off-host

## Listening ports (selected)

- `127.0.0.1:14080` — public API gateway
- `127.0.0.1:14001` — Icecast source
- `100.124.12.41:14080/14083/14084` — Tailscale-bound services

## Journal errors (24h)

No errors logged for server/icecast/tunnel services.

## Status

**PASS WITH WARNINGS** (RAM)
