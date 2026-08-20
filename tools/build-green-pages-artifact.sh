#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
site="$project_root/visuals-green"
out="${1:-$project_root/dist/visuals-green-pages}"
rm -rf "$out"
mkdir -p "$out"

# Copy only the Pages frontend/configuration. Large media is intentionally excluded.
find "$site" -maxdepth 1 -type f -exec cp -a {} "$out/" \;
find "$site" -maxdepth 1 -type d ! -name media ! -path "$site" -exec cp -a {} "$out/" \;

largest=""
largest_size=0
bad=0
while IFS= read -r -d '' file; do
  size=$(stat -c '%s' "$file")
  if (( size > largest_size )); then largest_size=$size; largest=$file; fi
  if (( size > 24*1024*1024 )); then
    printf 'ERROR: Pages file exceeds 24 MiB: %s (%s bytes)\n' "$file" "$size" >&2
    bad=1
  fi
done < <(find "$out" -type f -print0)
printf 'Pages artifact: %s\nLargest file: %s (%s bytes)\nFiles over 24 MiB: %s\n' "$out" "$largest" "$largest_size" "$bad"
(( bad == 0 )) || exit 1
