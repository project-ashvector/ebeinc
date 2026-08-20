#!/usr/bin/bash
set -euo pipefail

ssh_command="ssh -i /home/ebmarah/.ssh/allthings140radio_oracle_ed25519 -o BatchMode=yes -o ConnectTimeout=15 -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile=/etc/allthings140radio/oracle-known-hosts"
remote="opc@64.181.235.228"
local_data="/var/lib/allthings140radio"

mkdir -p "$local_data/backups"

rsync -aH --partial --chown=allthings140radio:allthings140radio \
  --include='/music/***' \
  --include='/ads/***' \
  --include='/voices/***' \
  --include='/personas/***' \
  --include='/takeover-logos/***' \
  --exclude='*' \
  --rsync-path='sudo rsync' \
  -e "$ssh_command" \
  "$remote:/srv/allthings140radio/data/" "$local_data/"

rsync -a --chown=allthings140radio:allthings140radio \
  --rsync-path='sudo rsync' \
  -e "$ssh_command" \
  "$remote:/srv/allthings140radio/backups/station.db.latest" \
  "$local_data/backups/cloud-primary.db"
