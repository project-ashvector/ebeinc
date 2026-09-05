# ALLTHINGS140 pre-cleanup safety manifest

Created: 2026-09-04 (America/Los_Angeles)

## Protected Git state

- Canonical repository: `/home/ebmarah/Projects/AllThings140Radio`
- Branch at capture: `main`
- HEAD: `a52ce63898cf7ded7752d992b7a3d0a2f27e26fc`
- Safety branch: `safety/pre-consolidation-20260904`
- Live GitHub `main` at audit: `d6638c398fb51d7d7f316cb457cdc79bf7100555`
- Verified divergence: local ahead 79, behind 0
- Tracked modifications before consolidation: 51
- Staged files before consolidation: 0
- Individual untracked files before consolidation: 2,553 (93 collapsed status entries)

## External rollback snapshot

The complete snapshot is outside the repository at:

`/home/ebmarah/Backups/ALLTHINGS140/pre-consolidation-20260904`

It contains:

- `allthings140-committed.bundle` — all local Git refs and objects
- `unstaged.patch` — binary-capable tracked-worktree patch
- `staged.patch` — empty at capture (nothing was staged)
- `untracked-files.tar.gz` — all 2,553 Git-untracked files
- `untracked-files.txt` — exact untracked path inventory
- `git-status-porcelain-v2.txt` — machine-readable state
- `git-all-refs-log.tsv` — commit/ref provenance
- `local79-files.tsv` — paths touched by the local-only commit range
- `local79-secret-scan.tsv` — path/rule-only scan; no secret values
- `SHA256SUMS` — verified hashes for every snapshot artifact

Snapshot sizes at creation:

| Artifact | Bytes |
|---|---:|
| Untracked archive | 1,916,418,370 |
| Git bundle | 373,659,051 |
| Unstaged patch | 356,355 |

All entries in `SHA256SUMS` passed `sha256sum -c`. Snapshot permissions are owner-only; ignored secrets and signing keys were not copied into this report or printed.

## Sensitive material inventory

Values were never read into reports or printed.

| Path/type | Classification | Treatment |
|---|---|---|
| `discord-bot/.env` | Discord/runtime secrets | Ignored, local-only, do not commit |
| Android/Wear `.debug-keystore.jks` files (10 detected) | Debug signing keys | Ignored, local-only; not Play production authority |
| Oracle `/etc/allthings140radio/support.env` | Production payment/service secrets | Root-owned external config; path only audited |
| Oracle service environment/config under `/etc/allthings140radio` | Production credentials/config | External production authority; not copied to Git |
| Visuals host `/etc/allthings140-visuals/realtime.env` | Realtime secrets/config | External host authority; not copied to Git |
| Cloudflare tunnel configuration/credentials | Tunnel secret material | External host authority; contents not recorded |

High-confidence scanning of the 79 local commits and worktree found no private-key blocks or GitHub, AWS, Google, Slack, Stripe-live, or Discord-token shapes. Six generic hits were reviewed as runtime access-token assignment or random guest-password generation, not hard-coded credentials.

## Recovery rule

Do not remove this snapshot until GitHub synchronization is complete, production is revalidated, and the user accepts the consolidated state.
