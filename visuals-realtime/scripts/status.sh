#!/usr/bin/env bash
set -euo pipefail
health_url="${REALTIME_HEALTH_URL:-http://${REALTIME_HOST:-127.0.0.1}:${REALTIME_PORT:-14140}/health}"
curl -fsS "$health_url"
printf '\nBACKUP\n'
status="${BACKUP_PATH:-/srv/allthings140-visuals/backups}/backup-status.json"
if [[ -r "$status" ]]; then python3 -m json.tool "$status"; else echo "LAST BACKUP: MISSING"; exit 2; fi
