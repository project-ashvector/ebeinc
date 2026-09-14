# Repairs Performed

## Repair 1 — Stale radio regression tests

### ISSUE
`tests/test_radio_system.py` failed because:
- `/api/public/alert-catalog` is served by Cloudflare Pages worker, not Python `PublicGatewayHandler`
- Test asserted hardcoded service worker cache `allthings140-radio-v63` while production/local use `v74`

### ROOT CAUSE
Tests not updated after alert catalog moved to static assets + `_worker.js`, and after SW cache bump.

### CHANGE
- `tests/test_radio_system.py` — updated alert catalog test to assert gateway 404 + validate `radio/assets/client-alerts/manifest.json` and worker flags
- `tests/test_radio_system.py` — read `radio/sw.js` and `radio/_worker.js` dynamically

### BACKUP
N/A (test-only change)

### VALIDATION
```
/tmp/at140-pytest/bin/python -m pytest tests/test_radio_system.py -q
# 20 passed
node tests/test_account_alert_entitlement.mjs
# PASS
```

### RESULT
**PASS**

---

## Repair 2 — Oracle SSH operator access

### ISSUE
Production Oracle VM only accepted `opc@...` with explicit key path; no `~/.ssh/config` entry.

### ROOT CAUSE
SSH config only documented GCP visuals host, not Oracle Tailscale host.

### CHANGE
- `~/.ssh/config` — added `Host allthings140radio-server allthings140-oracle`
- Backup: `~/.ssh/config.before-audit-20260913-220100Z`

### VALIDATION
```
ssh allthings140radio-server hostname
# allthings140radio-vnic
```

### RESULT
**PASS**
