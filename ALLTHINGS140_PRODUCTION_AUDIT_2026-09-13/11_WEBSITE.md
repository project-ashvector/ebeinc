# Website Audit

- **URL:** https://allthings140radio.online
- **Deploy:** Cloudflare Pages `ebeinc` @ `f4e8055`
- **app.js:** byte-identical local vs production
- **sw.js:** `allthings140-radio-v74`, byte-identical
- **Routes tested:** `/` 200, `/visuals` 200, `/api/public/status` 200

## Architecture

- PWA with persistent shell (`persistent-shell.html`)
- Service worker network-first for JS/CSS
- APIs never cached by SW

## Mobile

HTTP 200 on key routes; layout evidence screenshots exist in repo (not re-captured).

**Status: PASS**
