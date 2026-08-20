# v0.1.19 Stage Content rebuild

This release intentionally removes the special Stage Overlay editor UI and replaces it with a second instance of the same direct-video transform model used by Visual Content.

## User-visible change

Layers now show:

1. **Stage Content** — reads only from `/home/ebmarah/Videos/at140radio/desktop visuals/stage/`, renders above Visual Content, and uses the same X/Y/Width/Height/Scale/Fit transform controls and the same eight drag handles as Visual Content.
2. **Visual Content** — unchanged, reads only from `/home/ebmarah/Videos/at140radio/desktop visuals/visuals/`.

The former special **Stage Transform** block, Stage-specific aspect lock, Match Visual Canvas, Reset to Native, Stage Zoom, pixel/canonical geometry controls, and wrapper geometry debug UI are not part of the active Stage editor anymore.

## Intentional exceptions

Stage Content still has two Stage-specific responsibilities only:

- it selects media from the Stage folder / stage media server routes;
- the existing Stage screen-opening mask is applied to it so the Visual Content layer underneath can show through the intended screen.

Neither responsibility changes the Stage Content transform rectangle.

## Acceptance

At the same transform values, Stage Content and Visual Content must have the same DOM geometry behavior. Dragging/resizing Stage Content must behave exactly like Visual Content.
