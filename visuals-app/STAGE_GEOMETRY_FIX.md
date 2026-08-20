# ALLTHINGS140Radio Visuals v0.1.17 candidate fix

## Root cause found in v0.1.16

The wrapper refactor was only half-completed. `.layer.stage` changed from the video element into the wrapper `<div>`, but several runtime paths still treated `.layer.stage` as if it were the video. They assigned `src`, called `load()`, and called `play()` on the wrapper. After a workspace re-render/layer switch, the inner `.stage-media` therefore did not reliably reacquire the loopback H.264 source and could remain on/return to the original HEVC source or no source, producing `STAGE: FAILED`.

The workspace also recreated the Stage as a placeholder div, then converted it to video, then wrapped it. That lifecycle made re-renders fragile.

## v0.1.17 changes

- The workspace now creates `.stage-transform > .stage-media` directly.
- `ensureStageDom()` is idempotent and only exists as compatibility protection.
- Every Stage source write targets `.stage-media`, never `.layer.stage`.
- The wrapper exclusively owns canonical x/y/width/height.
- The inner video is `position:absolute; inset:0; width:100%; height:100%; object-fit:fill`, so its DOM rectangle equals the wrapper rectangle.
- `canonicalApplyLayers()` explicitly targets `.stage-transform` and centrally rebinds `/media/stage-main` after every workspace render when the loopback server is available.
- Media source changes use one `setVideoSource()` helper, avoiding needless reloads.
- Stage status shows decoded dimensions and media error code.

## Required runtime acceptance

1. Reset Stage to canonical `0,0,1920,1080`.
2. Stage reports decoded `1920x1080` and PLAYING.
3. `stage-transform.getBoundingClientRect()` and `.stage-media.getBoundingClientRect()` match within <1 CSS pixel.
4. Switch Stage Overlay → Visual Content → Stage Overlay repeatedly. Stage remains PLAYING.
5. Navigate to another app tab (Diagnostics / 24/7 Visuals) and back to Visual Workspace. Stage reacquires `/media/stage-main` and remains PLAYING.
6. Resize/move Stage; wrapper and media remain identical.
