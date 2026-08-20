#!/usr/bin/bash
set -u

failed=0
for service in allthings140radio-icecast.service allthings140radio-server.service; do
  if ! systemctl is-active --quiet "$service"; then
    systemctl restart "$service"
    failed=1
  fi
done

if ! curl --fail --silent --max-time 8 http://127.0.0.1:14080/api/health >/dev/null; then
  systemctl restart allthings140radio-server.service
  failed=1
fi

exit "$failed"
