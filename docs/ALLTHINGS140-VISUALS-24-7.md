# ALLTHINGS140 Visuals — 24/7 architecture

## Website

- Repository: `/home/ebmarah/Projects/AllThings140Radio`
- Remote: `https://github.com/project-ashvector/ebeinc.git`
- Public route: `https://allthings140radio.online/visuals/`
- Worker rewrite: `/visuals/` → `/visuals/adaptive` (`radio/_worker.js`, header `X-AT140-Visuals-Mode: adaptive-workstation-with-legacy-hls-fallback`)
- Pages project: `ebeinc`
- Deploy: `npx wrangler pages deploy radio --project-name ebeinc --branch main --commit-dirty=true`
- Rollback: redeploy the previous `radio/` tree from Git
- Fallback player: progressive MP4 `assets/visuals-desktop.mp4?v=7.0.0` (mobile: `phone-visuals-authoritative-v1.mp4`). Starts immediately; does not wait for WebSocket.
- Live renderer: shared `radio/room/workstation-stage.js`
- Realtime: `wss://visuals-realtime-staging.allthings140radio.online/ws?environment=live`
- Media origin: `https://visuals-media-staging.allthings140radio.online` and optimized `/media` on the realtime host

## Compositor

- Stage layer persists (`#stageVideo`)
- Visual layer is A/B `<video>` buffers with 700ms opacity crossfade
- Next clip is not promoted until a decoded frame exists (`requestVideoFrameCallback` / `HAVE_CURRENT_DATA` + `videoWidth`)
- Failed next clip keeps the current clip
- Composition stays `live-pending` (transparent) until live is armed so fallback is never covered by black/stage-only

## Workstation app

- Canonical source: `visuals-app/` (package 0.2.1 in source; installed dpkg may lag)
- Launcher: `allthings140radio-visuals`
- Visual-content layer uses A/B buffers in `src/main.js`
- Do not flash/rebuild blindly; `npm run build:frontend` then Tauri package when promoting a workstation release

## 24/7 notes

- Fallback is not paused solely because the tab is backgrounded
- Swap generation IDs drop stale async completions
- Do not create extra WebSocket clients per swap
