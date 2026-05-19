# OPS Rolling Day Boundary + Next Window — Issues 2026-05-20

| # | Issue | Fix |
|---|-------|-----|
| 1 | 41/43 vs 42/43 number conflict | → unify to PASS/total/WARN format |
| 2 | ops_date = natural day | → add scan_date/review_date split |
| 3 | review_date at midnight | → latest_completed fallback |
| 4 | V4 scan windows dynamic paths | → verify all 5 |
| 5 | logs dynamic date | → verify |
| 6 | task_status dynamic date | → verify |
| 7 | heartbeat dynamic date | → verify |
| 8 | source health dynamic | → verify |
| 9 | late 01:20 PENDING/WARN | → PENDING (not yet due) |
| 10 | next window identification | → calculate next due window |
| 11 | fallback_qq_brief exclusion | → per-window |
| 12 | V4 QQ gate blocked | → A=0,B=0 |
