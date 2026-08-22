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
- Existing website/broadcast infrastructure: not modified.

## Reliability

FFmpeg uses reconnect flags and bounded backoff. The watchdog restarts stalled
audio after 45 seconds. Voice disconnects, bot moves, FFmpeg exits, and stream
failures schedule bounded reconnects. The bot self-deafens and never receives
or records Discord users.

## Deployment status

The bot is currently running in a persistent terminal session for immediate
Listen Party operation. The production systemd unit is prepared at:

`/home/ebmarah/Projects/AllThings140Radio/config/systemd/allthings140-discord-radio.service`

An always-on Oracle/Tailscale host was not accessible from this workstation,
so boot persistence has not yet been installed. Install the unit on the
always-on host with the README instructions before treating reboot recovery as
complete.

## Operations

```sh
curl http://127.0.0.1:18401/health
journalctl -u allthings140-discord-radio.service -f
sudo systemctl restart allthings140-discord-radio.service
sudo systemctl stop allthings140-discord-radio.service
sudo systemctl start allthings140-discord-radio.service
```

