# V3V4 Dashboard Validation Visibility Recovery - 20260523

## Phase
V3V4-DASHBOARD-VALIDATION-VISIBILITY-RECOVERY-20260523

## Conclusion
`V3V4_DASHBOARD_VALIDATION_VISIBILITY_RECOVERY_WARN_ONLY`

The validation visibility defect has been repaired. The V3/V4 match validation card is now always visible in the active dashboard, even when the post-repair validation summary has no settled hit-rate data available.

## Root Cause
The validation summary exists and is traceable, but after the scout date repair/rebase the dashboard has no settled match-date validation rates ready for display. The source trace shows:

- `summary_exists=true`
- `validation_has_data=false`
- `api_disabled=true`
- `old_summary_stale=true`
- `brief_used_for_hit_rate=false`
- `c_observation_active=false`
- `last_7d_active=false`

The dashboard display layer needed to render a stable N/A state with reason text instead of allowing validation data absence to make the module appear missing.

## Fixes Applied

1. Added issue list and source trace artifacts.
2. Added a validation display contract requiring permanent visibility.
3. Updated the dashboard renderer to always render the V3/V4 validation card.
4. Updated N/A formatting so empty validation metrics display as `N/A`, not fake `0/0` or `0%`.
5. Added API-disabled / stale-rebase reason text:
   `赛果数据未就绪：API disabled / 修复后等待 match_date 正式 attribution，未伪造命中率。`
6. Added validation audit details for source files, latest validation date, API status, and brief-hit-rate guard.
7. Added `tools/check_v3v4_dashboard_validation_visibility.py` to fail if the validation module disappears.
8. Strengthened `tools/check_v3v4_dashboard_validation_two_column_script_highlight.py` to require A/B/A+B rows and visibility reason.
9. Rebuilt the dashboard through the daily refresh entrypoint in dry-run and apply modes, without capture, QQ push, cloud publish, or cron creation.

## Dashboard Result

- Validation card visible: `true`
- Yesterday validation visible: `true`
- Cumulative validation visible: `true`
- Layout: `two_column`
- Display mode: `na`
- A/B/A+B rows visible: `true`
- API disabled reason visible: `true`
- N/A visible: `true`
- C validation visible: `false`
- Last 7d validation visible: `false`
- Brief used for hit rate: `false`

## Served HTML Verification

- `http://127.0.0.1:8765/intel_ops_console.html`: `200`
- `http://192.168.1.2:8765/intel_ops_console.html`: `200`
- Browser DOM verification confirmed:
  - `V3/V4 比赛验证` visible
  - `昨日验证` visible
  - `累计验证` visible
  - `A / B / A+B` visible
  - `N/A` visible
  - API disabled reason visible
  - no C validation
  - no 7d validation
  - no `V2 active`
  - no `V33 active`

## Validation Source Answer

1. Why was validation not visible?
   - The post-repair summary had no settled hit-rate data ready (`validation_has_data=false`) and API-disabled / stale-rebase status needed a visible N/A presentation.
2. Was it data missing, API disabled, or renderer hidden?
   - It was an API-disabled / no-settled-data display case. The renderer now forces the validation card visible with N/A and reason text.
3. Is V3/V4 match validation visible now?
   - Yes.
4. Is yesterday validation visible?
   - Yes.
5. Is cumulative validation visible?
   - Yes.
6. Does no-data state show N/A?
   - Yes.
7. Does API-disabled state show a reason?
   - Yes.
8. Is C still hidden?
   - Yes.
9. Is last 7d still hidden?
   - Yes.
10. Did the brief participate in hit-rate calculation?
   - No. `brief_used_for_hit_rate=false`.
11. Was dashboard refreshed?
   - Yes, via dry-run and apply daily refresh.
12. Was capture run?
   - No.
13. Was QQ pushed?
   - No.
14. Was cloud published?
   - No.
15. Can this enter Git commit stage?
   - Functionally yes after BOSS review, but this phase explicitly did not commit.

## Validation Summary

- New visibility checker: `PASS`
- Scout date integrity checker: `WARN_ONLY`, with active/formal `contaminated_rows=0`; warnings are skipped raw dump / backup files.
- Daily 1200 policy checker: `WARN_ONLY`, inherited source-window warning only; no production/capture/push/cloud blocker.
- Dashboard UI/checker chain: `PASS`
- V2/V33 guard chain: `PASS`
- HTTP served HTML: `PASS`

## Forbidden Action Confirmation

- `v2_restored=false`
- `v2_visible_in_dashboard=false`
- `v2_active_source=false`
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
- `D13=false`
- `V33=false`
- `HOURLY=false`
- `strategy_changed=false`
- `v4_candidate_numbers_changed=false`
- `validation_numbers_changed=false`
- `attribution_numbers_changed=false`
- `secrets_committed=false`
