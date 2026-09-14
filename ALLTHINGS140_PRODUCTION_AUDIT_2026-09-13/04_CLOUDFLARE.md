# Cloudflare Audit

**Account:** ebmarahofficial@gmail.com (wrangler OAuth)  
**Account ID:** `46d84d23bf88af9f1c563ebbb3b6124b`

## Pages projects

| Project | Domains | Last deploy |
|---------|---------|-------------|
| `ebeinc` | allthings140radio.online, ebeinc.online, ebeinc-uqt.pages.dev | 17h ago — `f4e8055` |
| `allthings140-visuals-green` | allthings140-visuals-green.pages.dev | 1 week ago |
| `allthings140radio-online` | allthings140radio-online.pages.dev | 3 weeks ago (likely stale) |

## Verified live behavior

- `https://allthings140radio.online/` → 200
- `https://allthings140radio.online/api/public/status` → proxied to Oracle public API (200)
- `https://allthings140radio.online/api/public/alert-catalog` → worker + static manifest (injection flags false/true)
- `https://stream.ebeinc.online/live.mp3` → 200 audio/mpeg via Cloudflare

## DNS API

**PARTIAL** — Zone lookup succeeded for `allthings140radio.online` (zone id `5af6587ed022402d109c0344d44a1b79`). Full DNS record export via API returned 403 with wrangler OAuth token (insufficient scope or token type). No DNS changes made.

## Worker configuration

`radio/_worker.js` proxies public GET/POST routes to `status.ebeinc.online` and serves client alert catalog from `/assets/client-alerts/`. Env flags:
- `SERVER_STREAM_ALERT_INJECTION_ENABLED` — must be `"true"` to enable global injection (default off)
- `CLIENT_ACCOUNT_ALERTS_ENABLED` — defaults on unless `"false"`

## TLS / caching

- TLS terminated at Cloudflare (HTTP/2 observed)
- Stream: `cf-cache-status: BYPASS` on Icecast HEAD
- Alert catalog: `Cache-Control: public, max-age=60`

## Status

**PASS** (with DNS export BLOCKED)
