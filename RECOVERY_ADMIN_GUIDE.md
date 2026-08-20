# Recovery and administration quick guide

1. Connect the workstation to Tailscale and run `tailscale ping allthings140radio-server`.
2. Run `allthings140 status`, `allthings140 now-playing`, or `allthings140 diagnose`.
3. Open EBE Dock AI → ALLTHINGS140 RADIO for the station dashboard.
4. Use the authenticated DJ application for playlist refresh, Drive/catalog admission, AutoDJ controls, ads and takeovers.
5. On Oracle, inspect `systemctl status allthings140radio-{server,icecast,icecast-auth-relay,drive,tunnel}` and `journalctl -u allthings140radio-server.service`.
6. Restore SQLite only after stopping the station server: copy a validated backup to a temporary path, run `PRAGMA quick_check`, preserve the current DB, then atomically install the restored DB with station ownership.
7. Restore protected configuration from the encrypted off-host archive using the separately stored key. Never copy credentials into Git or chat.
8. For Oracle replacement, follow `BACKUP_RECOVERY.md`: provision storage/account, restore protected config and DB, mount/sync audio, start Icecast/relay/server/tunnel, then validate local and public health before traffic cutover.
9. If EBE Dock loses Oracle, verify Tailscale/MagicDNS first; the station continues independently of EBE Dock.
