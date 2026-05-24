# V3/V4 Dashboard Daily Auto Update Cron Plan - 20260524 Final Validation Rebase

## Scope
Plan only. Cron remains disabled. This rebase changes the 14:00 task from dashboard-only final-pass to final validation rerun plus dashboard validation refresh.

## Fixed Timeline

| Time | Task | Role |
|:----:|:-----|:-----|
| 12:00 | `V4_DAILY_SCAN_READONLY` | daily_1200 scan start only, timeout_seconds=1800 planned |
| 13:00 | `V3V4_DASHBOARD_AFTER_SCAN_REFRESH` | refresh today's candidates / A-B-SKIP / V4 status |
| 13:00 | `V4_VALIDATION_DRY_RUN` | first postmatch validation / attribution / review dry-run |
| 13:30 | `V3V4_DASHBOARD_AFTER_VALIDATION_REFRESH` | first validation dashboard refresh |
| 14:00 | `V4_VALIDATION_DRY_RUN_FINAL_AND_DASHBOARD_REFRESH` | second postmatch validation dry-run, then dashboard validation refresh |

## 14:00 Final Task

```bash
python3 tools/run_v3v4_validation_final_and_dashboard_refresh.py --date TODAY --mode apply --no-capture --no-push --no-cloud --strict
```

Rules:
- final_validation_ran=true
- scan_ran=false
- candidate_touched=false
- match_date_used=true
- scan_date_used_for_validation=false
- brief_used_for_hit_rate=false
- brief_used_for_script_validation=false
- if validation_source_hash unchanged: `refresh_status=NOOP_AFTER_VALIDATION_RERUN`
- if validation_source_hash changed: refresh validation section only
- if validation not ready: preserve last_good and write `VALIDATION_NOT_READY_FINAL`

## Governance

- cron_enabled=false
- autosync_cron_created=false
- boss_approval_required=true
- delivery.mode=none
- auto_retry=false
- auto_kill=false
- no capture=true
- no push=true
- no cloud=true
- V2/V33/C/近7天 remain inactive
