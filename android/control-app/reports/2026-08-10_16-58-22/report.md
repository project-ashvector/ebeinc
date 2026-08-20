# at140radiocs diagnostic
Generated: 2026-08-10_16-58-22

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
    "current_track_id": 702,
    "current_title": "\ud835\udd6f\ud835\udd8a\ud835\udd9b\ud835\udd94\ud835\udd91\ud835\udd9b\ud835\udd8a - Garfield in Hell (Free Download) (Also it_s very old)",
    "current_artist": "",
    "started_at": 1786406233,
    "position_seconds": 69.90660333633423,
    "duration_seconds": 212.472,
    "next_track_id": 381,
    "next_title": "Sophie Powers & NOAHFINNCE - Clearview (Fermilat Bootleg)",
    "next_artist": "",
    "transition_reason": "automatic",
    "ad_playing": false,
    "ad_name": "",
    "progress": 0.32901560363875815
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
    "free_bytes": 527934328832,
    "total_bytes": 1006450962432,
    "free_percent": 52.5,
    "state": "healthy"
  },
  "watchdog": {
    "state": "healthy",
    "last_check_at": 1786406299,
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