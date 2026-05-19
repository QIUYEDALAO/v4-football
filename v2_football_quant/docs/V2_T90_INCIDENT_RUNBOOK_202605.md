# V2 T-90 Incident Runbook — 2026-05-19

| Incident | Failure? | Continue? | QQ? | Verified? | Action |
|----------|---------|-----------|-----|-----------|--------|
| T90_LOCK_WINDOW_WAIT | No | Wait for T-90 | No | No | Re-run at T-90 |
| T90_NO_BET_LOCKED | No | Yes, normal | No | No | Report reason |
| T90_BET_LOCKED | No | Yes, proof | No | No | Report only, no push |
| NO_MARKET | No | Yes | No | No | Wait for odds |
| ODDS_LOW (<2.00) | No | Yes | No | No | SKIP_LOW |
| ODDS_HIGH (≥2.90) | No | Yes | No | No | WATCH_HIGH |
| ALREADY_SELECTED | No | Yes | No | No | Skip duplicate |
| CHECKER_BLOCKED | Yes | Stop | No | No | Report to BOSS |
| LOCK_OWNER_CONFLICT | Yes | Stop | No | No | Audit conflict |
| MISSING_ODDS_D | Yes | Yes | No | No | Wait for market |
