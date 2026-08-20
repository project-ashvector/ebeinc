# Restore

Stop only the realtime service, create a fresh backup, run `scripts/restore.py ARCHIVE --output /tmp/realtime.db`, inspect its successful checksum/SQLite result, atomically install it with service ownership, restart the realtime service, and test health/WebSocket chat/reaction/energy. This never requires touching the radio server.
