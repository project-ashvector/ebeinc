# EBE Dock integration

EBE Dock AI now includes an `ALLTHINGS140 RADIO` navigation panel. It asynchronously polls Oracle over MagicDNS/Tailscale with a five-second timeout and shows system health, stream/Icecast, listeners, AutoDJ, playable tracks, current/next track, storage and watchdog state. It can run diagnostics and open the installed DJ/Server applications. Production restart remains blocked until an authenticated station session exists; EBE Dock does not store a reusable credential.

Recommended cards: stream, Oracle reachability, AutoDJ, Drive mount, last backup, disk, current/next track, listeners, silence monitor and recent failure. Recommended actions: refresh status, run diagnostics, request Drive refresh, refresh playlist, restart AutoDJ, open DJ app, open Server Manager and open filtered logs. Destructive controls require confirmation and authentication.

Use MagicDNS name `allthings140radio-server`; keep the address configurable. EBE Dock must never synchronize `.env`, `*.token`, SSH keys, rclone configuration, Icecast credentials, station databases or machine identity files. Git is the source history; EBE Dock is transport/visibility, not blind overwrite logic.
