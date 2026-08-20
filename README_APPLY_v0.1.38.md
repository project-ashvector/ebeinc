# ALLTHINGS140 Visuals — ChatGPT Smoothness/Live-Readiness Update v0.1.38

This is a conservative source update built from the working v0.1.37 tree. It focuses on responsiveness, clean Green staging synchronization, renderer stability, bounded background work, state recovery, and avoiding regressions before live promotion.

## Important

- **Green remains staging. Production/live visual routing stays locked.**
- Apply this source into the real `/home/ebmarah/Projects/AllThings140Radio` repository, then build/install the Tauri `.deb` on Zorin.
- Deploy `visuals-realtime/app.py` to VM2 and `visuals-green/` to the **Green staging** Pages project only.
- Do not promote Green to the live website until the user visually approves a soak test.

## Main changes

- Workstation publish snapshots are compact and avoid cloning/sending unnecessary workstation state.
- Normal layout publishing uses Realtime/Media Origin, not a full Cloudflare Pages redeploy.
- Test-on-Green requires a real renderer ACK; gateway storage alone is no longer success.
- Test-on-Green opens Green when needed to break the “wait for ACK before renderer exists” loop.
- Failed/cancelled Green tests cancel native publish jobs.
- Workstation WebSocket reconnect uses bounded exponential backoff and online recovery.
- Hidden/unused workstation Stage video sources are released instead of decoding needlessly.
- Navigating away from a view releases video sources/resources.
- Runtime transcoding is bounded by a native timeout.
- Green visual transitions are serialized; inactive-buffer `ended` events cannot advance the playlist.
- Green waits for a decoded frame before switching buffer visibility.
- Emergency fallback is no longer randomly included in the healthy 24/7 playlist.
- Green network polling is bounded/non-overlapping.
- Duplicate layout delivery is deduplicated to avoid unnecessary media reloads.
- Renderer ACKs use WebSocket first and HTTP only as fallback instead of double-posting.
- Safe Playback Mode now actively resets pulse/bloom/shake to neutral.
- Valid `0` cutout coordinates are preserved in both workstation and Green.
- Corrupt workstation state can recover from the newest valid bounded backup.
- State backups are bounded (120) and use millisecond timestamp precision.
- Workstation config permissions are tightened to `0600` on Linux.
- Realtime server handles CORS preflight, uses SQLite `synchronous=NORMAL` + `busy_timeout`, and broadcasts concurrently with per-client timeout.
- Realtime admin credential is no longer exposed in the local `curl` process command line; a short-lived mode-0600 header file is used and removed.
- Build provenance now exposes app version, Git commit, and build timestamp in Diagnostics.
- Stale duplicate source mirrors are synchronized with their actual build-source counterparts.
- Mutating staging tests are opt-in instead of silently changing Green.

## Tests run in ChatGPT sandbox

- JavaScript syntax: workstation + Green — PASS
- Python compile: realtime server — PASS
- `tests/test_v0138_contract.mjs` — PASS
- `tests/test_visuals_workstation_ui.mjs` — PASS (47/47)
- `tests/test_visuals_system.py` — PASS (10/10)
- `tests/test_realtime_http.py` — PASS (3/3)

The sandbox does not have the Rust/Cargo toolchain or Zorin/WebKitGTK runtime, so Antigravity must perform the final Tauri compile/install and real workstation/Green soak verification.
