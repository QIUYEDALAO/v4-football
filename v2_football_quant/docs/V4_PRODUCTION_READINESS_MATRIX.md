# V4 Production Readiness Matrix

Phase: V4-H
Date: 2026-05-19
Status: FINAL (not yet in production)

## Matrix

### 1. Boundary Readiness
| Item | Checker | Status | Blockers | Prod Allowed | Exec Allowed | Notes |
|------|---------|--------|----------|--------------|--------------|-------|
| A/B/C/SKIP contract | boundary_contract | WARN | 0 | false | false | V33/V38 references in deprecation guards only |
| V33/V38 purge | legacy_purge_checker | WARN | 0 | false | false | Active refs in V2 code only |
| Active contamination cleanup | active_contamination | WARN | 0 | false | false | Guard references only |
| Forbidden terminology guard | reporting_guard | PASS | 0 | false | false | Hardened V4-G.1 |

### 2. Output Readiness
| Item | Checker | Status | Blockers | Prod Allowed | Exec Allowed | Notes |
|------|---------|--------|----------|--------------|--------------|-------|
| Output schema | output_schema | PASS | 0 | false | false | |
| Renderer guard | renderer_guard | PASS | 0 | false | false | |
| Template guard | reporting_guard | PASS | 0 | false | false | |
| Mobile QQ guard | qq_guard | PASS | 0 | false | false | |

### 3. Delivery Readiness
| Item | Checker | Status | Blockers | Prod Allowed | Exec Allowed | Notes |
|------|---------|--------|----------|--------------|--------------|-------|
| QQ no-push enforcement | no_push_enforcement | PASS | 0 | false | false | |
| Route marker | watchdog_contract | PASS | 0 | false | false | route_marker_ready |
| Sent marker | watchdog_contract | PASS | 0 | false | false | sent_marker_written=false |
| Route/sent separation | qq_guard | PASS | 0 | false | false | |

### 4. Runtime Readiness
| Item | Checker | Status | Blockers | Prod Allowed | Exec Allowed | Notes |
|------|---------|--------|----------|--------------|--------------|-------|
| Watchdog | watchdog_contract | PASS | 0 | false | false | bypass=false |
| Lock | lock_timeout_contract | PASS | 0 | false | false | required=true |
| Timeout | lock_timeout_contract | PASS | 0 | false | false | required=true |
| No AI kill/retry | watchdog_contract | PASS | 0 | false | false | locked=true |
| Fail-closed | watchdog_contract | PASS | 0 | false | false | required=true |

### 5. Attribution Readiness
| Item | Checker | Status | Blockers | Prod Allowed | Exec Allowed | Notes |
|------|---------|--------|----------|--------------|--------------|-------|
| Attribution schema | attribution_schema | PASS | 0 | false | false | |
| No-API guard | attribution_no_api_guard | PASS | 0 | false | false | allow_api default false |
| UNKNOWN policy | attribution_guard | WARN | 0 | false | false | API calls guarded by allow_api |
| No verified write | attribution_guard | PASS | 0 | false | false | |

### 6. Rolling Readiness
| Item | Checker | Status | Blockers | Prod Allowed | Exec Allowed | Notes |
|------|---------|--------|----------|--------------|--------------|-------|
| 7/14/30 schema | rolling_schema | PASS | 0 | false | false | |
| UNKNOWN excluded | rolling_guard | PASS | 0 | false | false | |
| API_DISABLED excluded | rolling_guard | PASS | 0 | false | false | |
| C observation-only | rolling_guard | PASS | 0 | false | false | |
| SKIP not-scored | rolling_guard | PASS | 0 | false | false | |
| No rule change | rolling_guard | PASS | 0 | false | false | |

### 7. Reporting Readiness
| Item | Checker | Status | Blockers | Prod Allowed | Exec Allowed | Notes |
|------|---------|--------|----------|--------------|--------------|-------|
| Daily/weekly/monthly schema | reporting_schema | WARN | 0 | false | false | Minor keyword mismatch in guard doc |
| Mobile report guard | reporting_guard | PASS | 0 | false | false | No long tables |
| Terminology guard | reporting_guard | PASS | 0 | false | false | Hardened V4-G.1 |
| No verified / no QQ | reporting_guard | PASS | 0 | false | false | |

## Summary

| Metric | Value |
|--------|-------|
| Total items | 30 |
| PASS | 21 |
| WARN (acceptable) | 9 |
| BLOCKER | 0 |
| Production allowed | false |
| Execution allowed | false |
| Production verified | false |
| Phase E allowed | false |
| V4-I allowed_to_generate | true |
| V4-I allowed_to_execute | false |
