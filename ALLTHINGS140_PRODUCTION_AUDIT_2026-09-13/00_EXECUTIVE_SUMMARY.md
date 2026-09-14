# ALLTHINGS140 Production Audit — Executive Summary

**Audit date:** 2026-09-13 (America/Los_Angeles) / 2026-09-14 UTC execution  
**Auditor:** Autonomous production audit session  
**Overall health:** **HEALTHY WITH WARNINGS**

## Bottom line

ALLTHINGS140 Radio is **live, streaming, and serving traffic correctly**. The Oracle broadcast plane, Cloudflare website, public status API, Icecast/AutoDJ chain, database integrity, and account-aware alert architecture are verified operational. Production `server.py` is **byte-identical** to the authoritative local source.

Primary risks are **operational**, not outage-level:

1. **GitHub sync blocked** — `main` is **94 commits ahead** of `origin/main`; `gh` CLI not authenticated on this workstation.
2. **Oracle VM memory pressure** — ~946 MiB RAM, ~558 MiB used; swap in use (363 MiB).
3. **Visuals workstation offline** — GCP realtime healthy but `workstationLive.active=false`, source `fallback`.
4. **Test harness gaps** — Hub/GUI tests need PySide6/aiohttp; fixed stale radio unit tests during audit.

## Repairs performed (safe)

| # | Issue | Action | Result |
|---|-------|--------|--------|
| 1 | Stale unit tests referenced removed gateway route + old SW cache version | Updated `tests/test_radio_system.py` | 20/20 PASS |
| 2 | No SSH alias for Oracle production (`opc` user) | Added `allthings140radio-server` to `~/.ssh/config` (backup created) | PASS |

## Critical findings

**0 critical production outages identified.**

## High findings

| ID | Finding | Status |
|----|---------|--------|
| H1 | 94 unpushed local commits on `main` | OPEN — GitHub auth blocked |
| H2 | Low RAM on Oracle VM (946 MiB) | MONITOR |
| H3 | `mcelog.service` failed (hardware logging) | LOW impact |

## Regression snapshot

| Check | Result |
|-------|--------|
| Homepage HTTPS | PASS |
| Public status API | PASS |
| Stream MP3 bytes | PASS |
| AutoDJ online | PASS |
| DB integrity | PASS |
| Alert stream injection OFF | PASS |
| Client alert catalog | PASS |
| Android unit tests | PASS |
| Android Auto contract script | PASS |
| Account alert static test (node) | PASS |

See numbered reports in this directory for full evidence.
