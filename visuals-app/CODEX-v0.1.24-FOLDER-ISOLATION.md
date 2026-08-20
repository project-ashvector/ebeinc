# Codex objective: implement/test v0.1.24 folder isolation fix without changing working UI/geometry

Continue from the CURRENT ALLTHINGS140Radio Visuals project. I am providing a complete v0.1.24 candidate source ZIP created from the uploaded v0.1.23 final source.

## Non-negotiable scope

DO NOT redesign Stage Content, Visual Content, transform handles, masks, overlays, layer manager UI, presets, GREEN, or production. Do not add features. Merge only newer unrelated fixes if the live tree has them.

The uploaded v0.1.23 validation explicitly did not certify the GUI 2x2 media/mask matrix. The user's runtime experiment now exposed a different issue: duplicating Visual Content and changing ONLY the duplicate's folder can make the app freeze/reload confusingly, while Linux can report the app as not responding.

## Concrete source problems fixed in candidate

1. v0.1.23 `scan_layer_media` is synchronous and directly invokes ffprobe/ffmpeg. Folder changes to HEVC/MOV can block GTK/WebKit.
2. v0.1.23 media route IDs are keyed by layer ID and are mutable. A duplicate can temporarily carry the original layer's route IDs.
3. v0.1.23 `changeLayerFolder()` performs a full `render('Visual Workspace')`, recreating ALL video elements after changing one layer.
4. v0.1.23 `duplicateLayer()` copies the transient `layerLibraries` entries, including runtime route IDs.

The candidate fixes all four while leaving geometry and mask behavior alone.

## First action

1. Back up the live project and `~/.local/share/allthings140radio-visuals/workstation.json`.
2. Extract the supplied v0.1.24 source.
3. Read `V0.1.24_FOLDER_ISOLATION_FIX.md`.
4. Diff `src/main.js` and `src-tauri/src/lib.rs` against the live tree.
5. Preserve this architecture unless a compile error requires a minimal correction.

## Required behavior

### Layer isolation

Create/keep two media layers:

- Visual Content
- Visual Content Copy

Both can initially use the Visuals folder.

Record for BOTH layers:

- id
- sourceFolder
- mediaIndex
- selected filename/sourcePath
- routeId
- frame x/y/width/height/scale/fit
- DOM video currentSrc

Then change ONLY `Visual Content Copy` to:

`/home/ebmarah/Videos/at140radio/desktop visuals/stage/`

After the change:

- only the COPY sourceFolder changes
- only the COPY catalog changes
- original Visual Content keeps its exact sourceFolder
- original Visual Content keeps its selected file
- original Visual Content keeps its route/currentSrc
- original Visual Content keeps playing
- neither layer's transform changes
- neither layer's mask changes

Do not accept visual guesses. Log/compare the actual per-layer values.

### Source-based routes

Routes must be source-based, e.g. `source-<fingerprint>`, not mutable `layer-<id>-0001` routes.

Two layers referencing the same physical file may share the same source route safely.
Changing one layer's folder must never repoint an existing source route used by the other layer.

### Source-based runtime cache

HEVC compatibility runtimes must be cached by physical source fingerprint under a source-based cache directory, not by layer ID.

Duplicating/renaming a layer must never force the same MOV to be encoded again simply because its layer ID changed.

Original media files must never be deleted or overwritten.

### Responsiveness

Trigger a Stage-folder refresh that requires HEVC conversion.

While ffmpeg is running:

- move the app window
- click another layer
- navigate to Diagnostics and back if safe
- confirm Linux does NOT show Not Responding

The ffmpeg/ffprobe work must run in a blocking worker via the async Tauri command, not on the GUI-critical path.

### No full workspace rebuild on folder change

Changing one layer folder must not call a full workspace render that destroys every video element.

The existing video elements for unrelated layers must survive.

Record before and after for the untouched Visual Content element:

- element identity (or a marker placed on the DOM element)
- currentSrc
- currentTime

It should not be replaced merely because another layer's folder changed.

### Duplicate behavior

When duplicating a media layer:

- copy editor layer definition/frame state
- DO NOT inherit transient runtime library route bindings by layer identity
- refresh/register the duplicate catalog safely

### Folder refresh vs folder change

A normal Refresh on the same folder should preserve the selected physical file by `sourcePath` when it still exists.
A Change Folder may select index 0 for ONLY the changed layer.

## Regression sequence — must pass 5 cycles

1. Visual Content → Visuals folder → select 87.mp4 (or another known Visual).
2. Duplicate it.
3. Rename copy Stage Content if desired.
4. Change ONLY copy folder to Stage.
5. Confirm original still plays the original Visual.
6. Select alpha.mov/alpha2.mov on copy.
7. Change copy back to Visuals.
8. Confirm original was never altered.
9. Change copy to Stage again.
10. Repeat five times.

At no point may both layer definitions silently change folders together.
At no point may changing one folder reset/recreate the other video's player.
At no point may the app become Not Responding during Stage preparation.

## Important screenshot interpretation

The user's latest screenshot status already showed two different selected sources simultaneously (`Visual Content Copy` on alpha2.mov and `Visual Content` on 87.mp4). So do not misdiagnose full-opacity Stage content covering the Visual as proof both source folders changed. Use per-layer state/currentSrc to prove or disprove coupling.

## Keep these systems unchanged

- generic media layer X/Y/Width/Height/Scale/Fit engine
- drag/resize handles
- explicit Stage screen mask toggle
- global frames
- overlays
- layer context menu
- production lock
- GREEN routing

## Validation before package

Run:

`node --check src/main.js`

`npm ci`

`npm run build`

`cargo check --manifest-path src-tauri/Cargo.toml`

Then run the installed/runtime layer-isolation test above.

Also inspect processes during a Stage conversion:

`pgrep -af 'allthings140radio|ffmpeg|ffprobe'`

The app must remain responsive.

## Build/install

Build one candidate as v0.1.24.

Install the real `.deb` on THIS PC, close the old process first, and reopen the normal installed application. If authorization is needed, open the normal authorization prompt and wait for me.

Do not publish GREEN. Do not touch production.

Production frozen hash remains:

`4ca1a32e74c2b319fa8c7979b2e68e1486166a2d105c53158f2a417bf976ef32`

## Final handoff

Create:

`Projects/AllThings140Radio/dist/ALLTHINGS140/Visuals-App/v0.1.24-folder-isolation/`

Include:

- final `.deb`
- SHA256SUMS.txt
- complete final v0.1.24 source ZIP
- validation report with five-cycle isolation results
- exact before/after per-layer sourceFolder/mediaIndex/sourcePath/route/currentSrc values

Open that folder with `xdg-open` so I can upload the final source ZIP back to ChatGPT.

End with:

`v0.1.24 FOLDER ISOLATION CANDIDATE INSTALLED — WAITING FOR USER APPROVAL`
