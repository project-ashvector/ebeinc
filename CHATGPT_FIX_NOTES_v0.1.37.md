# ALLTHINGS140 Visuals — ChatGPT Source Repair v0.1.37

This source-only repair targets the failures visible in the supplied recordings and source bundle.

## Fixed in source
- HTTP 413: realtime server previously used a 4 KB `client_max_size` for layout POSTs. HTTP layouts now have a separate 256 KB request ceiling with a 128 KB canonical-layout contract.
- Fast preview payload bloat: Test-on-Green preview layouts no longer include the entire 24/7 playlist or workstation-local file paths.
- Stage/Visual identity collisions: canonical resolver now rejects duplicate built-in IDs/roles instead of silently picking the first match; layer identity and media asset identity are separate.
- Reserved layer roles: custom media can no longer become an additional Stage/Visual structural layer.
- Runtime media extension: a `.webm` runtime asset remains `.webm` on the staging media origin instead of being uploaded as `<fingerprint>.mp4`.
- Realtime POST diagnostics: publisher returns payload byte size and HTTP status and posts from a temporary JSON file.
- Green buffer continuity: renderer waits for a decoded frame before making the standby buffer visible.
- Security: removed a hard-coded admin token from the bundled workflow test. The token previously bundled should be rotated.

## Deployment required
This ZIP cannot update the user's machine by itself. The repaired source must replace the corresponding files in the project, then:
1. Deploy `visuals-realtime/app.py` to VM2 and restart only the realtime service.
2. Deploy `visuals-green/stage.js` if Green source is served from Pages.
3. Build/install the Tauri workstation v0.1.37.

Production/live visuals should remain locked until Green is visually verified.
