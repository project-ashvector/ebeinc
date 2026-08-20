#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source_root="${1:-/home/ebmarah/Videos/at140radio/desktop visuals}"
output_root="$project_root/visuals-green/media"
playlist_dir="$output_root/playlist"
manifest="$project_root/visuals-green/playlist.json"

command -v ffmpeg >/dev/null
command -v ffprobe >/dev/null
test -r "$source_root/stage/alpha.mov"
test -d "$source_root/visuals"
mkdir -p "$output_root/stage" "$playlist_dir"

ffmpeg -nostdin -hide_banner -loglevel error -i "$source_root/stage/alpha.mov" -an \
  -vf 'scale=1280:-2:flags=lanczos,fps=30' -c:v libx264 -preset medium -crf 26 \
  -pix_fmt yuv420p -movflags +faststart -y "$output_root/stage/stage-overlay.mp4"

manifest_tmp="$manifest.tmp"
printf '[\n' > "$manifest_tmp"
item_number=0
while IFS= read -r -d '' source_file; do
  item_number=$((item_number + 1))
  item_id="visual-$(printf '%03d' "$item_number")"
  output_file="$playlist_dir/$item_id.mp4"
  ffmpeg -nostdin -hide_banner -loglevel error -i "$source_file" -an \
    -vf 'scale=1280:-2:flags=lanczos,fps=24' -c:v libx264 -preset medium -crf 28 \
    -pix_fmt yuv420p -movflags +faststart -y "$output_file"
  test "$(stat -c %s "$output_file")" -lt 25000000
  if (( item_number > 1 )); then printf ',\n' >> "$manifest_tmp"; fi
  source_name="$(basename "$source_file")"
  printf '  {"id":"%s","url":"/media/playlist/%s.mp4","fit":"cover","source":"%s"}' \
    "$item_id" "$item_id" "${source_name//\"/\\\"}" >> "$manifest_tmp"
done < <(find "$source_root/visuals" -maxdepth 1 -type f -iname '*.mp4' -print0 | sort -z)
printf '\n]\n' >> "$manifest_tmp"
mv "$manifest_tmp" "$manifest"
printf 'Prepared %d playlist visuals plus stage overlay.\n' "$item_number"
