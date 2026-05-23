# V3/V4 Dashboard Daily Auto Update Schedule Correction - 20260523

## Phase
V3V4-DASHBOARD-DAILY-AUTO-UPDATE-SCHEDULE-CORRECTION-20260523

## Conclusion
`V3V4_DASHBOARD_DAILY_AUTO_UPDATE_SCHEDULE_CORRECTION_WARN_ONLY`

The dashboard auto-update schedule has been corrected to separate scan-driven candidate refresh from validation-driven result refresh. No cron was created or enabled.

## Corrected Timeline

1. `12:00` — `V4_DAILY_SCAN_READONLY` starts the read-only V4 scan.
2. `13:00` — `V3V4_DASHBOARD_AFTER_SCAN_REFRESH` updates today's recommendations into the dashboard.
3. `13:00` — `V4_VALIDATION_DRY_RUN` starts post-match validation dry-run.
4. `13:30` — `V3V4_DASHBOARD_AFTER_VALIDATION_REFRESH` updates yesterday / cumulative validation into the dashboard.

## After-Scan Gate

- planned_time: `13:00`
- requires_scan_completed: `true`
- requires today's brief: `true`
- requires today's candidate source: `true`
- source_window: `daily_1200`
- validation_touched: `false`

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

If scan is not ready:

- do not overwrite dashboard
- write `SCAN_NOT_READY`
- preserve last_good
- stop and report
- no auto retry
- no kill
- no timeout change

## After-Validation Gate

- planned_time: `13:30`
- requires_validation_completed: `true`
- validation filter: `match_date`
- brief_used_for_hit_rate: `false`
- candidate_touched: `false`

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

If validation is not ready:

- do not overwrite validation section
- write `VALIDATION_NOT_READY`
- preserve last_good
- stop and report
- no auto retry
- no kill
- no timeout change

## Cron Plan

Generated:

- `docs/V3V4_DASHBOARD_DAILY_AUTO_UPDATE_CRON_PLAN_20260523.md`
- `data/runtime/status/v3v4_dashboard_daily_auto_update_cron_plan_20260523.json`

Cron controls:

- cron_enabled=false
- autosync_cron_created=false
- boss_approval_required=true
- delivery.mode=none
- QQ_push=false
- cloud_publish=false
- capture_ran=false
- auto_retry=false
- auto_kill=false
- timeout_change=false

## Checker Results

- `tools/check_v3v4_dashboard_daily_auto_update_schedule.py`: PASS
- `tools/check_v3v4_dashboard_daily_auto_update_pipeline.py`: PASS
- `tools/check_v3v4_dashboard_after_scan_refresh.py`: PASS
- `tools/check_v3v4_dashboard_after_validation_refresh.py`: PASS
- `tools/check_v4_single_daily_1200_scan_policy.py`: PASS
- `tools/check_v4_match_date_validation_history_recovery.py`: PASS
- `tools/check_v4_scout_date_integrity.py`: WARN_ONLY, raw_dump / backup skipped only; active/formal contaminated_rows=0
- `tools/check_v3v4_dashboard_validation_visibility.py`: PASS
- `tools/check_v2_decommission_v3_v4_only.py`: PASS
- `tools/check_gateway_cron_policy_hardening.py`: PASS

## Answers Required By BOSS

1. 12:00 is only the V4 scan start: yes.
2. 13:00 updates match recommendations into dashboard: yes.
3. 13:30 updates post-match validation into dashboard: yes.
4. after-scan only updates candidates: yes.
5. after-validation only updates validation: yes.
6. scan not ready preserves last_good and does not overwrite dashboard: yes.
7. validation not ready preserves last_good and does not overwrite validation: yes.
8. cron plan generated: yes.
9. cron enabled: no.
10. capture run: no.
11. QQ pushed: no.
12. cloud published: no.
13. OpenClaw pre-enable verification allowed: yes, after BOSS review.
14. Git commit stage allowed: yes, after BOSS review.

## Forbidden Confirmation

- cron_enabled=false
- autosync_cron_created=false
- capture_ran=false
- v4_scan_ran=false
- QQ_push=false
- push_enabled=false
- cloud_publish=false
- git_commit=false
- git_push=false
- v2_restored=false
- v33_active=false
- c_active_in_dashboard=false
- c_validation_visible=false
- last_7d_visible=false
- brief_used_for_hit_rate=false
- scan_date_used_for_validation=false
- strategy_changed=false
- v4_candidate_numbers_changed=false
- validation_numbers_changed=false
- attribution_numbers_changed=false
- secrets_committed=false
