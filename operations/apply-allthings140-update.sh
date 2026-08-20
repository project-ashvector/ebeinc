#!/bin/sh
set -eu
SOURCE=/home/ebmarah/ebeinc-cloudflare-migration
sudo cp "$SOURCE/tools/server.py" /opt/allthings140radio-server/server.py
sudo cp "$SOURCE/tools/dj_app.py" /opt/allthings140radio-dj/dj_app.py
sudo systemctl restart allthings140radio-server.service
echo
echo "AllThings140Radio server and DJ app updated successfully."
echo "Close and reopen the DJ app to load the new scheduler."
read -r -p "Press Enter to close..." _answer
