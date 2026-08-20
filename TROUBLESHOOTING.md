# Troubleshooting

Start with:

```bash
python3 tools/radio_healthcheck.py
python3 tools/site_smoke.py --json
```

If the website works but audio fails, check public status freshness, Icecast, the persistent encoder, then Cloudflare Tunnel. If AutoDJ fails, inspect the current decoder error, Drive mount, and fallback file before restarting. If Drive fails, do not stop the radio: confirm fallback paths remain readable and repair rclone independently. If metadata is stale, compare `/api/health`, `/api/public/status`, and the tunnel logs.

A useful Codex report contains timestamp, machine, expected behavior, actual behavior, PASS/WARNING/FAIL checks, redacted relevant log patterns, files/services involved, last known-good version and rollback path. Never include tokens, URLs containing credentials, `.env` contents, private keys, cookies or full configuration files.
# Background tab, stalled audio, or stale metadata

Open `https://allthings140radio.online/?diagnostics=1`, reproduce once, and copy
`AllThings140Diagnostics.snapshot()` from DevTools. Confirm the frontend is at
least 1.6.1, `last_state_sync` advances, and a wake produces
`page_resumed -> station_state_refresh -> resync_performed -> stream_attach -> audio_playing`.
Only one `stream_attach` should follow a resume transaction.

Server checks:

```bash
curl -fsS https://status.ebeinc.online/api/public/status | jq '{version,station_generation_id,station_sequence,server_time,current_track_id,started_at,stream_status}'
curl -fsS https://stream.ebeinc.online/live.mp3 --max-time 10 -o /dev/null
ssh allthings140radio-server sudo journalctl -u allthings140radio-tunnel.service --since '30 minutes ago'
ssh allthings140radio-server sudo journalctl -u allthings140radio-server.service --since '30 minutes ago'
```

Do not restart AutoDJ to repair one listener. A listener repair is a fresh GET
of the continuous mount. Android/iOS may require another play gesture after the
OS kills the browser process; that is not a station restart.
