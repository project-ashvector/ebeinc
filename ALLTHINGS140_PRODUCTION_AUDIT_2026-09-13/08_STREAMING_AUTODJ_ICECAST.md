# Streaming / AutoDJ / Icecast

## Live stream

- URL: `https://stream.ebeinc.online/live.mp3`
- HTTP 200, `audio/mpeg`
- Continuous byte delivery verified (364KB in 15s sample)

## Status API (2026-09-14)

- `mode`: autodj
- `stream_status`: online
- `listeners`: 2
- `current_title`: playing midroll track
- `catalog_health`: healthy
- `cache.status`: healthy (49 tracks ready, 168 min)

## Process chain (Oracle)

1. `server.py` AutoDJ reads from `/srv/allthings140radio/cache/READY/`
2. ffmpeg PCM → libmp3lame → Icecast `127.0.0.1:14001/live.mp3`
3. Silence detector ffmpeg on `127.0.0.1:14000/live.mp3`
4. `allthings140radio-tunnel` + Cloudflare → public stream URL

## Icecast

- Service: `allthings140radio-icecast` ACTIVE (not stock `icecast2` unit name)
- Custom binary `/usr/local/bin/icecast`

**Status: PASS**
