# Backend API Audit

- **Running binary:** `/usr/bin/python3 /opt/allthings140radio-server/server.py`
- **VERSION:** 0.8.0
- **Hash match:** local `tools/server.py` identical to production
- **Service user:** `allthings140radio`
- **Working directory:** `/var/lib/allthings140radio`
- **Public gateway:** `PublicGatewayHandler` on loopback :14080 (read-only + validated POST)
- **Private handler:** full DJ/admin API on separate port (not exposed via tunnel)

## API smoke tests

| Endpoint | Result |
|----------|--------|
| `/api/public/status` | 200, online autodj |
| `/api/public/schedule` | 200 |
| `/api/public/alert-catalog` (via Pages) | 200, injection off |
| POST `/api/public/takeover-interest` empty | 400 validation |

## Auth middleware

Session tokens for DJ `users` table (2 accounts: admin, manager). Listener accounts via Supabase JWT on worker-proxied routes.

**Status: PASS**
