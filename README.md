# EBE INC Hub v2.3.1 — Single-Page GitHub Build

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


## v2.3.0 mobile polish

- Rebuilt the phone navigation as a touch-friendly two-column menu with backdrop, scroll lock, Escape support, and an animated close state.
- Improved mobile typography, spacing, project-card proportions, filters, download buttons, résumé readability, and safe-area behavior.
- Preserves the single-page clean-domain navigation at `https://ebeinc.online/`.


## v2.3.0 fresh responsive redesign

- Eliminates mobile horizontal overflow and clipped text/buttons.
- Removes the mobile sticky-header overlap.
- Rebuilds mobile hero actions, category chips, console card, project filters, and resume spacing.
- Refreshes desktop navigation, hero balance, cards, metrics, section rhythm, and glass treatment.
- Preserves the single-page clean URL behavior and GitHub Pages custom-domain setup.


## v2.3.1 EBE Comics download update

- Replaces the previous EBE Comics reader download with **EBE Comics v2.13.2 Phone-to-Studio Sync**.
- Updates the public APK filename, project version label, feature description, and SHA-256 checksum.


## v2.3.2 EBE Comics release download fix

The EBE Comics v2.13.2 APK is distributed through a GitHub Release because the file is larger than GitHub's 25 MiB browser-upload limit for repository files.

Required release:

- Tag: `ebe-comics-v2.13.2`
- Asset: `EBE-Comics-v2.13.2.apk`

The site download buttons point to:

`https://github.com/project-ashvector/ebeinc/releases/download/ebe-comics-v2.13.2/EBE-Comics-v2.13.2.apk`
