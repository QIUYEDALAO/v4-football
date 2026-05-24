# V3/V4 Dashboard Dynamic Date Marker and Match-Date TZ Hotfix - 20260524

## Summary

The 13:00 dashboard after-scan refresh did not update because active dashboard runners were still bound to stale fixed-date marker paths. The hotfix removes active hardcoded dashboard marker dates, rebuilds 20260524 dashboard markers from formal scan outputs, repairs 20260524 scout match_date semantics to match-local dates, and refreshes the local dashboard without full scan, capture, QQ push, cloud publish, or strategy changes.

## Answers

1. Why did the dashboard not update?
   - `tools/run_v3v4_dashboard_daily_update.py` read fixed 20260523 marker paths, so 20260524 scan outputs were not recognized by after-scan.
2. Which files had hardcoded 20260523?
   - Active stale marker usage was removed from `tools/run_v3v4_dashboard_daily_update.py`; related after-scan/after-validation/final checkers were updated to dynamic date. Guard denylist text remains only as checker assertions.
3. Dynamic `--date` / TODAY?
   - Yes. Runners and checkers resolve markers from the requested date; cron `TODAY` remains runtime-only.
4. Were today's missing markers rebuilt?
   - Yes. `v3v4_dashboard_brief_resolution_20260524.json` and `v3v4_dashboard_candidate_view_20260524.json` were rebuilt from formal scout/brief/scan_perf outputs.
5. after-scan restored?
   - Yes. after-scan status is `READY` and dashboard_refreshed=True.
6. Dashboard uses 20260524 data?
   - Yes. HTTP page shows `今日候选`, A5/B5/SKIP4, and no stale-data notice.
7. 13:30 / 14:00 dynamic date fixed?
   - Yes. after-validation and final validation resolve `v3v4_validation_summary_20260524.json` and same-date source hash markers.
8. match_date actual local date?
   - Yes. 20260524 scout date fields now use match-local `kickoff_local` plus `timezone_source`; `scan_date` remains audit-only.
9. CST truncation still used?
   - No for repaired 20260524 formal scout; timezone checker reports cst_truncation_risk_rows=0.
10. Djurgardens filter reason?
   - not_present_in_20260524_formal_scout_or_brief; no manual insertion allowed.
11. MLS strategy changed?
   - No. Observation only.
12. recent_last_n changed?
   - No. Observation only.
13. Full scan run? false.
14. capture run? false.
15. QQ push? false.
16. cloud publish? false.
17. candidate raw grades changed? false.
18. validation / attribution raw results changed? false.
19. commit/push? pending at report generation; final response records actual commit/push.
20. cron post-enable reverify allowed? yes, after this hotfix is pushed.

## Validation

- Dynamic marker checker: PASS
- After-scan checker: PASS
- After-validation checker: PASS
- Final validation checker: PASS
- Match-date timezone checker: PASS
- Scout date integrity: WARN_ONLY, only raw_dump/backup skipped
- Dashboard HTTP 127: 200
- Dashboard HTTP 192: 200

## Boundary

- full_scan_ran=false
- capture_ran=false
- QQ_push=false
- cloud_publish=false
- cron_modified=false
- strategy_changed=false
- v4_candidate_numbers_changed=false
- result_validation_changed=false
- script_validation_changed=false
- attribution_numbers_changed=false
- secrets_printed=false
