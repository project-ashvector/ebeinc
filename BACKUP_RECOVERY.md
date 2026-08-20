# Backup and recovery

SQLite is backed up consistently every ten minutes to `/srv/allthings140radio/backups/station.db.latest`, with one daily recovery point retained for seven days. Rotation state and protected configuration should be included in pre-deployment backups. Google Drive is the audio master; the local Oracle library is the operational outage fallback, not disposable duplication.

Recovery order for a replacement Oracle host: provision the station account and storage, restore protected configuration separately, restore the latest validated SQLite backup, restore/install the known-good server and service files, synchronize or mount audio, validate catalog paths, start Icecast, start the station server, start the tunnel, then run internal and public health checks. Do not switch DNS/tunnel traffic until audio and metadata advance.

Daily off-host backups use AES-256-CBC with PBKDF2, upload only encrypted archives to `BACKUPS/ENCRYPTED`, retain 35 days, and write a machine-readable status file. The decryption key is separately protected on Oracle and this authorized workstation. The first upload passed encryption, decryption, tar extraction and SQLite `quick_check` restore testing.

If a laptop fails, another authorized Tailscale PC can use the canonical project and private control API. If Drive disconnects, continue from local fallback while repairing Drive. If the server app crashes, systemd restarts it; internal watchdog and silence monitoring handle common media failures. Roll back code by restoring the timestamped pre-deployment file and restarting only the affected service.

## Catalog-integrity recovery set

Before catalog recovery or cleanup, create a root-only timestamped directory under
`/srv/allthings140radio/backups/catalog-incident-<UTC timestamp>/`. Use SQLite's
online backup API, not a raw live-database copy. Include the database and table
counts, rotation/cache state, deployed source, effective systemd units, protected
configuration, audit/event logs, storage inventories, current trash, quarantine
manifests and recent immutable database recovery points. Generate SHA-256 checksums
and verify every entry plus `PRAGMA quick_check` before changing catalog or audio.

Reports and distributable migration archives must exclude rclone credentials,
tokens, passwords, private keys, support environment files and backup encryption
keys. The protected Oracle recovery directory may retain those files at mode 0700;
never copy them into Git or a report.

Catalog rows and audio assets are separate objects. Restore a catalog reference or
quarantined asset from its operation manifest; never infer that deleting a row
authorizes deleting audio. Preserve `catalog_operations`,
`catalog_operation_items`, `quarantine_assets`, integrity reports and playback
admission ledgers in future backups.
