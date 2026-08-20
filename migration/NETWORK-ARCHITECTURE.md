# Network architecture

Public listeners use Cloudflare Pages at `allthings140radio.online`, read no-cache state from `status.ebeinc.online`, and consume `stream.ebeinc.online/live.mp3`. Cloudflare Tunnel forwards only the listener-safe gateway/stream. Oracle runs the broadcast, encoder and state database. Ports 14080 (admin API) and 14083 (guest source) remain private and are reached only through authenticated Tailscale/control paths. Drive/rclone supplies the master library; prefetched local media keeps track changes off the critical remote-storage path.
