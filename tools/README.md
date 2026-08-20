# Radio operations checks

Run the public station check from this directory:

```bash
python3 tools/radio_healthcheck.py

# Read-only production asset/API smoke test
python3 tools/site_smoke.py

# Read-only rotation diversity audit
python3 tools/rotation_audit.py

# Timestamped SQLite/config/rotation backup
python3 tools/backup_radio.py --output /var/backups/allthings140radio
```

The command exits `0` only when the site, status API, current track, and
Icecast stream all pass. Use `--json` for a scheduler or monitoring service:

```bash
python3 tools/radio_healthcheck.py --json
```

For a local cron job, redirect output to a log and alert whenever the command
exits nonzero. The stream check uses a short ranged `GET`; Icecast may reject
`HEAD` even while the audio mount is healthy.

The health check defaults to `https://allthings140radio.online/` and fails if
the public status timestamp is older than three minutes. Use
`--max-track-age SECONDS` for a tighter or looser operational threshold.
