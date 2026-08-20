# Google Drive and ingestion

The dedicated Drive remote currently contains 490 audio files (310 MP3 and 180 WAV), all at the Drive root. rclone mounts it read/write with polling every minute and no VFS cache. The Oracle fallback library remains essential because playback from the primary mount can stall during Drive/network trouble.

Do not reorganize the live Drive root until catalog path migration is implemented and tested. New ingestion should use a staging prefix or directory, validate a completed file with ffprobe, calculate SHA-256, extract normalized metadata, then atomically admit it to the library and catalog. Partial files must never become approved tracks. Unsupported/corrupt files belong in quarantine, not deletion.

Production staging directories now exist under `/srv/allthings140radio/ingest/`. `audio_ingest.py` verifies stable file size/mtime, supported format, ffprobe decode, duration, metadata and SHA-256 before copying through a `.partial` file and atomically renaming into READY. It creates an unapproved review entry; no staged file enters rotation automatically.

Persistent `audio_assets` and `ingest_events` tables record hashes and duplicate relationships. The one-time backfill indexed 486 unique assets and recorded one content duplicate without deleting either catalog record. Drive remains flat for legacy compatibility; migration still requires dry-run path mapping before any moves.

Credentials are stored only in `/etc/allthings140radio/rclone.conf` with restrictive permissions. Never copy that file into Git, EBE Dock shares, reports, or diagnostics.
