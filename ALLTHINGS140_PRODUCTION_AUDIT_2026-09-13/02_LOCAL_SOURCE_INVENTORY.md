# Local Source Inventory

**Authoritative repo:** `/home/ebmarah/Projects/AllThings140Radio` (symlinked from `Projects/CURRENT-LIVE/ALLTHINGS140-Radio`)

## Primary trees

| Path | Purpose |
|------|---------|
| `radio/` | Production website, Pages worker, PWA, auth shell |
| `tools/server.py` | Broadcast authority, API, AutoDJ |
| `android/mobile-app/` | Play package `online.ebeinc.allthings140radio` |
| `android/watch-app/` | Wear OS companion (separate packages) |
| `visuals-app/` | Desktop visuals compositor (Tauri) |
| `visuals-realtime/` | GCP WebSocket gateway |
| `visuals-green/` | Green Room overlay assets |
| `chat-worker/` | Green Room chat Cloudflare Worker |
| `hub/` | Operator Hub (PySide6 desktop) |
| `supabase/migrations/` | Listener account entitlements schema |
| `discord-bot/` | Discord voice relay |

## Duplicate / archive copies

- `Projects/CURRENT-LIVE/ALLTHINGS140-Radio` → symlink to canonical repo
- `Backups/ALLTHINGS140/` — coordinated backups (2026-09-05)
- `hub.before-20260817T023840Z/` — pre-takeover hub snapshot inside repo
- Multiple nested Wear source snapshots under `android/watch-app/` — latest v0.3.2

## Build artifacts (local)

| Artifact | Path | SHA-256 |
|----------|------|---------|
| Release AAB | `android/mobile-app/app/build/outputs/bundle/release/app-release.aab` | `d683dd371f51ec98e953ac133ce7c70497bfedbd88cfee4bc9a6577785fce4a9` |
| Release APK | `android/mobile-app/app/build/outputs/apk/release/app-release.apk` | (not captured this session) |

## Dirty working tree

Current branch: `fix/visuals-24-7-compositor` with modified visuals-app files and many untracked assets/evidence screenshots. `main` is 94 commits ahead of origin.
