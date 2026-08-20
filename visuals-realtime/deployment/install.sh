#!/usr/bin/env bash
set -euo pipefail
[[ ${EUID:-$(id -u)} -eq 0 ]] || { echo 'Run as root on the designated realtime host.'; exit 2; }
getent passwd allthings140-visuals >/dev/null || useradd --system --home-dir /var/lib/allthings140-visuals --shell /sbin/nologin allthings140-visuals
install -d -o allthings140-visuals -g allthings140-visuals -m 0750 /opt/allthings140-visuals-realtime /var/lib/allthings140-visuals /srv/allthings140-visuals/backups
install -d -o root -g allthings140-visuals -m 0750 /etc/allthings140-visuals
echo 'Copy the reviewed release into /opt, create protected /etc/allthings140-visuals/realtime.env, install services, then enable them. This script intentionally does not overwrite an existing deployment.'
