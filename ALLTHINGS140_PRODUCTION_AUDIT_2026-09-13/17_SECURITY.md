# Security Audit (safe validation)

## Findings

| Severity | Finding | Location | Remediation |
|----------|---------|----------|-------------|
| INFO | Supabase publishable key in Android source | `SupabaseAuthClient.java` | Expected for client SDK |
| INFO | Temporary DJ password documented in DJ app UI | `tools/dj_app.py` | Operator onboarding only |
| WARN | 94 commits unpushed to GitHub | local git | Authenticate gh + push |
| WARN | Oracle VM low RAM | 946 MiB | Monitor; consider resize |
| PASS | Stream alert injection disabled | production ads.json | Maintained |
| PASS | Privileged entitlement tables locked | supabase migrations | Verified statically |
| PASS | Public gateway read-only | server.py | Verified |
| NOT TESTED | Full secret scan / penetration test | — | — |

No credentials printed. No secret rotation performed.

**Status: WARNINGS**
