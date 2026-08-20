# Release Notes — v1.3.0 Release Candidate

- Rebuilt the primary Android experience as a native radio app instead of a WebView-first shell.
- Centralized playback in a Media3 `MediaLibraryService` for background/system/Android Auto integration.
- Added responsive main UI with native LIVE/now-playing/listener/retry states and branded lightweight visualizer.
- Added Settings with dynamic app version/build, target SDK, truthful update-check states, privacy, and Play Store path.
- Added in-app privacy notice and a separate public-policy drafting checklist.
- Targeted Android 16 / API 36 and modernized edge-to-edge/back/large-screen behavior.
- Hardened the optional Visuals WebView and moved the general website to the external browser.
- Removed Green Room from the initial Play release surface pending full UGC moderation/report/block/Terms support.
- Removed the old ~57 MB decorative video resource.
- Added adaptive launcher icons and properly scaled legacy icons.
- Removed unnecessary permissions and unsafe release signing fallback.
- Added release QA, store-listing, privacy, and Google Play submission documentation.
