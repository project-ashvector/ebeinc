# Codex Objective — Install and Validate ALLTHINGS140Radio Visuals v0.1.21

Continue the CURRENT ALLTHINGS140Radio Visuals project from the installed v0.1.20 state.

I am providing the full source handoff:

`ALLTHINGS140Radio-Visuals-source-v0.1.21-layer-manager.zip`

This is a deliberate architecture change requested after repeated Stage-specific geometry failures.

## Core objective

DO NOT repair the old special Stage editor again.

The v0.1.21 source introduces a production-style layer manager where `Stage Content` and `Visual Content` use the SAME generic media-layer implementation.

The user must be able to delete Stage Content entirely, duplicate Visual Content, rename the duplicate Stage Content, change its media folder to the Stage folder, refresh the folder, and use it as the Stage without another code build.

## First actions

1. Back up the current project and current installed v0.1.20 deliverables.
2. Extract the supplied v0.1.21 source.
3. Read `V0.1.21_LAYER_MANAGER.md`.
4. Diff the supplied source against the live project.
5. Preserve unrelated newer fixes if the live project has any.
6. Keep the v0.1.21 generic layer-manager architecture authoritative.

## Architecture that must remain

Every workspace layer is represented by an entry in `state.workspaceLayers`.

Media layers all use the same direct video rendering architecture:

```text
CANVAS
  ├── Generic Media Layer A <video>
  ├── Generic Media Layer B <video>
  ├── Generic Media Layer C <video>
  └── overlays
```

There is no separate Stage transform engine.

Do NOT restore:

- stage-transform wrapper geometry system
- xPx / yPx / widthPx / heightPx Stage model
- Stage Zoom
- canonical Stage-only resize controls
- a second Stage-only `applyLayers()` path
- hard-coded `stage-main` playback
- hard-coded assumption that only two media layers can exist

## Important v0.1.21 migration behavior

On first migration from older state:

- `Visual Content` keeps the old working Visual transform.
- `Stage Content` is recreated using a CLONE of the Visual Content transform.
- Stage Content source folder is set to:
  `/home/ebmarah/Videos/at140radio/desktop visuals/stage`
- Visual Content source folder remains:
  `/home/ebmarah/Videos/at140radio/desktop visuals/visuals`
- Stage Content receives the Stage screen-opening mask.

This intentionally discards accumulated broken Stage geometry from prior versions.

## Dynamic media server

The supplied Rust code replaces the immutable hard-coded media map with a dynamic registered route map.

The command:

`scan_layer_media(layer_id, folder)`

must:

- scan the selected folder
- register media routes only for the selected layer
- support MP4, MOV, WebM, MKV, M4V
- preserve source geometry
- directly serve compatible MP4/WebM media when possible
- generate cached H.264 MP4 runtime media only when the source/container is not reliable for WebKitGTK
- NEVER scale, crop, pad, or zoom during compatibility conversion
- reuse cached runtime media when the source has not changed
- update the loopback server route map without restarting the server

The server must remain bound only to `127.0.0.1` and retain HTTP Range support.

## Required layer-tab UI

In Visual Workspace, RIGHT CLICK any layer tab.

The menu must provide:

- Duplicate
- Rename
- Delete
- Bring Forward
- Send Backward

For media layers it must additionally provide:

- Change Media Folder…
- Refresh Media Folder
- Enable/Disable Stage Screen Mask

Deleting a layer removes only the editor layer/configuration. It MUST NOT delete source media files.

## Exact user recovery test

This test is mandatory because it is the purpose of the release.

Start with the installed app.

1. Open Visual Workspace.
2. Confirm Visual Content plays a normal Visual.
3. RIGHT CLICK Stage Content → Delete.
4. Confirm Stage Content disappears from Layers.
5. RIGHT CLICK Visual Content → Duplicate.
6. Confirm a new copy appears and behaves identically to Visual Content.
7. RIGHT CLICK the copy → Rename.
8. Rename it exactly:
   `Stage Content`
9. RIGHT CLICK Stage Content → Change Media Folder…
10. Select:
    `/home/ebmarah/Videos/at140radio/desktop visuals/stage/`
11. RIGHT CLICK Stage Content → Refresh Media Folder.
12. Confirm the Stage videos appear in the generic SELECT MEDIA dropdown.
13. Select `alpha.mov` or `alpha2.mov`.
14. If the source is HEVC MOV, wait for its compatible runtime cache generation.
15. Confirm Stage Content reaches PLAYING.
16. Enable Stage Screen Mask if not automatically enabled.
17. RIGHT CLICK Stage Content → Bring Forward if required.
18. Drag Stage Content.
19. Resize from every side and corner.
20. Confirm the actual Stage video follows the cyan transform box exactly.
21. Select Visual Content and resize it.
22. Confirm Visual Content continues behaving exactly as it did before.
23. Switch media using Previous / Next / Random on both media layers.
24. Confirm each layer keeps its own geometry while changing video files.

