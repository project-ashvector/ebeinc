# Git / GitHub Audit

| Field | Value |
|-------|-------|
| Repository | `https://github.com/project-ashvector/ebeinc.git` |
| Local path | `/home/ebmarah/Projects/AllThings140Radio` |
| Current branch | `fix/visuals-24-7-compositor` @ `f4e8055` |
| `main` | `a41e941` — **94 commits ahead** of `origin/main`, 0 behind |
| Remote fetch | Succeeded (new feature branches discovered) |
| Working tree | Dirty (visuals changes + untracked assets) |

## Branches of note

- `main` — coordinated deployment record + 94 unpushed commits
- `fix/visuals-24-7-compositor` — active visuals HLS work (Pages prod commit `f4e8055`)
- `fix/android-auto-regression` — Android Auto repair (`d5d8318`)

## GitHub CLI

**BLOCKED** — `gh auth status` reports not logged in. Could not inspect Actions, PRs, security alerts, or remote branch protection.

## Hygiene notes

- No secrets scan completed on full history this session
- Large zip binaries in repo root (review packages) — consider Git LFS / release artifacts only
- `.gitignore` appears functional; build outputs generally untracked

## Recommendation

Run `gh auth login` and push `main` (or split into PRs) to restore GitHub as source-of-truth backup.
