# V4 Watchdog / State / Lock Contract

Phase: V4-D
Date: 2026-05-19
Status: FINAL (not yet executed in production)

## 1. Watchdog Contract

### Production Pathway
- ✅ V4 formal pipeline MUST pass through watchdog
- ✅ Watchdog reports status only (does not execute kills)
- ✅ Watchdog failure MUST be fail-closed (stop, report to user)
- ✅ Watchdog NOT PASS → NO route allowed
- ✅ Watchdog NOT PASS → NO sent allowed
- ✅ Watchdog NOT PASS → NO PRODUCTION_VERIFIED allowed

### AI Governance
- ✅ NO AI kill/retry — watchdog only reports
- ✅ Stale lock → report to watchdog only, do NOT auto-kill
- ✅ Timeout → report to watchdog only, do NOT auto-retry
- ✅ Concurrent run → BLOCKER, do NOT auto-kill

### Current Enforcement
- `v2_football_quant/engine/task_watchdog.py` — shared watchdog base
- `v2_football_quant/engine/v4_review_with_watchdog.py` — V4 review watchdog wrapper (exists, with lock/route_marker/sent_marker)
- `v2_football_quant/engine/v4_scan_and_brief.py` — V4 scan watchdog with global lock and timeouts

## 2. State Contract

### V4 State Marker Hierarchy

```
INPUT_READY                    # Scan input data ready
STRUCTURED_OUTPUT_READY        # Structured recommendation output
RENDERED_FULL_READY            # Full review rendered
RENDERED_QQ_READY              # QQ brief rendered
SCHEMA_GUARD_PASS              # Schema validation passed
RENDERER_GUARD_PASS            # Renderer guard passed
QQ_GUARD_PASS                  # QQ guard passed
WATCHDOG_PASS                  # Watchdog validated
ROUTE_MARKER_READY             # Route marker generated
SENT_MARKER_READY              # Sent marker ready (NOT written yet)
ATTRIBUTION_READY              # Attribution data ready
ROLLING_READY                  # Rolling window update ready
PRODUCTION_VERIFIED_READY      # NOT yet — still false
```

### Current Phase V4-D Status
- Current max state: `QQ_GUARD_PASS` contract established
- `WATCHDOG_PASS` contract established but NOT executed in production
- `ROUTE_MARKER_READY` ≠ `sent_marker`
- `SENT_MARKER_READY` = false (this phase)
- `PRODUCTION_VERIFIED_READY` = false (this phase)
- `phase_e_allowed` = false

### Marker Separation
- `route_marker` ≠ `sent_marker` ≠ `PRODUCTION_VERIFIED`
- Under no-push: `sent_marker_written` = false
- Under no-production: `PRODUCTION_VERIFIED` = false

## 3. Lock Contract

### Lock Requirements
- ✅ Every V4 run MUST acquire a lock before execution
- ✅ Lock MUST contain: pid, started_at, phase, date, window
- ✅ Stale lock → report ONLY, do NOT auto-kill
- ✅ Lock release MUST have marker
- ✅ Concurrent run MUST BLOCKER, not auto-resolve

### Lock Fields (required)
```json
{
  "pid": "<process_id>",
  "started_at": "<ISO_timestamp>",
  "phase": "<review|scan|render>",
  "date": "<YYYYMMDD>",
  "window": "<early|midday|evening|night>"
}
```

### Existing Lock Files
- `v2_football_quant/data/runtime/locks/v4_daily_review.lock`
- `v2_football_quant/data/runtime/locks/v4_scan_global.lock` (used by v4_scan_and_brief.py)
- All locks are in `data/runtime/locks/` which is NOT committed

## 4. Timeout Contract

### Each Phase Timeout
- ✅ Each stage MUST have timeout
- ✅ Timeout → stop and report to watchdog only
- ✅ NO AI auto-retry on timeout
- ✅ NO expanding scope on timeout

### Current Timeout Values (v4_review_with_watchdog.py)
- structured output: 900s (15m)
- shell guard: 600s (10m)
- full render: 1200s (20m)
- qq render: 120s (2m)
- route marker: 120s (2m)
- sent marker: 60s (1m)

### Current Timeout Values (v4_scan_and_brief.py)
- HARD_TIMEOUT: 3600s (60m)
- SOFT_TIMEOUT: 1800s (30m)

## 5. Enforcement

### Allowed (current phase)
- V4-E allowed_to_generate = true
- V4-E allowed_to_execute = false

### Blocked (current phase)
- production_verified = false
- phase_e_allowed = false
- qq_push_allowed = false
- state_write_allowed = false
- cron_enable_allowed = false
- watchdog_bypass_allowed = false
