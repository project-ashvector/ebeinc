# ALLTHINGS140 Visuals — Deep Smoothness / Live-Readiness Review v0.1.38

## Goal
Preserve the now-working Stage/Visual/Green path while hardening the system for long-running staging use and eventual user-approved live promotion.

## High-value issues found and addressed

1. **Oversized/UI-heavy publish state** — publish now deliberately constructs a compact contract rather than cloning the full workstation state.
2. **Unnecessary Cloudflare Pages redeploys** — routine layout changes now use media sync + Realtime; Pages deploy remains for Green code changes only.
3. **False Green success** — a stored layout is not called rendered until Green ACKs the exact layout hash.
4. **Circular renderer ACK workflow** — the test opens Green when no renderer is present and continues waiting for the real ACK.
5. **Hidden media decoder retention** — unused video sources are cleared in workstation view changes and Stage cutout/fallback paths.
6. **Green transition races** — visual swaps are serialized and old-buffer `ended` events are ignored.
7. **Early visibility swap** — Green waits for a decoded frame before making the replacement buffer visible.
8. **Broken eager preload behavior** — removed a preload path that could reload the retired buffer while it was still fading out.
9. **Emergency fallback entering normal shuffle** — fallback is now failure-only unless no valid playlist exists.
10. **Duplicate renderer ACK traffic** — ACK is sent over WebSocket, with HTTP used only as fallback.
11. **Network stalls** — Green fetches are bounded; station/takeover polls cannot overlap indefinitely.
12. **Safe Mode residual transforms** — disabling effects now resets transform variables immediately.
13. **Zero-coordinate geometry bug** — cutout x/y of 0 no longer silently become default 23/33.5 values.
14. **Background transcode hang risk** — automatic runtime FFmpeg conversion now has a native timeout.
15. **Realtime fanout head-of-line blocking** — WebSocket clients are sent concurrently with a per-client timeout.
16. **State corruption / backup growth** — recovery from newest valid backup, millisecond-safe filenames, bounded backup retention.
17. **Credential exposure in process list** — realtime Bearer token removed from curl argv.
18. **Stale source mirrors** — duplicate `visuals-app/main.js` and `src-tauri/lib.rs` are synchronized with actual build sources to reduce future agent mistakes.
19. **Release lock metadata** — package-lock/Cargo.lock root versions are synchronized with 0.1.38.
20. **Unsafe mutating tests** — staging-mutation tests require explicit opt-in.

## Conservative decisions

- The workstation’s four-panel WebKitGTK Stage cutout was **not** replaced because it is currently working and previous single-mask methods were unreliable in WebKitGTK. Hidden/unused decoders were reduced instead.
- No live-site routing is changed.
- No experimental takeover/music-video/audio-reactive feature expansion is included.
- No broad dependency upgrades were performed.

## Current-video observation
The short user screencast supplied with this review showed continuing visual motion without an obvious full-screen blackout/freeze. A ~6 second recording is useful smoke evidence, not a long soak test.

## Final promotion gate
Before using Green as the live visual feed, run the real installed Tauri app and Green for a minimum 30-minute soak with repeated visual changes, loops, Green publishes, realtime reconnects, and resource monitoring. Production cutover should stay locked until the user visually approves the result.
