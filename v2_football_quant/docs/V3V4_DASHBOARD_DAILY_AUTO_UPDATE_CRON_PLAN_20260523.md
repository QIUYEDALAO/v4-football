# V3/V4 Dashboard Daily Auto Update Cron Plan - 20260523

## Scope
This is a corrected plan only. It does not create, enable, or modify cron.

## Fixed Timeline

- 12:00: `V4_DAILY_SCAN_READONLY` starts the read-only V4 daily scan.
- 13:00: `V3V4_DASHBOARD_AFTER_SCAN_REFRESH` updates today's recommendations into the dashboard.
- 13:00: `V4_VALIDATION_DRY_RUN` starts post-match validation dry-run.
- 13:30: `V3V4_DASHBOARD_AFTER_VALIDATION_REFRESH` updates yesterday/cumulative validation into the dashboard.

## Task 1: V3V4_DASHBOARD_AFTER_SCAN_REFRESH

- planned_time: `13:00`
- command:

```bash
python3 tools/run_v3v4_dashboard_daily_update.py --date TODAY --phase after-scan --mode apply --no-api --no-capture --no-push --no-cloud --strict
```

Allowed updates:

- candidate list
- A/B/SKIP
- V4 intelligence status
- data status card
- today's formal brief display

Forbidden updates:

- yesterday validation
- cumulative validation
- validation summary
- attribution
- review

Completion gate:

- today's V4_DAILY_SCAN_READONLY completion marker must exist
- today's brief must exist
- today's candidate source must exist
- source_window must be daily_1200 compatible
- brief date must equal target date

If scan is not ready:

- do not overwrite dashboard
- write `SCAN_NOT_READY`
- preserve last_good
- stop and report
- no auto retry
- no kill
- no timeout change

## Task 2: V3V4_DASHBOARD_AFTER_VALIDATION_REFRESH

- planned_time: `13:30`
- command:

```bash
python3 tools/run_v3v4_dashboard_daily_update.py --date TODAY --phase after-validation --mode apply --no-api --no-capture --no-push --no-cloud --strict
```

Allowed updates:

- yesterday validation
- cumulative validation
- validation summary
- validation audit folded section

Forbidden updates:

- today candidate source
- brief source
- candidate raw numbers
- V4 strategy

Completion gate:

- 13:00 V4_VALIDATION_DRY_RUN must be complete or have explicit status
- validation / attribution / review source must be readable
- validation summary must be rebuilt with match_date
- API disabled must produce N/A reason, not fake 0%
- cumulative validation can use local trusted match_date history

If validation is not ready:

- do not overwrite validation section
- write `VALIDATION_NOT_READY`
- preserve last_good
- stop and report
- no auto retry
- no kill
- no timeout change

## Disabled Execution Controls

- cron_enabled=false
- boss_approval_required=true
- delivery.mode=none
- QQ_push=false
- cloud_publish=false
- capture_ran=false
- auto_retry=false
- auto_kill=false
- timeout_change=false
- cron_created=false
- git_commit=false
- git_push=false
