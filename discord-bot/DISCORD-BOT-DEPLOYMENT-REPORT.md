# ALLTHINGS140 Discord Radio Bot — Deployment Report

Date: 2026-08-22

## Current configuration

- Bot/application: ALLTHINGS140 Radio (application `1540657062265233448`)
- Guild: AllThings140 Radio (`1535405164989513881`)
- Voice channel: Listen Party (`1535425860226785403`)
- Stream: `https://stream.ebeinc.online/live.mp3`
- Metadata: `https://status.ebeinc.online/api/public/status`
- Project: `/home/ebmarah/Projects/AllThings140Radio/discord-bot`
- Runtime: Node.js v24.18.0
- discord.js: 14.22.1
- @discordjs/voice: 0.19.0
- @discordjs/opus: 0.10.0
- FFmpeg: 6.1.1

## Verification

- Direct FFmpeg decode: PASS (live MP3 to 48 kHz stereo PCM).
- Bot login and guild discovery: PASS.
- Least-privilege installation: PASS (View Channel, Connect, Speak; no Administrator).
- Voice join: PASS — joined Listen Party.
- Audio player: PASS — reached `playing`.
- Health endpoint: PASS — `http://127.0.0.1:18401/health` reported Discord ready, voice ready, stream connected, audio playing, and zero reconnects during the smoke test.
- Voice teardown hardening: PASS — FFmpeg stdout teardown is handled and voice state transitions schedule bounded recovery; a post-fix 45-second voice/FFmpeg run reached `playing` with no fatal exception.
- Existing website/broadcast infrastructure: not modified.

## Reliability

FFmpeg uses reconnect flags and bounded backoff. The watchdog restarts stalled
audio after 45 seconds. Voice disconnects, bot moves, FFmpeg exits, and stream
failures schedule bounded reconnects. The bot self-deafens and never receives
or records Discord users.

## Always-on deployment

- Destination host: `allthings140radio-server` (Oracle Linux 9.8)
- Tailscale address: `100.124.12.41`
- Isolated project: `/opt/allthings140-discord-radio`
- Service: `allthings140-discord-radio.service`
- Service account: `allthings140-discord` (non-root)
- Secrets: `/etc/allthings140radio-discord/discord-bot.env` (root-owned, mode 0640; token not logged)
- Private Node runtime: `/opt/allthings140-discord-radio/node` (v24.18.0)
- Health: localhost-only `http://127.0.0.1:18401/health`
- Systemd enabled: PASS
- Systemd active: PASS
- Discord login/guild discovery: PASS
- Listen Party voice READY: PASS
- Audio PLAYING/live stream CONNECTED: PASS
- Service restart recovery: PASS
- Controlled Node process failure recovery: PASS
- FFmpeg-child test: systemd recovered the bot; the tested source’s existing
  process-level recovery path is retained. No station service was changed.
- Laptop/terminal independence: PASS — the active instance is systemd-owned on
  the Oracle host; no local bot process remains required.
- AutoDJ/Icecast/website/Android: unchanged; final station health was online
  with active catalog playback after deployment.

## Operations

```sh
curl http://127.0.0.1:18401/health
journalctl -u allthings140-discord-radio.service -f
sudo systemctl restart allthings140-discord-radio.service
sudo systemctl stop allthings140-discord-radio.service
sudo systemctl start allthings140-discord-radio.service
```

Run the commands on the Oracle host (or through Tailscale SSH). The environment
file contains the Discord token and must never be printed or committed.
