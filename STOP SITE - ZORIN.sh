#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
STATE_FILE=".bitbyt3s-server.json"

if [[ ! -f "$STATE_FILE" ]]; then
  echo "No BitByt3s server state file was found. The site may already be stopped."
  exit 0
fi

PID="$(python3 - <<'PY'
import json
from pathlib import Path
try:
    print(json.loads(Path('.bitbyt3s-server.json').read_text())['pid'])
except Exception:
    print('')
PY
)"

if [[ -z "$PID" ]]; then
  echo "The saved server state is invalid."
  rm -f "$STATE_FILE"
  exit 1
fi

if kill -0 "$PID" 2>/dev/null; then
  CMD="$(tr '\0' ' ' < "/proc/$PID/cmdline" 2>/dev/null || true)"
  if [[ "$CMD" == *"LAN SERVER.py"* ]]; then
    kill "$PID"
    echo "Stopped BitByt3s portfolio server (PID $PID)."
  else
    echo "PID $PID is not the BitByt3s server; it was not stopped."
    exit 1
  fi
else
  echo "The saved server process is no longer running."
fi
rm -f "$STATE_FILE"
