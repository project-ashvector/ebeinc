#!/usr/bin/env bash
set -euo pipefail

if [[ ${EUID} -ne 0 ]]; then
  echo "Run as root on the Oracle radio server." >&2
  exit 2
fi

stamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup_root="/etc/allthings140radio/rollback-${stamp}"
install -d -m 0700 "$backup_root"
cp -a /etc/allthings140radio/icecast.xml "$backup_root/icecast.xml"
cp -a /etc/allthings140radio/config.json "$backup_root/config.json"
cp -a /opt/allthings140radio-server/server.py "$backup_root/server.py"
cp -a /etc/systemd/system/allthings140radio-server.service "$backup_root/allthings140radio-server.service"

rollback() {
  cp -a "$backup_root/icecast.xml" /etc/allthings140radio/icecast.xml
  cp -a "$backup_root/config.json" /etc/allthings140radio/config.json
  cp -a "$backup_root/server.py" /opt/allthings140radio-server/server.py
  cp -a "$backup_root/allthings140radio-server.service" /etc/systemd/system/allthings140radio-server.service
  systemctl daemon-reload
  systemctl restart allthings140radio-icecast.service
  systemctl stop allthings140radio-icecast-auth-relay.service 2>/dev/null || true
  systemctl restart allthings140radio-server.service
}
trap 'status=$?; if [[ $status -ne 0 ]]; then rollback; fi; rm -f /run/at140-source.new /run/at140-admin.new /run/at140-relay.new; exit $status' EXIT

python3 -m py_compile /tmp/server.py /tmp/icecast_auth_relay.py
takeover="$(curl -fsS http://127.0.0.1:14080/api/public/status | python3 -c 'import json,sys; d=json.load(sys.stdin); print(1 if d.get("live") or d.get("takeover_active") or d.get("mode") in ("live","takeover") else 0)')"
[[ "$takeover" == 0 ]] || { echo "Active takeover; deployment aborted." >&2; exit 3; }

umask 077
openssl rand -hex 32 > /run/at140-source.new
openssl rand -hex 32 > /run/at140-admin.new
openssl rand -hex 32 > /run/at140-relay.new

python3 - <<'PY'
import json
import xml.etree.ElementTree as ET
from pathlib import Path

source = Path('/run/at140-source.new').read_text().strip()
admin = Path('/run/at140-admin.new').read_text().strip()
relay = Path('/run/at140-relay.new').read_text().strip()
xml_path = Path('/etc/allthings140radio/icecast.xml')
tree = ET.parse(xml_path)
root = tree.getroot()
root.find('./authentication/source-password').text = source
root.find('./authentication/relay-password').text = relay
root.find('./authentication/admin-password').text = admin
source_timeout = root.find('./limits/source-timeout')
if source_timeout is not None:
    source_timeout.text = '60'
tree.write(xml_path, encoding='unicode')

config_path = Path('/etc/allthings140radio/config.json')
config = json.loads(config_path.read_text())
config['source_password'] = 'local-relay'
config['icecast_encoder_port'] = 14001
config_path.write_text(json.dumps(config, indent=2) + '\n')
PY

install -o allthings140radio -g allthings140radio -m 0600 /run/at140-source.new /etc/allthings140radio/icecast-source.secret
chown root:allthings140radio /etc/allthings140radio/icecast.xml
chmod 0640 /etc/allthings140radio/icecast.xml
chown allthings140radio:allthings140radio /etc/allthings140radio/config.json
chmod 0600 /etc/allthings140radio/config.json
install -o allthings140radio -g allthings140radio -m 0755 /tmp/server.py /opt/allthings140radio-server/server.py
install -o allthings140radio -g allthings140radio -m 0755 /tmp/icecast_auth_relay.py /opt/allthings140radio-server/icecast_auth_relay.py
install -o root -g root -m 0644 /tmp/allthings140radio-icecast-auth-relay.service /etc/systemd/system/allthings140radio-icecast-auth-relay.service
install -o root -g root -m 0644 /tmp/allthings140radio-server.service /etc/systemd/system/allthings140radio-server.service
systemctl daemon-reload
systemctl enable allthings140radio-icecast-auth-relay.service >/dev/null

systemctl stop allthings140radio-server.service
systemctl restart allthings140radio-icecast.service
systemctl restart allthings140radio-icecast-auth-relay.service
systemctl start allthings140radio-server.service

for _ in {1..20}; do
  if curl -fsS --max-time 4 http://127.0.0.1:14080/api/health >/dev/null; then break; fi
  sleep 2
done
curl -fsS --max-time 5 http://127.0.0.1:14080/api/health >/dev/null
systemctl is-active --quiet allthings140radio-server.service
systemctl is-active --quiet allthings140radio-icecast.service
systemctl is-active --quiet allthings140radio-icecast-auth-relay.service

encoder_pid="$(pgrep -P "$(systemctl show -p MainPID --value allthings140radio-server.service)" ffmpeg | head -1)"
[[ -n "$encoder_pid" ]]
if tr '\0' '\n' < "/proc/${encoder_pid}/cmdline" | grep -F -q -f /etc/allthings140radio/icecast-source.secret; then
  echo "Credential remains visible in encoder arguments." >&2
  exit 4
fi

trap - EXIT
rm -f /run/at140-source.new /run/at140-admin.new /run/at140-relay.new
echo "Secure Icecast credential rotation completed; rollback: $backup_root"
