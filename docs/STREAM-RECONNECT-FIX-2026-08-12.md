# Stream reconnect reliability fix — 2026-08-12

## Root cause

Icecast used a 10-second `source-timeout`. Brief decoder or Google Drive read
stalls could exceed that window, causing Icecast to close FFmpeg's local source
socket. The server recovered by restarting the AutoDJ loop, while some native
MP3 browser connections remained paused until the listener refreshed.

## Changes

- Production Icecast `source-timeout` increased from 10 to 60 seconds.
- `AutoDJManager.write_pcm()` retries a dropped encoder connection three times
  and resends the current PCM chunk without restarting the current track.
- The website forces a cache-busted MP3 URL on reconnect.
- The website monitors playback progress every five seconds and reconnects if
  playback has not advanced for 18 seconds.

## Verification

- 13 Python regression tests passed.
- JavaScript and Python syntax checks passed.
- Production website smoke and radio health checks passed.
- AllThings140Radio server, Icecast, and Drive services remained active.
- No new Icecast source timeout was observed after deployment monitoring.

## Production rollback

Backups created on Oracle:

- `/opt/allthings140radio-server/server.py.pre-reconnect-fix-20260812`
- `/etc/allthings140radio/icecast.xml.pre-reconnect-fix-20260812`

Restore those files, then restart Icecast and the radio server only after
confirming no artist takeover is active.

