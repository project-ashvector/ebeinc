# Oracle server operations

Host: `allthings140radio-server` on the private tailnet. Use the existing authorized SSH configuration; do not publish credentials or control endpoints.

Critical services include the server, Icecast, loopback authentication relay, Drive and tunnel. The stateful supervisor records consecutive failures and uses exponential restart backoff after three failures. SQLite backups run every ten minutes; encrypted off-host backups run daily and perform a decrypt/restore integrity test before upload.

Read-only checks:

```bash
systemctl status allthings140radio-{server,icecast,drive,tunnel}.service
systemctl list-timers --all | grep allthings140radio
curl -fsS http://127.0.0.1:14080/api/health | jq
journalctl -u allthings140radio-server.service --since today
journalctl -u allthings140radio-tunnel.service --since today
df -h / /srv/allthings140radio
free -h
```

`/api/public/status` is read-only and must never call AutoDJ controls. Check
`station_generation_id`, `station_sequence`, `server_time`, `started_at`, and
`stream_status` when diagnosing stale clients. Cloudflared messages saying a
stream was canceled by the remote usually represent a listener/browser closing
its HTTP stream; correlate repeated short sessions with client diagnostics.

Before deployment: confirm no live takeover, create a timestamped source backup, validate Python syntax, install only the intended file, restart only the affected service, then verify local health and the public stream. Keep the timestamped file for rollback.

SSH access is allowed persistently on the dedicated `at140tail` firewalld zone.
Both `sshd` and `tailscaled` must remain enabled. Verify with tailnet SSH; do not
expose the private control API or replace this with a public control route.

Legacy `/api/tracks/prune` and `/api/tracks/<id>/delete` are disabled. Reviewed
catalog unlinking uses a durable operation ID and preserves physical audio.
Physical isolation is a separate admin-only quarantine operation with a checksum
manifest and restore endpoint. A timeout is resolved by querying
`GET /api/catalog-operations/<operation-id>` rather than retrying an ambiguous
destructive request.
