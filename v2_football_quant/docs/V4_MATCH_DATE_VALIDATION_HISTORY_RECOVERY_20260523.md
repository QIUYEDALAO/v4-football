# V4 Match-Date Validation History Recovery - 20260523

## Phase
V4-MATCH-DATE-VALIDATION-HISTORY-RECOVERY-20260523

## Conclusion
`V4_MATCH_DATE_VALIDATION_HISTORY_RECOVERY_WARN_ONLY`

The stale polluted validation summary was not restored. Instead, local V4 attribution history was audited, reconnected to repaired scout `match_date` by `fixture_id`, and used to rebuild active dashboard validation.

## What Happened To The Old Validation Data

The previous dashboard validation summary was marked stale after the scout date integrity repair because it could have inherited scan-date contamination. That stale summary remains excluded from active validation.

The underlying local attribution history still exists in:

- `data/v4_archive/v4_result_attribution_20260513.jsonl`
- `data/v4_archive/v4_result_attribution_20260514.jsonl`
- `data/v4_archive/v4_result_attribution_20260515.jsonl`
- `data/v4_archive/v4_result_attribution_20260516.jsonl`
- `data/v4_archive/v4_result_attribution_20260517.jsonl`
- `data/v4_archive/v4_result_attribution_20260518.jsonl`
- `data/v4_archive/v4_result_attribution_20260520.jsonl`

These files were not used blindly. Each active A/B record was accepted only when it could be tied by `fixture_id` to the repaired scout `match_date` and had a resolved `MODEL_HIT` or `MODEL_MISS` result.

## Source Classification

- stale summary sources: 2
- trusted match_date-ready source entries: 10
- missing-match-date backfill candidates: 12
- API-disabled / unresolved sources: 2
- do-not-use sources: 15

Recoverability audit:

- total attribution records: 472
- trusted_records: 140
- recoverable_records: 140
- unresolved_records: 3
- blocked_records: 0

## Summary Rebuild

Active summary file:

- `data/runtime/status/v3v4_validation_summary_20260523.json`

Rules enforced:

- `date_filter_field=match_date`
- `old_summary_marked_stale=true`
- `active_summary_uses_stale_polluted_source=false`
- `brief_used_for_hit_rate=false`
- `c_observation_active=false`
- `last_7d_active=false`
- `c_excluded_from_ab=true`
- `api_enabled=false`

## Dashboard Validation Result

Yesterday validation uses `match_date=2026-05-22`:

- A: `N/A`
- B: `N/A`
- A+B: `N/A`
- reason: no trusted local settled attribution for yesterday / API disabled prevents fresh attribution

Cumulative validation was recovered from trusted local match_date attribution history:

- A: `39/46 · 84.8%`
- B: `85/94 · 90.4%`
- A+B: `124/140 · 88.6%`

The dashboard now displays the reason:

`累计验证已从本地 match_date attribution 历史恢复；昨日暂无可信已结算样本，显示 N/A。`

## Dashboard Refresh

Dashboard was refreshed through:

`python3 tools/run_v3v4_intel_ops_console_daily_refresh.py --date 20260523 --mode apply --source-window auto --no-capture --no-push --no-cloud --strict`

No capture, QQ push, cloud publish, cron creation, strategy change, candidate-number change, validation raw-data change, or attribution raw-data change was performed.

## Verification

- `tools/check_v4_match_date_validation_history_recovery.py`: PASS
- `tools/check_v3v4_dashboard_validation_visibility.py`: PASS
- `tools/check_v4_scout_date_integrity.py`: WARN_ONLY; active/formal contaminated rows remain 0, warnings are skipped raw_dump / backup files
- `tools/check_v4_single_daily_1200_scan_policy.py`: WARN_ONLY; inherited source_window warning only
- `tools/check_v3v4_dashboard_validation_two_column_script_highlight.py`: PASS
- `tools/check_v3v4_dashboard_compact_validation_remove_c.py`: PASS
- `tools/check_v3v4_dashboard_brief_validation_auto_refresh.py`: PASS
- `tools/check_v3v4_intel_ops_console_ui_data_validation.py`: PASS
- `tools/check_v3v4_intel_ops_console_ui.py`: PASS
- `tools/check_v2_decommission_v3_v4_only.py`: PASS
- `tools/check_openclaw_active_source_manifest.py`: PASS

HTTP:

- `http://127.0.0.1:8765/intel_ops_console.html`: 200
- `http://192.168.1.2:8765/intel_ops_console.html`: 200

Browser DOM confirmed:

- validation card visible: true
- yesterday visible: true
- cumulative visible: true
- cumulative recovered values visible: true
- C validation visible: false
- last 7d visible: false
- V2 active visible: false
- V33 active visible: false

## Answers Required By BOSS

1. Previous validation data is in local V4 attribution archive files under `data/v4_archive/`.
2. The active `v3v4_validation_summary_20260523.json` from the pre-repair chain was stale and was not restored as active.
3. 140 A/B records were recovered through repaired scout `match_date` linkage.
4. 3 records remain unresolved due API-disabled / unknown result status.
5. Cumulative validation was restored.
6. Yesterday validation remains N/A because no trusted settled local attribution exists for `match_date=2026-05-22` and API is disabled.
7. Cumulative validation has data because trusted historical attribution exists through `match_date=2026-05-21`.
8. Brief was not used to calculate hit rate.
9. Stale polluted summary was not used.
10. C is not displayed.
11. Last 7d is not displayed.
12. Dashboard was refreshed.
13. Capture was not run.
14. QQ was not pushed.
15. Cloud was not published.
16. Git commit can enter BOSS review stage, but this phase did not commit.

## Forbidden Confirmation

- `stale_polluted_summary_used=false`
- `brief_used_for_hit_rate=false`
- `v2_restored=false`
- `v33_active=false`
- `c_validation_visible=false`
- `last_7d_visible=false`
- `capture_ran=false`
- `QQ_push=false`
- `push_enabled=false`
- `cloud_publish=false`
- `cron_created=false`
- `git_commit=false`
- `git_push=false`
- `strategy_changed=false`
- `v4_candidate_numbers_changed=false`
- `validation_numbers_changed=false`
- `attribution_numbers_changed=false`
- `secrets_committed=false`
