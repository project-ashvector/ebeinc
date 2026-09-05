# ALLTHINGS140 database reconciliation

Audit date: 2026-09-04/05. Inspection was read-only. No database was overwritten, merged, or deleted.

## Decision

- **PRIMARY_LIVE:** Oracle `/var/lib/allthings140radio/station.db`
- **BACKUP (logically exact at capture):** `~/uptodate projects/ALLTHINGS140 Radio/migration-data/cloud-primary.db`
- **ARCHIVED_HISTORY:** `~/uptodate projects/ALLTHINGS140 Radio/migration-data/station.db`
- Database merge required: **NO**
- Database deletion authorized/performed: **NO**

## Runtime proof

`allthings140radio-server.service` runs `/opt/allthings140radio-server/server.py` with working directory `/var/lib/allthings140radio`. Source defaults and service deployment resolve `ALLTHINGS140_DB_PATH` to `/var/lib/allthings140radio/station.db`. The service is active and the public status API reports server 0.8.0 online. This is stronger evidence than local filenames or modification times.

## Comparison

| Property | Historical local `station.db` | Retained `cloud-primary.db` | Oracle live DB |
|---|---:|---:|---:|
| Size | 344,064 bytes | 2,240,512 bytes | 2,240,512 bytes at capture |
| SQLite integrity | ok | ok | ok |
| `user_version` | 0 | 0 | 0 |
| Tables | 11 | 22 | 22 |
| Tracks | 446 | 2,464 | 2,464 |
| Audio assets | table absent | 2,359 | 2,359 |
| Ingest events | table absent | 1,874 | 1,874 |
| Upload receipts | table absent | 2,040 | 2,040 |
| Audit rows | 1,557 | 3,652 | 3,652 |
| Sessions | 79 | 103 | 103 |
| Users | 2 | 2 | 2 |

The retained `cloud-primary.db` and Oracle live DB produced identical SHA-256 fingerprints for every table schema and every sorted logical row. Their raw database-file SHA-256 values differ because SQLite page/layout metadata can differ without logical content differences. Logical comparison is authoritative here.

The smaller historical DB lacks eleven current tables, including `audio_assets`, `ingest_events`, `upload_receipts`, catalog-operation tables, and billing/support tables. It also has fewer catalog and audit records. It contains no evidence requiring a merge into production. Preserve it as historical rollback evidence until final acceptance.

## Visuals state database

The separate Visuals host uses `/var/lib/allthings140-visuals/realtime.db` in WAL mode. Read-only integrity passed. At capture it contained `messages` (3 rows), `schedules` (1), and `stats` (6). This is a distinct realtime/community state database and must not be confused or merged with the station database. The remote backup timer is active.

## Safe future handling

Any new station snapshot must use SQLite's backup API or the existing `tools/backup_radio.py`/off-host backup mechanism. Do not copy a live WAL database casually. Keep the smaller historical database classified `ARCHIVED_HISTORY`; it is retireable from the canonical migration set only after user acceptance, but it must not be deleted by this audit.
