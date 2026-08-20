#!/usr/bin/env bash
set -euo pipefail

source_dir=/home/ebmarah/Documents/alerts/trump
output_dir=/home/ebmarah/at140-alerts-very-loud-2026-08-11

mkdir -p "$output_dir"

for source_file in "$source_dir"/*.mp3; do
    filename=${source_file##*/}
    ffmpeg -hide_banner -loglevel error -y -i "$source_file" \
        -af "acompressor=threshold=0.02:ratio=20:attack=1:release=100:makeup=64:knee=2.828,alimiter=limit=0.72:attack=5:release=50:level=false" \
        -codec:a libmp3lame -b:a 192k "$output_dir/$filename"
done
