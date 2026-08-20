# ALLTHINGS140 Visuals — ChatGPT Repair v0.1.37

This is a source repair package. It does **not** touch the live production visuals automatically.

## What it fixes

- Realtime `HTTP 413` caused by using a 4 KB aiohttp `client_max_size` for canonical layout POSTs.
- Test-on-Green preview payload bloat (full workstation playlist/local paths no longer sent).
- Stage/Visual canonical identity collisions and confusing layer-vs-asset IDs.
- Staging media extension mismatch (`.webm` runtime files were previously published/uploaded as `.mp4`).
- False/ambiguous realtime publish diagnostics; publisher now reports payload byte count and HTTP status.
- Green buffer switching now waits for a decoded frame before hiding the previous visual.
- A hard-coded realtime admin token was removed from the bundled workflow test.
- Bundled Green fallback layout was canonicalized (`stage-content` / role `stage`) and stripped of local paths.

## Important security action

A realtime admin token was present in the source-review archive's test file. Treat that credential as exposed and rotate it before using the repaired staging publisher.

## Apply on the Zorin workstation

1. Back up the project first.
2. Copy the repaired `visuals-app`, `visuals-green`, `visuals-realtime`, and `tests` files over the matching project directories.
3. Build the workstation:

```bash
cd /home/ebmarah/Projects/AllThings140Radio/visuals-app
npm ci
npx tauri build
```

4. Install the resulting v0.1.37 `.deb` from `src-tauri/target/release/bundle/deb/`.

## Deploy staging backend (required for the 413 fix)

Deploy the repaired `visuals-realtime/app.py` to VM2 and restart **only** the realtime service. The Green workflow cannot be fixed by rebuilding the desktop app alone because the old VM2 server rejects layout POST bodies over 4096 bytes.

## Deploy Green staging renderer

Deploy the repaired `visuals-green` code to the **Green staging** Pages project only. Do not promote Green to live production yet.

## Verification

Run:

```bash
node tests/test_v0137_contract.mjs
node tests/test_visuals_workstation_ui.mjs
python3 tests/test_visuals_system.py
```

Then test the installed app:

- Stage and Visual must resolve to different canonical layers/assets when different files are selected.
- `TEST THIS VISUAL ON GREEN` should report a compact payload size and HTTP 200.
- Green must ACK the same layout hash and display the exact selected visual.
- Production/live visuals remain locked.
