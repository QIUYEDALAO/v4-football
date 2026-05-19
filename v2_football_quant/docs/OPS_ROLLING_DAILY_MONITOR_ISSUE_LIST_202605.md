# OPS Rolling Daily Monitor — Remaining Issues 2026-05-20

| # | Issue | Fix |
|---|-------|-----|
| 1 | Checker date hardcoded 20260519 | → dynamic ops_date |
| 2 | late window: no log but could be PENDING | → time-based PENDING/WARN/BLOCKER |
| 3 | 5-window status not per-window timely | → per-window scheduled_time check |
| 4 | OPS heartbeat not fully read | → read html + status |
| 5 | V4/OPS logs not fully included | → add v4 logs, ops logs |
| 6 | task_status date filter needed | → read by ops_date |
| 7 | api_snapshot modules not listed | → per-module check |
| 8 | invalid_sources count from real index | → read real index |
| 9 | stale check should use hash/mtime | → real mtime check |
| 10 | V4 QQ not enabled flag | → explicitly check |
| 11 | future A/B>0 only gate | → document |
