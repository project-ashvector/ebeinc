#!/usr/bin/env bash
set -euo pipefail

state_file="${AT140_VISUALS_STATE:-/home/ebmarah/.local/share/allthings140radio-visuals/workstation.json}"
output_dir="${AT140_VISUALS_DERIVATIVES:-/home/ebmarah/Videos/at140radio/desktop visuals/generated/web-v1}"
manifest="$output_dir/manifest.jsonl"

mkdir -p "$output_dir"
: > "$manifest.tmp"

jq -r '.playlist[] | select(.enabled != false) | [.id, .sourcePath, .name] | @tsv' "$state_file" |
while IFS=$'\t' read -r asset_id source_path source_name; do
  destination="$output_dir/$asset_id.mp4"

  if [[ ! -s "$destination" ]]; then
    ffmpeg -nostdin -y -hide_banner -loglevel error -i "$source_path" \
      -map 0:v:0 -an \
      -vf 'scale=1280:-2:flags=lanczos,fps=30' \
      -c:v libx264 -preset veryfast -crf 24 -pix_fmt yuv420p \
      -movflags +faststart "$destination"
  fi

  probe="$(ffprobe -v error \
    -show_entries stream=codec_name,width,height,r_frame_rate,pix_fmt:format=duration,size,bit_rate \
    -of json "$destination")"
  source_size="$(stat -c '%s' "$source_path")"
  sha256="$(sha256sum "$destination" | awk '{print $1}')"
  jq -cn \
    --arg id "$asset_id" \
    --arg source "$source_path" \
    --arg name "$source_name" \
    --arg output "$destination" \
    --arg sha256 "$sha256" \
    --argjson sourceSize "$source_size" \
    --argjson probe "$probe" \
    '{id:$id,name:$name,source:$source,output:$output,sourceSize:$sourceSize,sha256:$sha256,probe:$probe}' \
    >> "$manifest.tmp"
done

mv "$manifest.tmp" "$manifest"
jq -s '{version:1,generatedAt:(now|todate),count:length,totalBytes:(map(.probe.format.size|tonumber)|add),items:.}' \
  "$manifest" > "$output_dir/manifest.json"
printf 'Generated %s optimized derivatives in %s\n' "$(jq -r '.count' "$output_dir/manifest.json")" "$output_dir"