If this exact workflow does not pass, DO NOT package the release.

## Folder refresh test

For any generic media layer:

1. Point it to a test media folder.
2. Refresh and record file count.
3. Add/copy another supported video into that folder.
4. Click Refresh Media Folder.
5. Confirm the new file appears without restarting the app.
6. Remove the test file afterward without deleting any real user media.

## Right-click operations test for all layer tabs

Test Duplicate / Rename / Delete on:

- a media layer
- a logo layer copy
- an alert layer copy

For non-media layers, folder options should not be shown.

Verify a deleted layer is removed from the canvas and state but its external assets remain untouched.

## Transform acceptance

All generic media layers must use the same transform path.

At any time:

```text
CYAN TRANSFORM BOX RECT == ACTUAL SELECTED LAYER RECT
```

Test:

- move
- left edge
- right edge
- top edge
- bottom edge
- all four corners
- Shift+corner aspect preservation

Do not create a separate Stage correction path if a test fails. Fix the shared generic transform path.

## Playback lifecycle acceptance

For at least two generic media layers, run 20 cycles of:

```text
Layer A → Layer B → Layer A → Layer B
```

Then navigate:

```text
Visual Workspace → Diagnostics → Visual Workspace
Visual Workspace → 24/7 Visuals → Visual Workspace
Visual Workspace → Chat / Room → Visual Workspace
```

All media layers must reacquire their registered routes and continue playing.

## Performance

Dragging/resizing must never:

- change `src`
- call ffmpeg
- restart the media server
- rebuild the media library
- reconnect realtime

Only geometry changes during a transform.

Folder scanning/conversion happens only when:

- changing a media folder
- refreshing a media folder
- first scan when cache is missing/stale

## Validate before packaging

Run:

```bash
node --check src/main.js
npm ci
npm run build
cargo check --manifest-path src-tauri/Cargo.toml
```

Then launch a dev/runtime build and complete all tests above.

Do not build the final `.deb` until they pass.

## Build and install

Version must be `0.1.21` consistently in:

- package.json
- package-lock.json
- src-tauri/Cargo.toml
- src-tauri/Cargo.lock
- src-tauri/tauri.conf.json

Build a fresh Debian package.

Copy the final installer to:

`Projects/AllThings140Radio/dist/ALLTHINGS140/Visuals-App/ALLTHINGS140Radio-Visuals_0.1.21_amd64.deb`

Calculate SHA-256.

INSTALL the `.deb` on this PC.

If authorization is required, open the normal authorization prompt and wait for user approval.

Then:

1. completely close v0.1.20
2. confirm no stale Visuals process remains
3. install v0.1.21
4. launch the normal installed app
5. verify dpkg reports 0.1.21
6. verify Diagnostics reports 0.1.21
7. perform the exact delete → duplicate Visual Content → rename Stage Content → choose Stage folder → refresh workflow again in the INSTALLED build

## Final deliverable folder

Create/open:

`Projects/AllThings140Radio/dist/ALLTHINGS140/Visuals-App/v0.1.21-final-handoff/`

Place inside:

- final `.deb`
- SHA256SUMS.txt
- full final source ZIP named:
  `ALLTHINGS140Radio-Visuals-source-v0.1.21-final.zip`
- `INSTALL.md`
- final validation report

Run an archive integrity test on the final source ZIP.

Open this folder in the file manager with `xdg-open` when finished so it is easy for me to upload the final ZIP back to ChatGPT for review.

## Production safety

Do NOT deploy GREEN during this objective.
Do NOT modify production.

Frozen production baseline must remain:

`4ca1a32e74c2b319fa8c7979b2e68e1486166a2d105c53158f2a417bf976ef32`

## Final report

Report:

- root cause(s) found during merge/test
- installed version
- `.deb` path
- `.deb` SHA-256
- media server address
- delete/duplicate/rename test result
- arbitrary folder selection test result
- refresh-after-new-file test result
- Stage Content recreated from Visual Content test result
- transform test result
- 20 layer-switch test result
- navigation test result
- realtime state
- production baseline verification
- final handoff folder path
- final source ZIP path + SHA-256

End with:

`v0.1.21 GENERIC LAYER MANAGER INSTALLED — WAITING FOR USER APPROVAL`

Do not call it production ready until I visually approve it.
