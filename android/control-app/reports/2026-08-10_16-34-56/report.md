# at140radiocs diagnostic
Generated: 2026-08-10_16-34-56

## Summary
- Tailscale: CONNECTED
- Radio online: True

## Relevant status
```json
{
  "ok": true,
  "name": "AllThings140Radio",
  "version": "0.6.0",
  "autodj": {
    "running": true,
    "pid": 837623,
    "mode": "catalog rotation",
    "last_error": "",
    "tracks": 444,
    "current_track_id": 136,
    "current_title": "LOUD",
    "current_artist": "BENDA & VASTIVE",
    "started_at": 1786404745,
    "position_seconds": 151.1254596710205,
    "duration_seconds": 192.574678,
    "next_track_id": 614,
    "next_title": "Saunter - Shock Value [Free Download]",
    "next_artist": "",
    "transition_reason": "automatic",
    "ad_playing": false,
    "ad_name": "",
    "progress": 0.7847628838876756
  },
  "icecast": {
    "online": true,
    "listeners": 3,
    "live_source": true,
    "sources": [
      {
        "genre": "various",
        "listener_peak": 4,
        "listeners": 3,
        "listenurl": "http://localhost:14000/live.mp3",
        "server_description": "140 BPM and bass music, live around the clock.",
        "server_name": "AllThings140Radio",
        "server_type": "audio/mpeg",
        "stream_start": "Mon, 10 Aug 2026 16:13:52 -0700",
        "stream_start_iso8601": "2026-08-10T16:13:52-0700",
        "dummy": null
      }
    ]
  },
  "disk": {
    "path": "/var/lib/allthings140radio",
    "free_bytes": 528060235776,
    "total_bytes": 1006450962432,
    "free_percent": 52.5,
    "state": "healthy"
  },
  "watchdog": {
    "state": "healthy",
    "last_check_at": 1786404892,
    "last_recovery_at": 0,
    "recovery_count": 0,
    "last_failure": ""
  },
  "silence": {
    "state": "healthy",
    "silent": false,
    "silent_seconds": 0.0,
    "last_audio_at": 1786403631,
    "error": ""
  },
  "recording": {
    "recording": false,
    "archive_id": "",
    "started_at": 0,
    "storage": "r2"
  },
  "storage": {
    "provider": "r2",
    "remote_available": true
  },
  "ads": {
    "playing": false,
    "name": ""
  },
  "online": true
}
```

## Recommended next step
Use the least disruptive recovery action; no playlist files were modified.