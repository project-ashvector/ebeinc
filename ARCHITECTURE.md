# AllThings140Radio architecture

## Production path

Google Drive (`at140drive:`) is mounted by rclone at `/mnt/allthings140radio-drive`. The Python station server at `/opt/allthings140radio-server/server.py` indexes approved tracks in SQLite, decodes one source at a time with FFmpeg, mixes scheduled ads, and feeds a persistent 44.1 kHz stereo MP3 encoder. That encoder publishes to loopback-only Icecast on port 14000. A separate loopback public gateway on port 14082 exposes only public status/audio routes through Cloudflare Tunnel. The public website is Cloudflare Pages and reads `status.ebeinc.online`; listeners use `stream.ebeinc.online/live.mp3`.

The Oracle playback engine is the sole timeline authority. Browsers consume the
continuous Icecast MP3 output and a separate read-only, no-store status API.
They never coordinate individual files or send listener heartbeats/control
commands. Public state includes a per-server generation ID and monotonic
sequence so resumed clients can discard stale responses. See
`docs/BACKGROUND_PLAYBACK_RELIABILITY.md` for lifecycle and reconnect details.

The authenticated control API is port 14080. Oracle currently binds it to all interfaces, but OCI network controls block direct public access. Authorized computers should reach it over Tailscale, preferably using the MagicDNS host `allthings140radio-server`, not a hard-coded IP. Port 14083 is the token-protected live guest source listener and must remain private/restricted.

## Sources of truth

- Audio masters: dedicated Google Drive root; Oracle fallback mirror provides outage continuity.
- Catalog, approvals, users, schedules and audit records: `/var/lib/allthings140radio/station.db`.
- Rotation position: `/var/lib/allthings140radio/rotation-state.json`.
- Station settings: `/etc/allthings140radio/config.json`; secrets remain outside Git.
- Public site: `radio/` in this project, deployed to Cloudflare Pages.
- Operational source: `tools/server.py`, `tools/radio_extensions.py`, and `tools/dj_app.py`.

Icecast source authentication is now handled by a loopback-only relay on port 14001. FFmpeg uses a non-secret local URL; the relay reads the rotated credential from a protected file. Ports 14080 and 14083 bind to loopback and are forwarded only inside the tailnet by Tailscale Serve.

New audio is admitted through `STAGING → validation/hash/deduplication → READY → catalog review`. Approval remains explicit. No component makes playback depend on a browser or administration laptop.
