# ALLTHINGS140 project consolidation report

## Current canonical local root

Path: `/home/ebmarah/Projects/AllThings140Radio`

Why authoritative: it is the sole current related Git repository; it has the newest coherent Git history, current Android 1.3.9/25 source, and production-exact hashes for the Oracle radio/Discord services and Visuals realtime deployment. Active deployment scripts, service paths, current Supabase migrations, website source, tests, and project continuity reports converge here.

## Git

| Field | Result |
|---|---|
| Branch | `main` |
| Local HEAD at snapshot | `a52ce63898cf7ded7752d992b7a3d0a2f27e26fc` |
| GitHub HEAD | `d6638c398fb51d7d7f316cb457cdc79bf7100555` |
| Ahead / behind | 88 / 0 after recording the sync result; the original 79 / 0 was verified against live GitHub in an isolated full clone |
| Upstream issue | Local `origin/main` was stale, but live GitHub is the same ancestor |
| Local-only commits | Original 79 valid descendant commits plus nine audit/consolidation/finalization commits across web/auth, radio/server, Supabase, Android, Visuals, and documentation |
| Stashes | none |
| Tracked modifications before | 51 |
| Individual untracked files before | 2,553 |
| Staged before | 0 |
| Tracked modifications after | 0 |
| Individual untracked files after | 2,529 intentionally retained historical/media/build/evidence candidates |
| Commits reconciled locally | 9 logical audit/consolidation/finalization commits, including this sync-result record |
| GitHub pushed | NO — normal push attempted; blocked because neither the HTTPS remote nor GitHub CLI has credentials on this workstation |
| Force push used | NO |

Why GitHub is behind: development continued locally on `main`; the configured GitHub branch did not change or diverge. A normal fast-forward is structurally possible. Current source changes were preserved in subsystem-specific commits. A normal push was attempted after the final secret scan, but failed before updating GitHub because no HTTPS or GitHub CLI credentials are configured.

The local-only range passed a high-confidence secret-pattern scan. Generic findings were code variables, not embedded credentials. Ignored `.env` and signing material remain outside Git.

## Databases

See `ALLTHINGS140-DATABASE-RECONCILIATION.md`.

| Database | Status |
|---|---|
| Oracle `/var/lib/allthings140radio/station.db` | PRIMARY_LIVE |
| Consolidated `cloud-primary.db` | BACKUP; logical content identical at capture |
| Smaller consolidated `station.db` | ARCHIVED_HISTORY; older 11-table/446-track state |
| Visuals `/var/lib/allthings140-visuals/realtime.db` | Separate PRIMARY_LIVE realtime/community state |

Database merge required: **NO**. Retired/deleted database: **NONE**.

## Oracle / remote production

Audited: **YES**, directly and read-only.

The Oracle broadcast server is active with its Drive, cache, Icecast, tunnel, Discord, health/backup, admission, and off-host backup services/timers. Important deployed source hashes match local current files. The database and media mount were independently inspected. No unique newer Oracle source was found; Oracle remains authoritative for runtime state/config and the live database.

The separately deployed Visuals host was also audited. Its source matches local dirty-tree source exactly; its live WAL database and daily backups are host authority. The host name in old documents calling it “Oracle VM2” is historical; direct SSH currently reaches the configured Google Cloud IP.

## Google Drive

Audited: **YES**, through the live Oracle rclone mount.

Unique current source found: **NO**. Unique media found: **YES — production music master**. Unique backups found: **YES — 26 encrypted state packages**. Any source newer than local: **NO**.

Final classification: audio files `MEDIA_MASTER`; encrypted state packages `BACKUP`; no deletions performed.

## Project copies

Meaningful candidate groups found:

1. Canonical current Git repo — `Projects/AllThings140Radio`
2. Active separate Mic app — `Projects/ALLTHINGS140-Mic`
3. Android review package — `Projects/ALLTHINGS140-RADIO-ANDROID-LATEST-REVIEW-PACKAGE` (historical vs current 1.3.9)
4. Green Room v0.1.40 source bundle at home root (historical)
5. `Projects/ARCHIVE/ALLTHINGS140-Radio` (58 GB historical/archive tree)
6. `Backups/ALLTHINGS140` and `.allthings140-backups` (rollback/backups)
7. Downloads Wear source packages (historical predecessors)
8. Current external runtime/config/media/report/build locations under `.config`, `.local/share`, Documents, Videos, Pictures, Music, and Releases

