# v0.1.18 Stage Duplicate-Layer Fix

This candidate intentionally stops treating Stage Overlay as a special geometry system.

## Architecture

- `Visual Content` is a direct `<video class="layer content">`.
- `Stage Overlay` is now a second direct `<video class="layer stage stage-media">`.
- Both use the same normalized `x/y/width/height/scale` transform model and the same transform box code.
- Stage renders above Visual Content with a higher z-index.
- Stage media comes only from `/home/ebmarah/Videos/at140radio/desktop visuals/stage/`.
- Visual media comes only from `/home/ebmarah/Videos/at140radio/desktop visuals/visuals/`.
- Each Stage source gets its own generated H.264 runtime file (`stage-0001.mp4`, `stage-0002.mp4`, ...), generated directly from the source without crop/scale/pad filters.
- The Stage selector maps to those per-stage runtime IDs, so changing Stage actually changes the media source.
- The existing Stage opening mask is applied directly to the duplicated Stage video layer.

## Intended reset state

- Visual Content: x=0, y=0, width=100, height=100.
- Stage Overlay: x=0, y=0, width=100, height=100.
- Therefore both have identical outer canvas bounds at reset.
- The Stage is above the Visual.

## Why this is simpler

The earlier wrapper/canonical geometry path accumulated several competing coordinate systems. This candidate removes the Stage wrapper from the active architecture and reuses the working Visual Content layer model for Stage.
