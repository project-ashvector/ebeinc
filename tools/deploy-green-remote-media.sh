#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
"$project_root/tools/sync-visuals-staging-media.sh"
artifact="${GREEN_PAGES_ARTIFACT:-$project_root/dist/visuals-green-pages}"
"$project_root/tools/build-green-pages-artifact.sh" "$artifact"
npx wrangler pages deploy "$artifact" --project-name allthings140-visuals-green
