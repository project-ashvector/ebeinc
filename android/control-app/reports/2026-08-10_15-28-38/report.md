# at140radiocs diagnostic
Generated: 2026-08-10_15-28-38

## Summary
- Tailscale: DISCONNECTED
- Radio online: unknown

## Relevant status
```json
{
  "ok": true,
  "name": "AllThings140Radio",
  "version": "0.6.0",
  "autodj": {
    "running": true,
    "pid": 796606,
    "mode": "catalog rotation",
    "last_error": "",
    "tracks": 444,
    "current_track_id": 547,
    "current_title": "Artix & Monsuo - Doppelgagner [Free Download]",
    "current_artist": "",
    "started_at": 1786400762,
    "position_seconds": 156.78819060325623,
    "duration_seconds": 219.794286,
    "next_track_id": 627,
    "next_title": "Subfiltronik - Blockz (Batikz Bootleg) [Riddim Dubstep Exclusive - Free Download]",
    "next_artist": "",
    "transition_reason": "automatic",
    "ad_playing": false,
    "ad_name": "",
    "progress": 0.7133406125182719
  },
  "icecast": {
    "online": true,
    "listeners": 2,
    "live_source": true,
    "sources": [
      {
        "genre": "various",
        "listener_peak": 2,
        "listeners": 2,
        "listenurl": "http://localhost:14000/live.mp3",
        "server_description": "140 BPM and bass music, live around the clock.",
        "server_name": "AllThings140Radio",
        "server_type": "audio/mpeg",
        "stream_start": "Mon, 10 Aug 2026 15:17:15 -0700",
        "stream_start_iso8601": "2026-08-10T15:17:15-0700",
        "dummy": null
      }
    ]
  },
  "disk": {
    "path": "/var/lib/allthings140radio",
    "free_bytes": 529100816384,
    "total_bytes": 1006450962432,
    "free_percent": 52.6,
    "state": "healthy"
  },
  "watchdog": {
    "state": "healthy",
    "last_check_at": 1786400914,
    "last_recovery_at": 0,
    "recovery_count": 0,
    "last_failure": ""
  },
  "silence": {
    "state": "healthy",
    "silent": false,
    "silent_seconds": 0.0,
    "last_audio_at": 1786342149,
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
  }
}
```

## Recommended next step
Use the least disruptive recovery action; no playlist files were modified.