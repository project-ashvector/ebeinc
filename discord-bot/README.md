# ALLTHINGS140 Radio Discord voice bot

This daemon is an independent audio consumer of the production station feed:

`https://stream.ebeinc.online/live.mp3`

It does not capture the website, duplicate AutoDJ, record Discord users, or
handle video. FFmpeg decodes the live MP3 to 48 kHz stereo PCM and
`@discordjs/voice` sends it to the configured Discord voice channel.

## Configuration

Copy `.env.example` to `.env` and set `DISCORD_TOKEN` privately. The token is
never logged or committed. Set `DISCORD_CLIENT_ID`, `DISCORD_GUILD_ID`, and
`DISCORD_VOICE_CHANNEL_ID`; the existing ALLTHINGS140 `Listen Party` channel is
`1535425860226785403`.

The service account should own the environment file with mode `0600`.

## Run locally

```sh
npm ci
npm start
curl http://127.0.0.1:18401/health
```

## Commands

- `/radio-status` — ephemeral bot, voice, stream, FFmpeg, uptime, and reconnect health.
- `/nowplaying` — reads the existing public station metadata endpoint.
- `/radio-reconnect` — schedules a bounded reconnect; requires Manage Server (or `DISCORD_OWNER_ID`).

## Recovery behavior

The bot reconnects with bounded exponential backoff (1 second through 60
seconds), restarts FFmpeg if it exits or stops producing bytes for 45 seconds,
rejoins the configured voice channel after a voice disconnect/move, and exposes
health at localhost. It self-deafens and never receives or records user audio.

## systemd

Install the supplied `config/systemd/allthings140-discord-radio.service` as a
system service, create a dedicated non-root `allthings140-discord` account, and
place the environment file at `/etc/allthings140radio/discord-bot.env` with
mode `0600`. Then:

```sh
sudo systemctl daemon-reload
sudo systemctl enable --now allthings140-discord-radio.service
systemctl status allthings140-discord-radio.service
journalctl -u allthings140-discord-radio.service -f
sudo systemctl restart allthings140-discord-radio.service
sudo systemctl stop allthings140-discord-radio.service
```

Do not install this unit on the broadcast host unless it is an isolated
service account and resource limits are acceptable. The bot is designed to be
an independent consumer and must not alter Icecast, AutoDJ, or station files.
