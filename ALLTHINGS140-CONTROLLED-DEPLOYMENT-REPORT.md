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
