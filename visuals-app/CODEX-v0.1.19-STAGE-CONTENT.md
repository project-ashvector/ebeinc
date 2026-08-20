# Codex implementation objective — v0.1.19 Stage Content

Use this supplied v0.1.19 source as the implementation candidate. Do not rebuild the old Stage Overlay architecture.

The Stage UI has intentionally been replaced by a duplicated Visual Content-style layer named **Stage Content**. It uses the same normalized x/y/width/height/scale/fit transform path and the same drag/resize behavior as Visual Content. Its only Stage-specific differences are media source (Stage folder / stage routes), z-index above Visual Content, and the existing internal screen-opening mask.

Build the Tauri `.deb`, install it, close the prior process, relaunch the installed package, and verify Stage Content can resize exactly like Visual Content. Do not publish GREEN or production until the user visually approves it.
