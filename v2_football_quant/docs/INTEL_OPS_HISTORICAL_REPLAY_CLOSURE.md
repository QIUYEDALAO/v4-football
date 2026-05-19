# INTEL-OPS Historical Replay — Closure
Phase: INTEL-OPS-0.2 | 2026-05-19

**Key fix**: V2 readonly runner now distinguishes CURRENT_WINDOW_CHECKER from HISTORICAL_FILE_SCAN.

**Modes**:
- READONLY_CURRENT: calls live window checker → evidence_mode=CURRENT_WINDOW_CHECKER
- READONLY_HISTORICAL_EVIDENCE_SCAN: scans files/logs/markers → evidence_mode=HISTORICAL_FILE_SCAN

**05/17-20 evidence**:
- 05/17: DAILY_POOL_FOUND (ledger, ran 14:23, BL=0)
- 05/18: DAILY_POOL_MISSING (P0 marker)
- 05/19: DAILY_POOL_MISSING (log no DAILY_POOL)
- 05/20: NO_EVIDENCE_FOUND

**Historical mode never calls live window checker as history.**
