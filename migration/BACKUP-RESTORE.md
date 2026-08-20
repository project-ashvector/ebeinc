# Backup restore

- Migration ZIP: source/config templates/tooling only; verify its `.sha256`, extract, and follow START-HERE.
- Local operational backup: restore files to an isolated directory first and compare its manifest.
- Oracle database: stop the server only for the final atomic swap, copy `station.db.latest`, run SQLite `quick_check`, preserve ownership, then restart and smoke-test.
- Encrypted Drive backup: download one `.enc`, decrypt with the separately held key using AES-256-CBC/PBKDF2, extract in isolation, validate manifest hashes and SQLite, then restore.

Never restore over a live database without a fresh pre-restore backup.

Migration and incident backups must retain catalog integrity state, audio hashes,
playback-admission ledgers, durable catalog operation tables, audit history and
quarantine manifests. Keep protected credentials only in the encrypted/root-only
backup tier; exclude them from portable ZIPs and reports. Validate SQLite with
`PRAGMA quick_check` and verify the checksum manifest before restoration.
