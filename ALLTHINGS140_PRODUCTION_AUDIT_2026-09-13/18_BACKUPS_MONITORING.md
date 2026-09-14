# Backups & Monitoring

## Oracle timers

| Timer | Purpose | Evidence |
|-------|---------|----------|
| healthcheck | ~1 min service probe | active |
| backup | local DB snapshot | `station.db.latest` 2026-09-14 04:58 |
| playback-admission | catalog admission | active |
| offhost-backup | encrypted daily tarball | `allthings140-state-20260914T042935Z.tar.gz.enc` |

## GCP visuals

- Daily state backup timer referenced in prior docs; not re-verified this session

## Monitoring

- Discord webhook failure notifier in server.py
- ffmpeg silence detector process running
- No external APM observed

## Restore testing

**NOT TESTED** — backup files exist; restore drill not performed (per safety rules).

**Status: PASS WITH WARNINGS**
