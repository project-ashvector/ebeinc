# ALLTHINGS140 Project Map

Updated: 2026-08-26

Canonical project root: `/home/ebmarah/Projects/AllThings140Radio`

This repository is intentionally a multi-application workspace. Several paths are deployment inputs or runtime references; do not move them merely to make the root smaller.

## Canonical source paths

| Path | Purpose | Current state |
|---|---|---|
| `radio/` | Public Cloudflare Pages website, persistent radio shell, Account, Green Room, and Visuals routes | Production website source; main Pages project `ebeinc` |
| `radio/visuals/` | Public Visuals selector targets: known-good legacy HLS plus dormant shared compositor | Public selector currently `legacy` |
| `radio/room/` | Public Green Room route, moderated chat bridge, and shared compositor client | Public selector currently `legacy` |
| `visuals-app/` | Canonical Tauri Visuals workstation/editor/publisher | Source and installed package version 0.1.43 |
| `visuals-green/` | Canonical isolated Green renderer source | Shared renderer core; staging-only |
| `visuals-green-pages-dist/` | Generated/sanitized Green Pages deployment artifact | Deploy only to `allthings140-visuals-green` |
| `visuals-realtime/` | aiohttp realtime/layout/renderer-truth service and systemd/deployment files | Oracle VM2 service, version 0.2.0-staging |
| `android/` | Android listener and Wear OS source/build inputs | Do not move signing files or Gradle paths |
| `supabase/` | Account/Green Room database migrations and configuration | Do not alter role architecture casually |
| `hub/` | ALLTHINGS140 management hub | Local management application |
| `tools/` | Radio and Visuals operational tools | Some scripts are production deployment inputs |
| `config/`, `operations/` | Service definitions, recovery, backup, and operational configuration | Preserve paths referenced by documentation/installers |
| `tests/` | Cross-system regression contracts | Run targeted Visuals suites before promotion |
| `docs/`, `ALLTHINGS140_PROJECT_CONTEXT/` | Architecture, safety, and operational memory | Read `AGENTS.md` and `DO_NOT_BREAK.md` first |
| `backups/` | Historical rollback snapshots | Large (about 46 GB); retained, not live source |
| `dist/`, `builds/`, `build-deb/` | Generated artifacts and old releases | Large; do not treat as canonical source |
| `archive/` | Reserved for inventoried, proven-obsolete snapshots | Do not move uncertain files here |

## External canonical/runtime paths

| Path or host | Purpose | Move policy |
|---|---|---|
| `/home/ebmarah/Videos/at140radio/desktop visuals/visuals/` | 95 master Visual clips | **DO NOT MOVE**; workstation state references absolute paths |
| `/home/ebmarah/Videos/at140radio/desktop visuals/stage/` | Master Stage media | **DO NOT MOVE** |
| `/home/ebmarah/Videos/at140radio/desktop visuals/generated/web-v1/` | Generated web derivatives and manifest | Regenerable; never overwrite masters |
| `/home/ebmarah/.local/share/allthings140radio-visuals/` | Workstation state, versions, media cache, logs | **DO NOT MOVE**; contains active local state |
| Oracle VM2 `/opt/allthings140-visuals-realtime/` | Realtime service program | Server canonical deployed path |
| Oracle VM2 `/srv/allthings140-visuals/media/` | Hosted Stage and Visual media | Live-referenced; backup and update atomically |
| Oracle VM2 `/var/lib/allthings140-visuals/realtime.db` | Persisted layouts, messages, schedules, state | Never replace without backup/migration verification |

## Live and staging systems

- Website production: `https://allthings140radio.online` (`ebeinc` Pages project).
- Public Visuals: `https://allthings140radio.online/visuals/`; KV selector currently chooses legacy HLS.
- Public Green Room: `https://allthings140radio.online/room/`; moderated chat remains independent.
- Visuals Green staging: `https://allthings140-visuals-green.pages.dev/` (`allthings140-visuals-green` Pages project).
- Realtime health: `https://visuals-realtime-staging.allthings140radio.online/health`.
- Media origin: `https://visuals-media-staging.allthings140radio.online`.
- Public radio stream: `https://stream.ebeinc.online/live.mp3`; Visuals work must never restart its services.

## Deployment locations

- Website Pages command is recorded in `hub/registry/app_registry.py`; production output is `radio/` and project is `ebeinc`.
- Green Pages deployment is implemented in `visuals-app/src-tauri/lib.rs`; it deliberately deploys only the small `visuals-green-pages-dist/` artifact.
- Realtime install/service definitions live under `visuals-realtime/deployment/` and `visuals-realtime/services/`.
- Media synchronization helper: `tools/sync-visuals-staging-media.sh`.
- Visual routing/rollback authority: `radio/_worker.js` plus the `VISUALS_ROUTING_KV` selector. Legacy remains the safe default.

## Current component summary

- Website: tabbed layout live from commit `28f3c3d`.
- Visuals workstation: 0.1.43, canonical source `visuals-app/`.
- Visuals renderer: one shared `stage.js` core across Green, Room, and public Visuals sources.
- Realtime: 0.2.0-staging on isolated Oracle VM2; health must pass before Green promotion.
- Android listener: canonical source `android/mobile-app/`; release artifacts are organized under `/home/ebmarah/Documents/AT140 Builds/Android/`.
- Mic: separate project `/home/ebmarah/Projects/ALLTHINGS140-Mic`; do not merge it into listener/Visuals source.
- Reports: canonical new collection `/home/ebmarah/Documents/ALLTHINGS140 Reports/`; older report paths remain intact for compatibility.

## Safe organization policy

The project is currently 74 GB, dominated by `backups/` (~46 GB), `visuals-app/` (~16 GB), `android/` (~4.1 GB), `dist/` (~3.1 GB), and old `builds/` (~1.8 GB). These were inventoried but not moved or deleted because some contain rollback material or live-referenced state. Future cleanup should begin with a checksum/reference inventory and copy-to-archive operation, never deletion.
