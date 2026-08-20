# Codex objective: install v0.1.26 compositor stabilization

Continue the CURRENT ALLTHINGS140Radio Visuals project from installed v0.1.25.

I am supplying `ALLTHINGS140Radio-Visuals-source-v0.1.26-compositor-stabilization.zip`.

This is a narrowly scoped stabilization candidate made from the actual v0.1.25 final source. Do not redesign the transform engine, layer manager, media routing, startup performance, realtime, overlays, GREEN, or production.

## Why this change is necessary

The latest installed v0.1.25 screenshot shows:

- Stage Content PLAYING.
- Visual Content PLAYING.
- Stage role = Stage Overlay.
- Stage mask = Stage Screen.
- Stage artwork appears primarily inside the central target while large outside areas are black.

That is the inverse/incorrect visual result of the intended mask. The v0.1.25 validation explicitly could not perform pixel-level WebKitGTK confirmation, so source/build success was not proof that the CSS mask rendered correctly in the real GTK WebView.

The fix is to STOP USING CSS MASKING in the active compositor.

## Required compositor

Use this stable model:

1. Stage Base = ordinary opaque H.264/other browser-compatible video, full canvas or user frame.
2. Visual Content = ordinary generic media layer ABOVE Stage Base, positioned inside the Stage screen opening with the existing transform/Global Frame controls.
3. Station/Takeover Logo, Now Playing, Presence, Reactions, Room Energy remain above both.

The Stage can remain H.264 and opaque. The Visual physically covers the black Stage screen area, which produces the same final appearance without alpha or CSS mask support.

## Preserve supplied implementation

The supplied v0.1.26 source already:

- changes the default Stage/Visual z relationship to Stage below Visual;
- clears legacy `stage-screen` masks in a one-time migration;
- makes role `stage` mean **Stage Base**, not masked overlay;
- makes role `visual` mean **Visual Screen** above Stage;
- disables the legacy CSS mask in `applyLayers()` by always calling `clearMask()`;
- keeps Visual and Stage on the exact same generic transform code;
- centers object positioning;
- removes Stage-mask controls from the active inspector/context menu;
- prevents Stage-role layers from ending up above the primary Visual Content;
- keeps source-fingerprint routes/cache and async scan architecture untouched.

Review the diff, preserve unrelated newer fixes if any, but do not restore the v0.1.25 mask path.

## First: prove whether the problem is outside normal transform code

Before installing the candidate, make a tiny standalone test using the CURRENT WebKitGTK/Tauri engine:

- render a solid colored rectangle;
- apply the exact v0.1.25 SVG/data-URI `mask-image` implementation;
- compare against Chromium if useful;
- record whether WebKitGTK displays the intended outside-visible/inside-hole polarity.

This is diagnostic only. Do NOT spend time repairing CSS masks if they differ. The candidate intentionally avoids them.

Also confirm the original source and H.264 runtime are normal 1920x1080 media files. Do not modify originals.

## Back up first

Back up:

- project source;
- `~/.local/share/allthings140radio-visuals/workstation.json`;
- current installed v0.1.25 package/source handoff.

Do not delete current user state.

## Migration acceptance

Launch v0.1.26 against the EXISTING state.

Verify migration changes only compositor state:

- Stage role remains Stage.
- Visual role remains Visual.
- `mask` is cleared to `none` on media layers.
- saved X/Y/Width/Height/Scale/Fit values are byte-for-byte/numerically unchanged.
- Stage z < Visual z.

Do not reset the Stage or Visual frames.

## Exact GUI test

Use the existing current layout.

Stage Content:
- choose alpha.mov or alpha2.mov;
- role should display `STAGE BASE`;
- source/runtime should reach PLAYING;
- MEDIA MASK should no longer be part of the active compositor.

Visual Content:
- choose a known-good normal Visual;
- role should display `VISUAL SCREEN`;
- reach PLAYING;
- keep the currently saved screen-sized frame.

Expected final output:

- Stage artwork fills its current Stage rectangle.
- Visual is visible where the Visual Content rectangle sits over the Stage screen.
- no CSS mask is involved;
- no inverted mask;
- no black outside canvas caused by mask polarity.

## Fit test

If Visual Content is not already aligned to the screen opening, select Visual Content and use the existing `Fit To Screen Target` once.

Do NOT change Stage geometry.

Then save the Visual Global Frame.

Switch through at least 10 Visuals using Next and Random.

Every Visual must retain the same frame and appear in the Stage screen.

## Transform regression test

Stage Base:
- drag;
- resize left/right/top/bottom/corners;
- actual video follows cyan box.

Visual Screen:
- drag;
- resize;
- actual video follows cyan box.

Neither operation may mutate the other layer.

## Folder isolation test

On a duplicate generic media layer:

Visuals folder -> Stage folder -> Visuals folder.

Verify:

- only sourceFolder/media catalog changes;
- x/y/width/height/scale/fit unchanged;
- role unchanged;
- z unchanged;
- no mask is activated;
- unrelated layer video DOM/currentSrc/currentTime remain untouched.

## Crash/stability test

Because earlier builds produced GTK `Not Responding`, run a 30-minute local soak:

- both videos looping;
- Next/Random periodically;
- change selected layer repeatedly;
- navigate Workspace -> Diagnostics -> Workspace;
- change a test duplicate's folder twice;
- monitor app and WebKitWebProcess CPU/RSS;
- inspect journal/stdout for WebKit errors;
- verify no ffmpeg/ffprobe blocks the UI.

If a freeze occurs, do not blame geometry. Capture:

`pgrep -af 'allthings140|WebKitWebProcess|ffmpeg|ffprobe'`

and process CPU/memory plus frontend unhandled errors.

Fix any clearly related crash/reload bug found, but do not add unrelated features.

## Build/install

Build version 0.1.26 consistently in package.json/package-lock/Cargo.toml/Cargo.lock/tauri.conf.json.

Run:

- `node --check src/main.js`
- `npm ci`
- `npm run build`
- `cargo check --manifest-path src-tauri/Cargo.toml`
- Tauri release build

Build one final `.deb`, calculate SHA-256, install it on this PC, close v0.1.25 completely, and launch the normal installed v0.1.26 app.

If privilege authorization is required, open the normal authorization prompt and wait for me.

## Do not touch staging/prod publishing

Do NOT publish GREEN.
Do NOT modify production.

Frozen production baseline remains:

`4ca1a32e74c2b319fa8c7979b2e68e1486166a2d105c53158f2a417bf976ef32`

## Final handoff

Create:

`Projects/AllThings140Radio/dist/ALLTHINGS140/Visuals-App/v0.1.26-compositor-stabilization/`

Include:

- final .deb;
- SHA256SUMS.txt;
- full v0.1.26 source ZIP;
- WebKitGTK mask diagnostic result;
- 30-minute soak report;
- folder-isolation report;
- install/recovery notes.

Integrity-test the ZIP and open the folder with `xdg-open`.

End with:

`v0.1.26 COMPOSITOR STABILIZATION INSTALLED — WAITING FOR USER APPROVAL`

Most important: do not reintroduce the Stage CSS mask. The final local compositor is Stage Base BELOW Visual Screen. Both remain ordinary generic media layers using the already-working transform engine.
