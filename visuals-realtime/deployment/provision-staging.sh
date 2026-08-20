#!/usr/bin/env bash
set -euo pipefail

[[ ${EUID:-$(id -u)} -eq 0 ]] || { echo 'Run as root on the designated staging host.'; exit 2; }
[[ -f /tmp/allthings140-visuals-realtime-release.tgz ]] || { echo 'Release archive missing.'; exit 2; }
[[ -f /tmp/tunnel-credentials.json ]] || { echo 'Tunnel credentials missing.'; exit 2; }
[[ -x /tmp/cloudflared ]] || { echo 'cloudflared binary missing.'; exit 2; }

getent passwd allthings140-visuals >/dev/null || useradd --system --home-dir /var/lib/allthings140-visuals --shell /sbin/nologin allthings140-visuals
install -d -o allthings140-visuals -g allthings140-visuals -m 0750 /opt/allthings140-visuals-realtime /var/lib/allthings140-visuals /srv/allthings140-visuals/backups
install -d -o root -g allthings140-visuals -m 0750 /etc/allthings140-visuals
install -d -o root -g root -m 0755 /etc/cloudflared

tar -xzf /tmp/allthings140-visuals-realtime-release.tgz -C /opt/allthings140-visuals-realtime
chown -R allthings140-visuals:allthings140-visuals /opt/allthings140-visuals-realtime
python3 -m venv /opt/allthings140-visuals-realtime/.venv
/opt/allthings140-visuals-realtime/.venv/bin/pip install --disable-pip-version-check --no-cache-dir -r /opt/allthings140-visuals-realtime/requirements.txt

admin_token="$(openssl rand -hex 32)"
install -o root -g allthings140-visuals -m 0640 /dev/null /etc/allthings140-visuals/realtime.env
{
  echo 'ENVIRONMENT=staging'
  echo 'REALTIME_HOST=127.0.0.1'
  echo 'REALTIME_PORT=8765'
  echo 'REALTIME_PUBLIC_URL=https://visuals-realtime-staging.allthings140radio.online'
  echo 'DATABASE_PATH=/var/lib/allthings140-visuals/realtime.db'
  echo 'BACKUP_PATH=/srv/allthings140-visuals/backups'
  echo 'ALLOWED_ORIGINS=https://allthings140-visuals-green.pages.dev,http://127.0.0.1:14141'
  echo "ADMIN_TOKEN=${admin_token}"
  echo 'CHAT_HISTORY_LIMIT=30'
  echo 'MAX_CONNECTIONS=500'
} >/etc/allthings140-visuals/realtime.env
unset admin_token

install -o root -g root -m 0755 /tmp/cloudflared /usr/local/bin/cloudflared
install -o root -g root -m 0600 /tmp/tunnel-credentials.json /etc/cloudflared/tunnel-credentials.json
install -o root -g root -m 0644 /dev/null /etc/cloudflared/config.yml
{
  echo 'tunnel: b64f426e-d98b-41af-9362-0b4e0180d463'
  echo 'credentials-file: /etc/cloudflared/tunnel-credentials.json'
  echo 'ingress:'
  echo '  - hostname: visuals-realtime-staging.allthings140radio.online'
  echo '    service: http://127.0.0.1:8765'
  echo '  - service: http_status:404'
} >/etc/cloudflared/config.yml

install -o root -g root -m 0644 /opt/allthings140-visuals-realtime/services/allthings140-visuals-realtime.service /etc/systemd/system/
install -o root -g root -m 0644 /opt/allthings140-visuals-realtime/services/allthings140-visuals-backup.service /etc/systemd/system/
install -o root -g root -m 0644 /opt/allthings140-visuals-realtime/services/allthings140-visuals-backup.timer /etc/systemd/system/
install -o root -g root -m 0644 /opt/allthings140-visuals-realtime/services/allthings140-visuals-tunnel.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now allthings140-visuals-realtime.service
systemctl enable --now allthings140-visuals-backup.timer
systemctl enable --now allthings140-visuals-tunnel.service

rm -f /tmp/tunnel-credentials.json /tmp/allthings140-visuals-realtime-release.tgz /tmp/cloudflared
echo 'Staging gateway provisioned. Protected tokens were not displayed.'
