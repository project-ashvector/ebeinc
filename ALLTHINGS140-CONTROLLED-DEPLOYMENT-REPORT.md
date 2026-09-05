# ALLTHINGS140 Controlled Deployment Report

Date: 2026-09-05

## Commits reviewed

`d94ae1b`, `65ae914`, `d543084`, and `6529712` were inspected. They affect the Community/static UI, Worker route allow-list, takeover schema/API, DJ UI, support CSS, and deployment documentation. No alert-entitlement implementation, Icecast, AutoDJ, signing, secret, or unrelated database file changes were present. The 69 pre-existing untracked entries were not staged, modified, or deployed.

## Deployment result

The tracked `radio/` artifact was deployed to Pages project `ebeinc` at `6b171130.ebeinc-uqt.pages.dev`. Public smoke testing found that the new form endpoint returned `Guest link is invalid` because its required Oracle server/API changes had not been deployed. No Oracle change was authorized in this pass. The Pages site was immediately rolled back using the pre-change tracked artifact; rollback deployment URL: `b659bc01.ebeinc-uqt.pages.dev`.

| Check | Result |
|---|---|
| Website after rollback | PASS |
| Takeover form | NOT DEPLOYED (backend dependency absent) |
| DJ approval queue | NOT CHANGED |
| Auto-publish prevention | NOT CHANGED |
| Non-expiring one-time links | NOT DEPLOYED |
| Link revocation | NOT CHANGED |
| SoundCloud Discovery removal | LOCAL ONLY |
| Station Ads responsiveness | LOCAL ONLY |
| Support modal | LOCAL ONLY |
| Visuals tests | PASS (2 tests) |
| Radio/status | PASS; status online/autodj, stream returned bytes |
| Production interruption | NO |
| Alert entitlement code modified | NO |
| 69 untracked items modified | NO |
| Rollback available | YES |

## Rollback reference

The pre-change website artifact was recreated from `d94ae1b^` with `git archive`, so no untracked material entered either deployment. The current local HEAD remains `6529712a20334b677eb0a260d32fafb6082ae67e`. The live site is restored to the pre-change website state. Oracle, databases, AutoDJ, Icecast, Discord relay, and Visuals services were not restarted or modified.

## Required next step

Deploy the compatible `tools/server.py` migration/API to Oracle through its backup-first service procedure, validate the new endpoint and database migration in a controlled window, then redeploy the tracked website artifact. Until then, the four commits remain validated local changes but are not production-active.

## Coordinated Oracle API + frontend deployment (2026-09-05)

### Root cause of first deployment failure

The first frontend called `POST /api/public/takeover-application`; the pre-change Oracle server did not implement that route and its fallback returned `Guest link is invalid`. The matching API now validates the public payload, writes the authoritative `/var/lib/allthings140radio/station.db` `takeovers` row as `pending`, and leaves publication to the authenticated DJ approval endpoint.

### Oracle

- Host: `allthings140radio-vnic` (`64.181.235.228`)
- Active service: `allthings140radio-server.service`
- ExecStart: `/usr/bin/python3 /opt/allthings140radio-server/server.py`
- API ports: private `14080`, public gateway `14082`
- Database: `/var/lib/allthings140radio/station.db` (unchanged)
- Rollback backup: `/opt/allthings140radio-server/server.py.before-coordinated-20260905T171732Z`
- Backup SHA-256: `6a9ad3d80cb46e731960cdcbf5d0601a0b5258b4959741648f4aa92e2b96b448`
- Backend deployed: YES; API-only service restart: YES; radio interruption: NO observed

### Backend tests

Health PASS; takeover submission PASS; approval-queue insertion PASS; auto-publish prevention PASS; live/recorded fields PASS; schedule/timezone/socials/visuals/rights validation PASS. A uniquely marked test row was confirmed `pending`, absent from the public schedule, and removed.

Non-expiring/one-time/revocable link semantics are implemented in code; no production invite was consumed during testing.

### Website and production

- Matching artifact deployed: `733533d0.ebeinc-uqt.pages.dev` (Pages project `ebeinc`, branch `main`)
- Homepage, Community, Visuals, and Green Room: HTTP 200
- Public form markers and fields present; public test submission succeeded and was cleaned up
- Status: `online=true`, `mode=autodj`
- Oracle health after deployment: AutoDJ running, Icecast online, cache healthy, silence monitor healthy
- Stream returned audio bytes (curl timeout is expected for a continuing stream)
- Visuals tests: 2 passed
- Alert-entitlement code: NOT modified
- Global alert injector: NOT modified
- 69 untracked entries: NOT modified
- Database reconciliation: NOT performed
- Android/signing: NOT modified

Final coordinated result: BACKEND + FRONTEND COMPATIBLE = PASS; NEW FEATURES PRODUCTION ACTIVE = YES; PRODUCTION RADIO HEALTHY = PASS; ROLLBACK AVAILABLE = YES.
