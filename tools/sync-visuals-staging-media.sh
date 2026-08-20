#!/usr/bin/env bash
set -euo pipefail

# Explicitly requires an operator-provided SSH target. It never touches production.
project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source_root="${1:-$project_root/visuals-green/media}"
ssh_target="${VISUALS_MEDIA_SSH_TARGET:?Set VISUALS_MEDIA_SSH_TARGET to the staging Oracle SSH alias/user}"
remote_root="${VISUALS_MEDIA_REMOTE_ROOT:-/srv/allthings140-visuals/media}"
remote_origin="${VISUALS_MEDIA_ORIGIN:?Set VISUALS_MEDIA_ORIGIN to the HTTPS staging media origin}"

ssh "$ssh_target" "install -d -m 0755 '$remote_root/stage' '$remote_root/visuals'"
rsync -az --partial --checksum --delete "$source_root/stage/" "$ssh_target:$remote_root/stage/"
rsync -az --partial --checksum --delete "$source_root/playlist/" "$ssh_target:$remote_root/visuals/"

manifest="$project_root/visuals-green/media-manifest.json"
python3 - "$source_root" "$remote_origin" "$manifest" <<'PY'
import hashlib, json, pathlib, sys
root = pathlib.Path(sys.argv[1])
base = sys.argv[2].rstrip('/')
out = pathlib.Path(sys.argv[3])
items = {'stage': [], 'visuals': []}
for kind, folder, url_folder in [('stage', root/'stage', 'stage'), ('visuals', root/'playlist', 'visuals')]:
    for p in sorted(folder.glob('*.mp4')):
        h = hashlib.sha256(p.read_bytes()).hexdigest()
        items[kind].append({'id': p.stem, 'filename': p.name, 'url': f'{base}/{url_folder}/{p.name}', 'bytes': p.stat().st_size, 'sha256': h})
pathlib.Path(out).write_text(json.dumps(items, indent=2) + '\n')
PY
echo "Synced staging media to $ssh_target:$remote_root"
