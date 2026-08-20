#!/usr/bin/env bash
set -u

printf 'This script performs checks only; it never contacts production.\n'
for command_name in python3 node npm git; do
  command -v "$command_name" >/dev/null 2>&1 || printf 'Missing project tool: %s\n' "$command_name"
done
if [ ! -f discord-bot/.env ]; then
  printf 'Configure discord-bot/.env locally from its safe example if that component is needed.\n'
fi
printf 'Review PROJECT_MANIFEST.md and component documentation before running anything.\n'
