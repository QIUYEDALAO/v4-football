# V4 Scout Date Integrity Repair and Validation Rebase - 20260523

## Conclusion

- conclusion: `V4_SCOUT_DATE_INTEGRITY_REPAIR_VALIDATION_REBASE_WARN_ONLY`
- current scope: V3/V4 only
- V2 restored: false
- V33 restored: false
- capture_ran: false
- QQ_push: false
- cloud_publish: false
- cron_enabled: false
- git_commit: false
- git_push: false

## Root Cause

The V4 scanner wrote `date` from scan date (`scan_dt`) while night scans with `--lookahead-hours 24` included next-day fixtures. That made validators using `--date` treat scan-file rows as same-day matches even when kickoff was on the next local date.

## Fixed Schema

- `date`: compatibility alias of actual kickoff local `match_date`.
- `match_date`: actual kickoff local date and the only formal validation filter.
- `scan_date`: scanner run date, audit-only.
- `scout_file_date`: date embedded in `scout_v4_YYYYMMDD.json`, audit-only.
- `kickoff_local`: parsed local kickoff timestamp.

## Code Repairs

- scanner/writer: `engine/v4_runner.py`
- validator match-date filter: `engine/v4_ht_result_validator.py`
- attribution match-date filter: `engine/v4_result_attribution.py`
- candidate source resolver: `tools/v4_today_source_resolver.py`
- dashboard validation resolver: `tools/v3v4_dashboard_validation_resolver.py`
- repair script: `tools/repair_v4_scout_match_dates.py`
- integrity checker: `tools/check_v4_scout_date_integrity.py`

## Historical Repair

- active formal scout files: 19
- active formal rows: 1584
- active polluted rows before repair: 920 (58.1%)
- repaired active rows: 920
- archive repaired rows: 12
- changed rows including metadata completion: 1599
- non_date_field_changed: False
- backup root: `data/runtime/backups/v4_scout_date_repair_20260523`

## 20260522 Scout File

- rows: 373
- polluted rows before repair: 339 (90.9%)
- contaminated rows after repair: 0

## Validation Rebase

- old_summary_marked_stale: True
- date_filter_field: `match_date`
- validation_source_status: `STALE_REBASED_NO_API_RESULTS_READY`
- brief_used_for_hit_rate: False
- C active: false
- last_7d visible: false
- A+B excludes C: true

Because live result API execution was not authorized in this phase, dashboard validation is rebased conservatively to N/A rather than fake 0% rates. Formal source files and stale markers are recorded for audit.

## Dashboard Refresh

- dashboard_sha256: `89c1559b7f6bec5a4719feb42379191a49b57cc191e885194370dd9f766681f4`
- validation_layout: `two_column`
- C visible: false
- last_7d visible: false
- today brief drives dashboard: true
- HTTP 127: 200
- HTTP 192: 200

## Verification

{
  "scout_date_integrity": "WARN_ONLY",
  "dashboard_two_column": "PASS",
  "compact_remove_c": "PASS",
  "brief_validation_refresh": "PASS",
  "ui_data_validation": "PASS",
  "ui": "PASS",
  "v2_decommission": null,
  "repo_singleton": "PASS",
  "openclaw_manifest": "PASS",
  "cloud_bundle": "PASS",
  "cloud_autosync": null,
  "gateway_cron": null,
  "daily_refresh": "PASS"
}

## Integrity Checker Warning

The scout integrity checker is `WARN_ONLY` only because it records skipped non-formal raw dump and backup files as warnings. Active contamination is 0.

## Safety Confirmations

- v2_restored=false
- v2_visible_in_dashboard=false
- v2_active_source=false
- v33_active=false
- c_active_in_dashboard=false
- c_validation_visible=false
- last_7d_visible=false
- capture_ran=false
- QQ_push=false
- push_enabled=false
- cloud_publish=false
- cron_enabled=false
- autosync_cron_created=false
- git_commit=false
- git_push=false
- D13=false
- V33=false
- HOURLY=false
- strategy_changed=false
- v4_candidate_numbers_changed=false
- validation_numbers_changed=false
- attribution_numbers_changed=false
- secrets_committed=false
