# AllThings140Radio release checklist

Run this before publishing a site, DJ-app, or server change.

## Automated checks

- `python3 -m unittest discover -s tests -v`
- `python3 tools/radio_healthcheck.py --json`
- `python3 tools/site_smoke.py --json`
- `python3 tools/rotation_audit.py --json`
- `git diff --check`

## Public site

- Open the home page on a narrow Android viewport and desktop viewport.
- Open and close the menu; verify every item is tappable and Escape closes it.
- Start the player, mute/unmute, reload, and confirm automatic reconnect behavior.
- Confirm now-playing, schedule, takeover logo, newsletter, and artist-interest forms.
- Open `/visuals/` and both OBS widget URLs; verify fallback logo and live takeover state.

## Station operations

- Confirm `/health` and `/api/public/status` are fresh.
- Confirm Icecast has an audio source and the current track is advancing.
- Confirm AutoDJ, silence monitor, disk, recording, and relay badges are healthy.
- Confirm the current rotation contains no disabled/missing files.

## Release safety

- Run `python3 tools/backup_radio.py --output /var/backups/allthings140radio`.
- Keep the previous Pages deployment URL available for rollback.
- Never deploy an uncompressed video larger than the Pages asset limit.
