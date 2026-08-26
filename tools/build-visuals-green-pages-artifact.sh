#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source_root="$project_root/visuals-green"
derivative_root="${AT140_VISUALS_DERIVATIVES:-/home/ebmarah/Videos/at140radio/desktop visuals/generated/web-v1}"
output_root="${1:?Usage: build-visuals-green-pages-artifact.sh NEW_OUTPUT_DIRECTORY}"

if [[ -e "$output_root" ]]; then
  printf 'Refusing to overwrite existing artifact: %s\n' "$output_root" >&2
  exit 2
fi

mkdir -p "$output_root/media/visuals" "$output_root/media/stage"
for file in _headers config.js index.html layout.json overlay.css playlist.json robots.txt stage.css stage.js; do
  cp "$source_root/$file" "$output_root/$file"
done

while IFS= read -r asset_id; do
  source_file="$derivative_root/$asset_id.mp4"
  [[ -s "$source_file" ]] || { printf 'Missing derivative: %s\n' "$source_file" >&2; exit 3; }
  cp "$source_file" "$output_root/media/visuals/$asset_id.mp4"
done < <(jq -r '.playlist[] | select(.enabled != false) | .id' "$source_root/layout.json")

stage_id="$(jq -r '.layers[] | select(.id == "stage-content") | .media.id' "$source_root/layout.json")"
cp "$derivative_root/$stage_id.mp4" "$output_root/media/stage/$stage_id.mp4"
cp "$derivative_root/manifest.json" "$output_root/media/manifest.json"

count="$(find "$output_root/media/visuals" -maxdepth 1 -type f -name '*.mp4' | wc -l)"
expected="$(jq '[.playlist[] | select(.enabled != false)] | length' "$source_root/layout.json")"
[[ "$count" == "$expected" ]] || { printf 'Artifact count mismatch: %s != %s\n' "$count" "$expected" >&2; exit 4; }

largest="$(find "$output_root/media" -type f -name '*.mp4' -printf '%s\n' | sort -nr | head -1)"
[[ "$largest" -lt 25000000 ]] || { printf 'Artifact has a media file at or above 25 MB: %s bytes\n' "$largest" >&2; exit 5; }

printf 'Green artifact ready: %s visuals, largest media %s bytes, path %s\n' "$count" "$largest" "$output_root"