The deep name scan produced 101 candidate directories after pruning caches, the canonical repo, and the previous migration consolidation; most are nested generated/package directories rather than independent sources.

Classification totals at tree-group level: canonical 1; active components 1 (Mic) plus external runtime resources; historical/archive/backup groups 5; unknown 1 (`gilfoyle_rescue_builder` rescue copy, retained for review). No originals were moved or deleted.

## Cleanup and repository boundaries

The existing `.gitignore` correctly excludes dependency/build trees, caches, archives, DBs, private configs, credentials, keys, and release packages. Historical Watch source chains, rollout copies, media masters, evidence recordings, recovery snapshots, and build outputs remain preserved and uncommitted. Four unrelated APKs are already tracked under `downloads/`; removing them from history was not attempted.

Files/folders archived during this pass: rollback snapshot only; originals unchanged. Generated files removed: 0. Duplicate builds removed: 0. Caches removed: 0. Space reclaimed: 0. This conservative result is deliberate because production and rollback preservation outrank space recovery.

## Source-of-truth matrix

| Component | Local | GitHub | Oracle/remote | Drive | Authoritative |
|---|---|---|---|---|---|
| Website | Current and production-matching | 79+ commits behind | Cloudflare deploy matches key local assets | none | Local source; Cloudflare runtime |
| Android listener | 1.3.9/25, builds pass | behind | Play Internal 1.3.7/23 | none | Local source; Play for deployed release |
| Mic/PTT app | Separate current local tree | not established | service integration only | none | `Projects/ALLTHINGS140-Mic` |
| Radio server/AutoDJ | Production-exact 0.8.0 | behind | running exact local hash | none | Local source; Oracle runtime |
| Icecast | templates/docs | behind | live config/service | none | Oracle config/runtime |
| Alert/auth/account | current dirty source + Supabase migrations | behind | edge/runtime integrations | none | Local migrations/source; Supabase runtime data |
| Visuals desktop | 0.2.1 source; installed 0.1.43 | behind | workstation runtime | media external | Local source |
| Visuals realtime | production-exact dirty source | behind | running exact local hash + live DB | none | Local source; remote runtime DB |
| Green Room/public Visuals | current dirty source | behind | Cloudflare/Visuals host runtime | media external | Local source; deployed runtime |
| Discord radio bot | production-exact source | behind | active Oracle service | none | Local source; Oracle secrets/runtime |
| Supabase | seven current migrations untracked | behind | hosted schema/data not mutated | none | Local migrations + hosted runtime |
| Catalog/music | manifests/tools | behind | live DB/cache/mirror | 2,483-file media master | Oracle DB + Drive media |
| Signing configuration | references only | must remain absent | Play signing/deployment state | none | Secure external material / Play |
| Deployment scripts/docs | current local | behind | deployed copies where applicable | none | Local repo |

## Validation

- Visuals Node contract test: PASS
- Python syntax parse (39 files): PASS
- JavaScript syntax and JSON manifests: PASS
- Android `testReleaseUnitTest bundleRelease`: PASS (53 tasks; lint-vital and signing included)
- Python pytest suite: NOT RUN because no project pytest environment is reproducible on this workstation; system Python lacks pytest
- Website/status/stream: PASS
- Oracle radio/DB/services: PASS
- Visuals realtime/DB/backup timer: PASS
- Production restarts or deployments: none

## Final status

| Question | Answer |
|---|---|
| Project consolidated | **YES WITH WARNINGS — current source is canonical and committed; historical/untracked archive classification remains** |
| GitHub current | **NO — 84 commits behind; push withheld** |
| Database authority clear | **YES** |
| Oracle audited | **YES** |
| Google Drive audited | **YES** |
| Production unbroken | **YES** |
| Rollback available | **YES** |

### Remaining review gates

1. Decide whether large untracked media belongs in external media-master storage or a documented release archive; do not put it into ordinary Git.
2. Choose the canonical Wear source from nested v0.3.x/v1.0.x chains, then archive predecessors without deleting them.
3. Recreate/document a Python test environment and run the 37-file suite.
4. Resolve the Visuals runtime/`VERSION.txt` mismatch.
5. Re-scan the final local range and fast-forward GitHub normally; never force-push.
6. Independently verify hosted Supabase schema/version if credentials and authority are provided; no production data was changed.

Until those gates are closed, the safe status is **COMPLETE WITH WARNINGS / REVIEW REQUIRED**, not a falsely clean repository.
