#!/bin/sh
set -eu
DEST=/home/ebmarah/rotation-audit
mkdir -p "$DEST"
sudo cp /var/lib/allthings140radio/station.db "$DEST/station.db"
sudo cp /var/lib/allthings140radio/rotation-state.json "$DEST/rotation-state.json"
sudo cp /var/lib/allthings140radio/events.jsonl "$DEST/events.jsonl"
sudo chown -R ebmarah:ebmarah "$DEST"
echo
echo "Read-only rotation audit snapshot exported successfully."
read -r -p "Press Enter to close..." _answer
