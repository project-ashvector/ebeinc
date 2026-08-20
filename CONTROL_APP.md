# Control applications and API

The Python station server is the common control plane. DJ, Server Manager and at140radiocs should call named API operations rather than run arbitrary remote shell commands. Public Cloudflare routes expose public status, schedule, archive and stream data only. Authenticated administrative routes stay on port 14080 via Tailscale/authorized local access.

at140radiocs uses a localhost daemon on port 14200 and a machine-local bearer token. Its token is ignored by Git and EBE Dock synchronization. The current Android shell is a listener client, not an unrestricted server administration client.

Central non-secret defaults belong in a machine-specific copy derived from `config/station-config.example.json`. Secrets use protected OS configuration or a secret store and must never appear in diagnostics.
