# at140radiocs diagnostic
Generated: 2026-08-10_16-45-19

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
    "pid": 852468,
    "mode": "catalog rotation",
    "last_error": "",
    "tracks": 444,
    "current_track_id": 387,
    "current_title": "Crankdat - STFU (Loud Mix)",
    "current_artist": "",
    "started_at": 1786405438,
    "position_seconds": 81.15210890769958,
    "duration_seconds": 156.562517,
    "next_track_id": 533,
    "next_title": "Saunter & Stayns - Catch!!! [Forthcoming - Warriors Free EP]",
    "next_artist": "",
    "transition_reason": "automatic",
    "ad_playing": false,
    "ad_name": "",
    "progress": 0.5183367670800769
  },
  "icecast": {
    "online": true,
    "listeners": 2,
    "live_source": true,
    "sources": [
      {
        "genre": "various",
        "listener_peak": 3,
        "listeners": 2,
        "listenurl": "http://localhost:14000/live.mp3",
        "server_description": "140 BPM and bass music, live around the clock.",
        "server_name": "AllThings140Radio",
        "server_type": "audio/mpeg",
        "stream_start": "Mon, 10 Aug 2026 16:36:09 -0700",
        "stream_start_iso8601": "2026-08-10T16:36:09-0700",
        "dummy": null
      }
    ]
  },
  "disk": {
    "path": "/var/lib/allthings140radio",
    "free_bytes": 527999131648,
    "total_bytes": 1006450962432,
    "free_percent": 52.5,
    "state": "healthy"
  },
  "watchdog": {
    "state": "healthy",
    "last_check_at": 1786405518,
    "last_recovery_at": 0,
    "recovery_count": 0,
    "last_failure": ""
  },
  "silence": {
    "state": "healthy",
    "silent": false,
    "silent_seconds": 0.0,
    "last_audio_at": 1786404968,
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