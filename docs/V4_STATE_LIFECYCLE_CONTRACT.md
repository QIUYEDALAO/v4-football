# V4 State Lifecycle Contract

Phase: V4-D
Date: 2026-05-19
Status: FINAL

## State Progression

Each V4 pipeline run progresses through defined states in order.
No state can be skipped. No state can be written without the previous state being confirmed.

```
1.  INPUT_READY                → Scan input data is loaded
2.  STRUCTURED_OUTPUT_READY    → Structured recommendations generated (A/B/C/SKIP)
3.  RENDERED_FULL_READY        → Full review markdown rendered
4.  RENDERED_QQ_READY          → QQ brief markdown rendered
5.  SCHEMA_GUARD_PASS          → Output schema validated
6.  RENDERER_GUARD_PASS        → Renderer guard validated
7.  QQ_GUARD_PASS              → QQ guard validated
8.  WATCHDOG_PASS              → Watchdog validates complete pipeline
9.  ROUTE_MARKER_READY         → Route marker generated (not sent)
10. SENT_MARKER_READY          → Sent marker ready (NOT written in current phase)
11. ATTRIBUTION_READY          → Attribution data generated
12. ROLLING_READY              → Rolling window updated
13. PRODUCTION_VERIFIED_READY  → Full production verification (NOT in current phase)
```

## Current Phase V4-D Constraints

| Marker | Status |
|--------|--------|
| INPUT_READY | controllable |
| STRUCTURED_OUTPUT_READY | controllable |
| RENDERED_FULL_READY | controllable |
| RENDERED_QQ_READY | controllable |
| SCHEMA_GUARD_PASS | PASS |
| RENDERER_GUARD_PASS | PASS |
| QQ_GUARD_PASS | PASS |
| WATCHDOG_PASS | contract established, NOT executed |
| ROUTE_MARKER_READY | contract established, NOT executed |
| SENT_MARKER_READY | false (this phase) |
| ATTRIBUTION_READY | contract established |
| ROLLING_READY | contract established |
| PRODUCTION_VERIFIED_READY | false (this phase) |

## Key Rules

1. `ROUTE_MARKER_READY` does NOT equal `SENT_MARKER_READY`
2. `SENT_MARKER_READY` does NOT equal `PRODUCTION_VERIFIED_READY`
3. Skip or bypass of any state is BLOCKER
4. Concurrent progression to the same state is BLOCKER
5. No state can be written before WATCHDOG_PASS for that phase
6. `PRODUCTION_VERIFIED_READY` requires ALL prior states PASS

## Current Phase Enforcement

- `production_verified` = false
- `phase_e_allowed` = false
- `qq_push_allowed` = false
- `state_write_allowed` = false
- `cron_enable_allowed` = false
- `watchdog_bypass_allowed` = false
- `v4_e_allowed_to_generate` = true
- `v4_e_allowed_to_execute` = false
