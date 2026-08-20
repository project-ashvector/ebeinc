#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mode="${1:-setup}"
if [[ "$mode" == "--diagnose" ]]; then exec python3 "$root/tools/allthings140-diagnose.py"; fi
dry=false; [[ "$mode" == "--dry-run" ]] && dry=true
run(){ if $dry; then echo "DRY-RUN: $*"; else "$@"; fi; }
echo "ALLTHINGS140 guided workstation setup"
source /etc/os-release 2>/dev/null || true
case "${ID:-unknown}" in ubuntu|zorin|debian|linuxmint|pop) ;; *) echo "Warning: ${ID:-unknown} is not a validated Debian-family host.";; esac
for command in git python3 curl ssh unzip; do command -v "$command" >/dev/null || { echo "Missing: $command"; exit 2; }; done
run mkdir -p "$root/dist/ALLTHINGS140" "$root/backups"
echo "Checking optional control-plane tools..."
command -v tailscale >/dev/null && tailscale status >/dev/null 2>&1 && echo "Tailscale: connected" || echo "Tailscale: login/setup required"
command -v rclone >/dev/null && echo "rclone: installed" || echo "rclone: installation required for Drive operations"
[[ -f "$root/.env" ]] || echo "Secrets: create protected runtime configuration from .env.example; never commit it"
if ! $dry; then python3 "$root/tools/allthings140-diagnose.py" || true; fi
echo "Setup check complete. Read migration/NEW-PC-SETUP.md before production changes."
