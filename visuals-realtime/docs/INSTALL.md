# Install

Use a dedicated supported Linux host after verifying its identity and taking a pre-change backup. Create the locked service account `allthings140-visuals`, install Python 3.12/venv, copy the app to `/opt/allthings140-visuals-realtime`, create its venv from `requirements.txt`, place secrets in root-owned `/etc/allthings140-visuals/realtime.env`, install the systemd units, and expose loopback port 14140 through the existing TLS/Cloudflare Tunnel design. Do not open the backend port directly. Verify `/health`, origin rejection, WSS and backups before enabling staging traffic.
