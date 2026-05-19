# OPS Daily Strong Monitoring — Issue List 2026-05-20

| # | Weakness | Fix |
|---|----------|-----|
| 1 | V4_C3 uses C>=0 | → C==3 |
| 2 | V4_SKIP2 uses SKIP>=0 | → SKIP==2 |
| 3 | no_stale_0517 hardcoded True | → read real markers |
| 4 | Intel real markers STRENGTHENING | → read real markers |
| 5 | OPS heartbeat STRENGTHENING | → read real markers |
| 6 | api_snapshot not read | → read bundle/status |
| 7 | source_health not read | → read per-source |
| 8 | task_status not read | → read task_status_*.json |
| 9 | logs not read | → read recent logs |
| 10 | invalid_sources not read | → read index |
| 11 | V4 scan 5 windows not per-window | → per-window check |
| 12 | production_evidence not per-window | → per-window verify |
| 13 | fallback_qq_brief not per-window | → per-window exclude |
| 14 | OPS heartbeat html not read | → read html/status |
| 15 | D13/V33/HOURLY hardcoded | → read from markers |
| 16 | stale dashboard hardcoded | → read mtime/hash |
| 17 | issue list vs report conflict | → unify READY/STRONG |
