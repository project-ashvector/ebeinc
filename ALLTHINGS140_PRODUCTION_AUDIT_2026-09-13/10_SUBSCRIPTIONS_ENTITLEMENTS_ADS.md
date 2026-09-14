# Subscriptions, Entitlements, Alert Ads

## Expected behavior (verified in code + production flags)

| Account type | Alert ads |
|--------------|-----------|
| REGULAR | enabled |
| PLUS | suppressed |
| RESIDENT | suppressed |
| PARTNER/SPONSOR | suppressed |
| MODERATOR | suppressed |
| ADMIN | suppressed |

## Production flags (live)

```
server_stream_alert_injection_enabled: false
client_account_alerts_enabled: true
```

## Injection paths audited

| Path | Status |
|------|--------|
| AutoDJ `mix_ad()` → Icecast | FAIL-CLOSED for client alerts (`shared_stream_asset_allowed`) |
| Cloudflare worker global injection env | OFF |
| Web `persistent-shell.js` scheduler | Server RPC before play; blocks entitled |
| Android `RadioService` second player | `loadRole` before `startAuthorizedAlert` |
| WebSocket station events | not used for alert audio |

## Static tests

- `node tests/test_account_alert_entitlement.mjs` → **PASS**
- Production `ads.json`: 29 promotional_alert with client_delivery, 3 uncategorized

## Prior global injection bug

**REMEDIATED** — stream injection disabled; client-only delivery with entitlement gates.

**Status: PASS**
