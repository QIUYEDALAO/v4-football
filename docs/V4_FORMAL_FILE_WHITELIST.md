# V4 Formal File Whitelist

Phase: SYSTEM-LEGACY-0
Date: 2026-05-19
Status: CANDIDATE (pre-V4-A review)

This document lists all files in the V4 formal file whitelist.
Only files listed here are permitted as formal V4 production files.
All other V4-related files must be removed or archived.

## Eligibility Requirements

A V4 file must satisfy ALL of:
1. Targets only V4 first-half goal intelligence system
2. Does NOT reference V33/V38 as active modules (historical ref only if marked deprecated)
3. Does NOT contain old/backup/batch-worker entry points
4. Only outputs A/B/C/SKIP as formal grades (no non-V4 grades)
5. Does NOT write SKIP as recommendation
6. Does NOT write C as primary recommendation
7. Does NOT allow AI free grade recalculation
8. Does NOT directly push QQ
9. Does NOT directly write production state
10. Does NOT write PRODUCTION_VERIFIED

## Formal V4 Files (confirmed eligible for V4 production path)

None at this time. All V4 files are currently CANDIDATE status pending V4-A review.

## Formal V4 Candidate Files (pending V4-A formal contract)

All located in `v2_football_quant/engine/`:

| File | Status | Notes |
|------|--------|-------|
| v4_api_budget_audit.py | CANDIDATE | API budget monitoring |
| v4_calibration_report.py | CANDIDATE | Calibration report |
| v4_daily_recommendation_brief.py | CANDIDATE | Daily brief generation |
| v4_dashboard.py | CANDIDATE | Dashboard |
| v4_data_logger.py | CANDIDATE | Data logging |
| v4_display_name_normalizer.py | CANDIDATE | Display name normalization |
| v4_ht_result_validator.py | CANDIDATE | HT result validation |
| v4_ht_result_verifier.py | CANDIDATE | HT result verification |
| v4_job_runner.py | CANDIDATE | Job runner |
| v4_live_capture_audit.py | CANDIDATE | Live capture audit |
| v4_live_capture_scheduler.py | CANDIDATE | Live capture scheduler |
| v4_live_odds_collector.py | CANDIDATE | Live odds collection |
| v4_live_stats_snapshot.py | CANDIDATE | Live stats snapshot |
| v4_master_run.py | CANDIDATE | Master run orchestration |
| v4_match_intelligence.py | CANDIDATE | Match intelligence |
| v4_monthly_report.py | CANDIDATE | Monthly report |
| v4_openclaw_brief.py | CANDIDATE | OpenClaw brief |
| v4_ops_alert.py | CANDIDATE | Ops alert |
| v4_ops_dashboard.py | CANDIDATE | Ops dashboard |
| v4_ops_doctor.py | CANDIDATE | Ops doctor |
| v4_ops_status.py | CANDIDATE | Ops status |
| v4_ops_summary.py | CANDIDATE | Ops summary |
| v4_progress_reporter.py | CANDIDATE | Progress reporter |
| v4_qq_formatter.py | CANDIDATE | QQ formatter |
| v4_release_freeze.py | CANDIDATE | Release freeze |
| v4_report.py | CANDIDATE | Report |
| v4_result_attribution.py | CANDIDATE | Result attribution |
| v4_review_guard.py | CANDIDATE | Review guard |
| v4_review_renderer.py | CANDIDATE | Review renderer |
| v4_review_report.py | CANDIDATE | Review report |
| v4_review_result_refresh.py | CANDIDATE | Review result refresh |
| v4_review_with_watchdog.py | CANDIDATE | Review watchdog |
| v4_runner.py | CANDIDATE | Runner |
| v4_scan_and_brief.py | CANDIDATE | Scan and brief |
| v4_scan_worker.py | CANDIDATE | Scan worker |
| v4_scout_report.py | CANDIDATE | Scout report |
| v4_sh_result_verifier.py | CANDIDATE | SH result verifier |
| v4_sh_strategy_eval.py | CANDIDATE | SH strategy eval |
| v4_strategy_eval.py | CANDIDATE | Strategy evaluation |
| v4_universe_gap_repair.py | CANDIDATE | Universe gap repair |
| v4_validation_progress.py | CANDIDATE | Validation progress |
| v4_versioning.py | CANDIDATE | Versioning |
| v4_weekly_report.py | CANDIDATE | Weekly report |

Also in `v2_football_quant/tools/`:
| File | Status | Notes |
|------|--------|-------|
| check_v4_boundary_contract.py | CANDIDATE | V4 boundary contract check |
| dump_raw_scout.py | CANDIDATE | Raw scout dump |
| generate_mobile_dashboard.py | CANDIDATE | Mobile dashboard |
| patch_time_bins.py | CANDIDATE | Time bin patches |
| replay_day.py | CANDIDATE | Day replay |
| serve_dashboard.py | CANDIDATE | Dashboard server |

## Excluded Legacy Files

Files that matched V33/V38/backup/legacy patterns and are excluded from formal V4:

- All files in `tools/` matching `*v33*`, `*v38*` (see SYSTEM_LEGACY_INVENTORY.md rows 1-13) - DELETE from tools/
- `report-v38-decision.md`, `report-v38-final.md`, `report-v38-summary.md` - ARCHIVE
- `V38-changelist.md` - ARCHIVE
- `MEMORY_legacy_20260515.md` - ARCHIVE
- `data/验证存档/v33/*` - MARK_DEPRECATED
- `data/验证存档/v38/*` - MARK_DEPRECATED

## Archived Legacy Files

See `docs/archive/system_legacy/` directory.

## Deleted Legacy Files

See SYSTEM_LEGACY_INVENTORY.md for the complete delete/archive decision table.
