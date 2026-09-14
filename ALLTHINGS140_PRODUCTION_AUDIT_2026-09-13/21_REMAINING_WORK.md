# Remaining Work

## High priority

1. **GitHub authentication** — run `gh auth login`, push 94 commits on `main`, reconcile branch strategy with Pages deploy branch naming
2. **Oracle RAM** — evaluate VM shape upgrade or service memory tuning
3. **Visuals workstation** — reconnect live compositor feed (currently fallback on GCP)

## Medium priority

4. Install pytest/PySide6/aiohttp in CI or dev venv for full test matrix
5. Export Cloudflare DNS with API token that has Zone:Read
6. Play Store production track — confirm latest 1.3.11 vc27 uploaded (local build newer than last documented Play report v1.3.5)
7. Retire or document stale Pages project `allthings140radio-online`

## Low priority

8. Fix `mcelog.service` or mask if hardware unsupported
9. Consolidate nested Wear source directories
10. Python 3.13 `audioop` deprecation — plan migration

## Not required (working as designed)

- Alert global stream injection remains OFF
- DJ SQLite users separate from Supabase listeners

