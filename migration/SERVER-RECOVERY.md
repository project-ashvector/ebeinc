# Oracle server recovery

Provision a supported Linux host, create dedicated service/state/cache paths, install Icecast/FFmpeg/Python/rclone/cloudflared, restore protected config separately, restore and quick-check the latest `station.db`, restore rotation/ad state, mount Drive, seed the hot cache, install systemd units, and start dependencies before the station server. Validate loopback audio, public audio, generation/sequence advancement and metadata before changing the Tunnel route. Roll back DNS/Tunnel immediately if smoke checks fail.
