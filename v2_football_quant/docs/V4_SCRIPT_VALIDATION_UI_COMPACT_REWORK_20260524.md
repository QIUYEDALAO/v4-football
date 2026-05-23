# V4 Script Validation UI Compact Rework 20260524

## Scope
- Phase: V4-SCRIPT-VALIDATION-UI-COMPACT-REWORK-20260524
- Scope is display-layer, checker, and dashboard API status display only.
- No V4 strategy change, no candidate rating change, no result validation mutation, no script validation mutation.
- No full scan, no capture, no QQ push, no cloud publish, no cron creation, no git commit, no git push.

## Step 1 Issue List
Status: PASS

Issues covered: 10

1. Script validation was visually mixed with result validation.
2. Yesterday N/A and cumulative A/B/A+B were crowded into one line.
3. Yellow highlight carried too much visual weight.
4. Script validation rate was not clearly labeled as trend-fit rate.
5. Script validation must not affect A/B result hit rate.
6. Script validation should default to compact display.
7. Detailed A/B split belongs in a collapsed details block.
8. SCRIPT_UNKNOWN denominator exclusion must remain explicit.
9. Dashboard API disabled state could be stale.
10. Checker must prevent the confusing script UI from returning.

Issue list: `docs/V4_SCRIPT_VALIDATION_UI_COMPACT_REWORK_ISSUE_LIST_20260524.md`

## Step 2 Display Rules
Status: PASS

- Main metric: AB_cumulative
- Details collapsed: true
- Main screen text: `剧本验证（辅助） 累计 A+B：69/124 · 55.6%`
- Meaning label: `走势吻合率，不影响 A/B 结果命中率`
- A split, B split, yesterday N/A, SCRIPT_UNKNOWN, source files, C/SKIP exclusions are in collapsed details.

## Step 3 Renderer
Status: PASS

- `script_validation_ui=compact_lite`
- `script_a_visible_main=false`
- `script_b_visible_main=false`
- `script_yesterday_visible_main=false`
- `script_unknown_in_denominator=false`
- Result validation preserved.
- Script validation raw numbers preserved.

Renderer path: `tools/generate_intel_desk_html.py`

## Step 4 API Status
Status: PASS

- latest_safe_to_scan=True
- api_disabled_visible=False
- Dashboard status now prioritizes latest successful key-injection/direct preflight evidence before older local shell no-key preflight markers.
- API OK / preflight passed no longer renders as API disabled.

## Step 5 Checker
Status: PASS

Checker path: `tools/check_v4_script_validation_ui_compact.py`

Guards:
- compact_ui_guard=True
- api_status_guard=True
- served_html_checked=True
- HTTP 127=200
- HTTP 192=200

The older postmatch script validation checker was aligned to accept `剧本验证明细` and compact `累计 A+B` script validation display.

## Step 6 Dashboard Rebuild
Status: PASS

- dashboard_sha256=452c72454228c002a43e69c52fdc26d6790211d12fb03f750369f53a9cc12dd9
- result_validation_changed=false
- script_validation_changed=false
- capture_ran=false
- QQ_push=false
- cloud_publish=false

## Step 7 Validation
Status: WARN_ONLY

Checker results:
```json
{
  "check_v4_script_validation_ui_compact": "PASS",
  "check_v4_postmatch_script_validation": "PASS",
  "check_v4_postmatch_validation_api_route": "PASS",
  "check_v4_api_preflight": "WARN_ONLY",
  "check_v4_scout_date_integrity": "WARN_ONLY",
  "check_v4_match_date_validation_history_recovery": "PASS",
  "check_v3v4_dashboard_validation_visibility": "PASS",
  "check_v3v4_dashboard_daily_auto_update_pipeline": "PASS",
  "check_v2_decommission_v3_v4_only": "PASS",
  "check_gateway_cron_policy_hardening": "PASS"
}
```

Warnings:
```json
[
  "local shell API key missing during current preflight; dashboard uses latest successful key-injection/preflight status and does not display API disabled",
  "scout integrity checker skipped raw_dump/backup files by design; formal contaminated_rows=0"
]
```

No BLOCKER was found.

## Validation Numbers Preserved
Result validation:
- A: 39/46 · 84.8%
- B: 85/94 · 90.4%
- A+B: 124/140 · 88.6%

Script validation:
- A: 22/39 · 56.4%
- B: 47/85 · 55.3%
- A+B: 69/124 · 55.6%

## Forbidden Item Confirmation
- result_validation_changed=false
- script_validation_changed=false
- brief_used_for_script_validation=false
- scan_date_used_for_validation=false
- c_validation_visible=false
- c_script_validation_visible=false
- last_7d_visible=false
- full_scan_ran=false
- capture_ran=false
- QQ_push=false
- push_enabled=false
- cloud_publish=false
- cron_enabled=false
- git_commit=false
- git_push=false
- v2_restored=false
- v33_active=false
- strategy_changed=false
- v4_candidate_numbers_changed=false
- validation_numbers_changed=false
- attribution_numbers_changed=false
- secrets_printed=false
- secrets_committed=false

## Conclusion
V4_SCRIPT_VALIDATION_UI_COMPACT_REWORK_WARN_ONLY
