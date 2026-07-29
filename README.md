# EBE INC — GitHub Pages Hub v2.0.0

EBE INC is Cody Richenberg’s central hub and online résumé. It connects:

- **BitByt3s** — apps, games, Linux tools, web development, IT, networking, and cybersecurity work
- **Ebmarah** — music production, audio engineering, mixing, mastering, and the SoundCloud catalog
- **EBE Designs** — practical digital products at `https://ebedesigns.online/`
- **EBE Comics** — original comic publishing and Android reading
- **Cody Richenberg’s résumé** — a printable online résumé at `resume.html`

## Publish with GitHub Pages

1. Create a GitHub repository such as `ebe-inc`.
2. Extract the ZIP and upload **all files and folders from the ZIP root** to the repository root. Do not upload the ZIP itself as the website.
3. Commit the files to the `main` branch.
4. In the repository, open **Settings → Pages**.
5. Under **Build and deployment**, choose **Deploy from a branch**.
6. Select `main` and `/(root)`, then save.

GitHub will publish the site at a URL similar to:

`https://YOUR-USERNAME.github.io/ebe-inc/`

For an account-level site, name the repository `YOUR-USERNAME.github.io`.

## Custom domain

After the GitHub Pages URL works, add a domain in **Settings → Pages → Custom domain** and configure the matching DNS records with the domain provider. Do not create a `CNAME` file until the final domain is chosen.

## Main files

- `index.html` — EBE INC hub, company divisions, projects, skills, and contact
- `resume.html` — Cody Richenberg’s printable online résumé
- `music.html` — Ebmarah catalog and professional audio profile
- `styles.css` — responsive purple EBE INC visual system
- `app.js` — navigation, filtering, and reveal interactions
- `downloads/` — completed APK files only
- `.nojekyll` — tells GitHub Pages to publish the static site directly
- `404.html` — custom not-found page

## Public-source warning

A public GitHub repository allows visitors to view and download the website files from GitHub. The **website interface** offers only finished APK downloads, but repository files cannot be hidden inside a public repository. `LICENSE.txt` states that the work remains proprietary and all rights are reserved.

## Local Zorin preview

```bash
chmod +x "START SITE - ZORIN.sh"
./"START SITE - ZORIN.sh"
```

Stop with `Ctrl+C` or:

```bash
./"STOP SITE - ZORIN.sh"
```
