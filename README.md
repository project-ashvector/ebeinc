# EBE INC Hub v2.2.0 — Single-Page GitHub Build

This is the GitHub Pages–ready EBE INC hub and Cody Richenberg online résumé.

## What changed

- All internal tabs now run inside `index.html`.
- The visible address stays `https://ebeinc.online/` while visitors switch between Hub, Projects, Capabilities, Music, About, Contact, and Résumé.
- The selected tab is remembered for the current browser session without adding a path, hash, or query string.
- `music.html`, `resume.html`, and `404.html` redirect old links back to the clean root domain.
- The résumé can still be printed or saved as PDF from its tab.

## GitHub upload

Extract the ZIP and upload all files directly to the root of the `project-ashvector/ebeinc` repository. Uploading the included redirect files is important because it replaces the previous separate Music and Résumé pages.

Keep these files at the repository root:

- `index.html`
- `styles.css`
- `app.js`
- `CNAME`
- `.nojekyll`

The `CNAME` file must contain exactly:

```text
ebeinc.online
```

Public downloads remain limited to completed APK files. Source packages are not offered through the website interface.


## v2.2.0 mobile polish

- Rebuilt the phone navigation as a touch-friendly two-column menu with backdrop, scroll lock, Escape support, and an animated close state.
- Improved mobile typography, spacing, project-card proportions, filters, download buttons, résumé readability, and safe-area behavior.
- Preserves the single-page clean-domain navigation at `https://ebeinc.online/`.
