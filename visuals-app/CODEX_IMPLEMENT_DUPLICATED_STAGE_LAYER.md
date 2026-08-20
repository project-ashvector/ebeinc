# Codex objective: implement/test v0.1.18 duplicate-stage-layer candidate

Use this source as the candidate implementation. Do not reintroduce the old Stage wrapper/canonical transform stack.

The Stage is intentionally implemented as a second copy of the working Visual Content video-layer architecture:

- Visual Content: direct video layer, z-index 1, media from the Visuals folder.
- Stage Overlay: direct video layer, z-index 5, media from the Stage folder.
- Both use the same normalized x/y/width/height/scale transform path and the same resize box.
- Stage gets the existing screen-opening mask, but no separate outer geometry wrapper.
- Each Stage source gets its own browser-compatible H.264 runtime derivative generated directly from that source without scale/crop/pad filters.
- The Stage selector changes the actual stage-NNNN route.

Acceptance: at reset, Stage and Visual outer bounds are identical. The Stage is above the Visual. The Stage's decoded video is 1920x1080, while the editor viewport can be 1280x720. The Stage remains visible and playing after switching Stage/Visual layers and after navigating away/back.
