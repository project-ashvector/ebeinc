# DJ Takeover System

## Code paths verified

- Submission via public POST endpoints (validated)
- `takeover_rows(True)` vs `False` separates approved vs pending
- Timezone field stored and tested in unit tests
- Logo/socials/rights fields in submit payload tests
- Invite token flow with expiry

## Production data

- 1 takeover record: **rejected** (not live)
- Schedule API returns empty approved list

## Approval gate

Unit test confirms pending status — no auto-publish on submit.

**Status: PASS** (no active takeover to observe live branding switch)
