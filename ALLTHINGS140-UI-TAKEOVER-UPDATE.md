# ALLTHINGS140 Radio UI / Takeover Update

Date: 2026-09-05

## Changes

- Restored a Community takeover application section. It is intentionally routed through the existing server `takeovers` table and DJ approval queue, so public requests do not publish directly.
- Added live-mix vs recorded-mix selection, future schedule fields, timezone, recorded-mix URL/length/rights confirmation, visuals opt-out, transparent-logo-friendly PNG/WebP upload, social links, and contact email.
- DJ-created artist form links are now one-time links with no expiry (`expires_at=0`); they remain revocable and old expiring links continue to work.
- Removed the SoundCloud Discovery tab from the desktop DJ UI. SoundCloud review endpoints/configuration remain intact for compatibility and catalog metadata.
- Moved Station Ads list refresh/probing off the Tk UI thread. The existing server-side ad playback and account-aware alert paths were not changed.
- Increased Support modal width and constrained overflow so desktop and mobile dialogs do not create a horizontal scrollbar.
- Bumped the main service-worker shell cache and added the new takeover script.

## Safety boundaries

No production service, database, Oracle host, Cloudflare route, Supabase data, stream, AutoDJ process, or account-alert logic was restarted or modified. Existing source and database safety snapshots remain available. The new public endpoint is rate-limited and requests remain pending until DJ approval.

## Verification

- `python3 -m py_compile tools/server.py tools/dj_app.py`
- `node --check radio/takeover-apply.js`
- `node --check radio/_worker.js`
- Visuals app tests: 2 passed
- `git diff --check`

Deployment is intentionally not performed in this pass; publish the Worker/static assets and restart the server only through the existing controlled deployment procedure after a staging/public smoke test.
