# Google Drive master + Oracle hot cache

Google Drive remains the authoritative, scalable music library. Oracle keeps a
bounded disposable cache at `/srv/allthings140radio/cache/READY`, with partial
downloads isolated under `TEMP/`. `cache_manager.py` plans from the persisted
rotation order, validates files with `ffprobe` and the catalog SHA-256, then
publishes each file with an atomic rename. The cache service runs at low I/O
priority and never owns the encoder.

The server resolves a cache path first and uses the local emergency library
only when a planned cache item is not ready. It never needs a live Drive read
for a cached track. The current cache policy is 50 tracks / approximately 120
minutes target, 45-minute safety floor, 5 GB maximum, and 12% protected free
disk. `cache-state.json` and `cache-index.json` are operational state only;
Drive originals are never removed by cache eviction.

Useful commands:

```bash
allthings140 cache status
allthings140 cache health
sudo systemctl status allthings140radio-cache
```

The cache service can be disabled for rollback while retaining the original
local emergency library, but playback should remain local rather than using a
network-mounted Drive path during normal operation.

Approved Drive uploads must also be admitted to the local emergency playback
mirror. `allthings140radio-playback-admission.timer` runs the bounded rclone-based
admission utility every 30 minutes. It copies only approved/enabled/rights-cleared
files missing locally, validates duration and SHA-256 through a temporary file,
then publishes atomically without overwriting an existing target. Its JSON ledger
is stored under `/srv/allthings140radio/data/recovery/`.

Integrity reporting distinguishes `stored_audio` from `playback_ready`. A Drive
master absent from the emergency mirror/cache is `STORED_NOT_PLAYBACK_READY`, not
`MISSING_AUDIO`. This distinction prevents a cache-admission backlog from being
misreported as lost music.
