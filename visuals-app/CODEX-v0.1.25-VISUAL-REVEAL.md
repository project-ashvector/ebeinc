# Codex v0.1.25 Visual Reveal Fix

Use the supplied v0.1.25 candidate as the starting point. Preserve v0.1.24 folder isolation, source-fingerprint routes, source-based cache, generic transform engine, and startup responsiveness.

The screenshot proves both videos are PLAYING. The upper duplicated layer is `alpha.mov`; the lower Visual Content layer is a normal MP4. The Visual is not missing: it is covered by the opaque black center of the H.264 Stage runtime because the upper layer says `MEDIA MASK: NONE`.

Do not change geometry. Do not change media routes. Do not add Stage Zoom. Make Stage Overlay an explicit media-layer role. The role enables the existing Stage screen-opening mask. Folder changes remain neutral.

See the full prompt supplied by ChatGPT with this ZIP for acceptance tests.
