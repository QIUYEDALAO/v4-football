# SYSTEM LEGACY INVENTORY

Phase: SYSTEM-LEGACY-0
Created: 2026-05-19
Status: FINAL

## Inventory Table

| # | path | module_guess | legacy_type | risk_level | executable_path | production_risk | current_reference | action | final_location | reason |
|---|------|-------------|-------------|------------|-----------------|-----------------|-------------------|--------|----------------|--------|
| 1 | tools/batch-worker-v38.js | V38 batch worker | old_worker | HIGH | tools/ | HIGH - was production worker | None | DELETE | N/A | V38 worker, not V4, in executable path |
| 2 | tools/batch-worker-v38.1.js | V38.1 batch worker | legacy_worker | HIGH | tools/ | HIGH - was production worker | None | DELETE | N/A | V38.1 variant, not V4, in executable path |
| 3 | tools/batch-worker-v38.backup.js | V38 backup | backup_worker | HIGH | tools/ | MED - backup only | None | DELETE | N/A | Backup of legacy worker, in tools/ |
| 4 | tools/v33-config.js | V33 config | V33 | HIGH | tools/ | HIGH - config for V33 pipeline | None | DELETE | N/A | V33 config, not V4, in executable path |
| 5 | tools/v38-config.js | V38 config | V38 | HIGH | tools/ | HIGH - config for V38 pipeline | None | DELETE | N/A | V38 config, not V4, in executable path |
| 6 | tools/v38.1-config.js | V38.1 config | V38 | HIGH | tools/ | HIGH - config for V38 pipeline | None | DELETE | N/A | V38.1 config, not V4, in executable path |
| 7 | tools/jiebao-scraper-v38.js | V38 scraper | V38 | HIGH | tools/ | HIGH - was production scraper | None | DELETE | N/A | V38 scraper, not V4, in executable path |
| 8 | tools/jiebao-scraper-v38.1.js | V38.1 scraper | V38 | HIGH | tools/ | HIGH - was production scraper | None | DELETE | N/A | V38.1 scraper, not V4, in executable path |
| 9 | tools/report-v38.js | V38 report generator | V38 | HIGH | tools/ | MED | None | DELETE | N/A | V38 report, not V4, in executable path |
| 10 | tools/report-v38.1.js | V38.1 report generator | V38 | HIGH | tools/ | MED | None | DELETE | N/A | V38.1 report, not V4, in executable path |
| 11 | tools/verify-v38.js | V38 verifier | V38 | HIGH | tools/ | MED | None | DELETE | N/A | V38 verify, not V4, in executable path |
| 12 | tools/verify-v38.1.js | V38.1 verifier | V38 | HIGH | tools/ | MED | None | DELETE | N/A | V38.1 verify, not V4, in executable path |
| 13 | tools/verify-v38.1-v2.js | V38.1-V2 verifier | V38 | HIGH | tools/ | MED | None | DELETE | N/A | V38.1-V2, not V4, in executable path |
| 14 | report-v38-decision.md | V38 decision doc | stale_doc | LOW | N/A | LOW - doc only | Historical ref | ARCHIVE | docs/archive/system_legacy/report-v38-decision.md | V38 decision, not V4 reference |
| 15 | report-v38-final.md | V38 final report | stale_report | LOW | N/A | LOW - doc only | Historical ref | ARCHIVE | docs/archive/system_legacy/report-v38-final.md | V38 final, not V4 reference |
| 16 | report-v38-summary.md | V38 summary | stale_report | LOW | N/A | LOW - doc only | Historical ref | ARCHIVE | docs/archive/system_legacy/report-v38-summary.md | V38 summary, not V4 reference |
| 17 | V38-changelist.md | V38 changelist | stale_doc | LOW | N/A | LOW - doc only | Historical ref | ARCHIVE | docs/archive/system_legacy/V38-changelist.md | V38 changelist, not V4 |
| 18 | MEMORY_legacy_20260515.md | Legacy memory backup | archive_reference | LOW | N/A | LOW - mem backup | Historical ref | ARCHIVE | docs/archive/system_legacy/MEMORY_legacy_20260515.md | Backup memory, superseded by current MEMORY.md |
| 19 | data/验证存档/v33/predictions.json | V33 archive predictions | V33 | LOW | N/A (in data/archive) | LOW - historical data | None | MARK_DEPRECATED | data/验证存档/v33/ | Historical V33 data, not V4 reference |
| 20 | data/验证存档/v33/stats.json | V33 archive stats | V33 | LOW | N/A (in data/archive) | LOW - historical data | None | MARK_DEPRECATED | data/验证存档/v33/ | Historical V33 data, not V4 reference |
| 21 | data/验证存档/v38/predictions.json | V38 archive predictions | V38 | LOW | N/A (in data/archive) | LOW - historical data | None | MARK_DEPRECATED | data/验证存档/v38/ | Historical V38 data, not V4 reference |
| 22 | data/验证存档/v38/report-2026-05-04.md | V38 archive report | V38 | LOW | N/A (in data/archive) | LOW - historical data | None | MARK_DEPRECATED | data/验证存档/v38/ | Historical V38 report, not V4 reference |
| 23 | data/验证存档/v38.1/predictions.json | V38.1 archive predictions | V38 | LOW | N/A (in data/archive) | LOW - historical data | None | MARK_DEPRECATED | data/验证存档/v38.1/ | Historical V38.1 data, not V4 reference |
| 24 | data/验证存档/jiebao-scraper-v31.js | V31 scraper archive | legacy_worker | LOW | N/A (in data/archive) | LOW - historical data | None | MARK_DEPRECATED | data/验证存档/ | Historical V31 scraper, in archive |
| 25 | .v2_football_quant/engine/v3_clv_audit.py | V3 CLV audit | V33/V38 reference | MED | v2_football_quant/engine/ | LOW - not production | V2 code | KEEP_FORMAL_V2 | v2_football_quant/engine/ | V2 diagnostics module, not V4 but V2 production |
| 26 | v2_football_quant/engine/v3_dashboard.py | V3 dashboard | V33/V38 reference | MED | v2_football_quant/engine/ | LOW - not production | V2 code | KEEP_FORMAL_V2 | v2_football_quant/engine/ | V2 dashboard, V3 reference but part of V2 system |
| 27 | v2_football_quant/engine/v3_router_guard.py | V3 router guard | V33/V38 reference | MED | v2_football_quant/engine/ | LOW - not production | V2 code | KEEP_FORMAL_V2 | v2_football_quant/engine/ | V3 guard, part of V2 ecosystem |
| 28 | v2_football_quant/engine/v3_signal_builder.py | V3 signal builder | V33/V38 reference | MED | v2_football_quant/engine/ | LOW - not production | V2 code | KEEP_FORMAL_V2 | v2_football_quant/engine/ | V3 signal builder, part of V2 |
| 29 | v2_football_quant/engine/v3_gap_bucket_audit.py | V3 gap audit | V33/V38 reference | MED | v2_football_quant/engine/ | LOW - not production | V2 code | KEEP_FORMAL_V2 | v2_football_quant/engine/ | V2 analysis module |
| 30 | v2_football_quant/engine/v3_wc_stage_resolver.py | V3 stage resolver | V33/V38 reference | MED | v2_football_quant/engine/ | LOW - not V4 | V2 code | KEEP_FORMAL_V2 | v2_football_quant/engine/ | V2 WC module, part of existing system |
| 31 | v2_football_quant/data_pipeline/data/v3_thresholds.json | V3 thresholds data | V33/V38 reference | LOW | v2_football_quant/data_pipeline | LOW | data file | KEEP | v2_football_quant/data_pipeline/ | V2/V3 data, not V4 but part of V2 |
| 32 | v2_football_quant/engine/v4_*.py (all v4 .py files) | V4 engine modules | formal_v4_candidate | VARIED | v2_football_quant/engine/ | LOW - paper only | V4 system | KEEP_FORMAL_V4 | v2_football_quant/engine/ | V4 engine modules, candidate for formal V4 |
| 33 | tools/check_apr26_*.js | Apr26 debug tools | obsolete_script | MED | tools/ | LOW | None | DELETE | N/A | Experimental debug scripts, no current reference |
| 34 | tools/analyze_ft1.js | FT1 analysis | obsolete_script | MED | tools/ | LOW | None | DELETE | N/A | Experimental analysis script |
| 35 | tools/api-football-scraper-v1.js | V1 scraper | old_worker | MED | tools/ | LOW | None | DELETE | N/A | Old v1 scraper, not in use |
| 36 | tools/apif-config.js | APIF config | obsolete_script | MED | tools/ | LOW | None | DELETE | N/A | Old config, not referenced |
| 37 | tools/batch_fox.js | Batch fox | obsolete_script | MED | tools/ | LOW | None | DELETE | N/A | Experimental script |
| 38 | tools/check_az.js | Check AZ | obsolete_script | MED | tools/ | LOW | None | DELETE | N/A | Debug script |
| 39 | tools/check_date_map.js | Date map check | obsolete_script | MED | tools/ | LOW | None | DELETE | N/A | Debug script |
| 40 | tools/check_dates.js | Dates check | obsolete_script | MED | tools/ | LOW | None | DELETE | N/A | Debug script |
| 41 | tools/check_ft1_details.js | FT1 details | obsolete_script | MED | tools/ | LOW | None | DELETE | N/A | Debug script |
| 42 | tools/check_ft2.js | FT2 check | obsolete_script | MED | tools/ | LOW | None | DELETE | N/A | Debug script |
| 43 | tools/check_ft3_ft4.js | FT3/FT4 check | obsolete_script | MED | tools/ | LOW | None | DELETE | N/A | Debug script |
| 44 | tools/check_ft_js.js | FT JS check | obsolete_script | MED | tools/ | LOW | None | DELETE | N/A | Debug script |
| 45 | tools/check_matches.js | Matches check | obsolete_script | MED | tools/ | LOW | None | DELETE | N/A | Debug script |
| 46 | tools/check_nowscore.js | Nowscore check | obsolete_script | MED | tools/ | LOW | None | DELETE | N/A | Debug script |
| 47 | tools/check_osa_bar.js | OSA bar check | obsolete_script | MED | tools/ | LOW | None | DELETE | N/A | Debug script |
| 48 | tools/check_results2.js | Results check | obsolete_script | MED | tools/ | LOW | None | DELETE | N/A | Debug script |
| 49 | tools/check_sc_data.js | SC data check | obsolete_script | MED | tools/ | LOW | None | DELETE | N/A | Debug script |
| 50 | tools/check_serie_ligue1.js | Serie/Ligue1 check | obsolete_script | MED | tools/ | LOW | None | DELETE | N/A | Debug script |
| 51 | tools/check_today_data.js | Today data check | obsolete_script | MED | tools/ | LOW | None | DELETE | N/A | Debug script |
| 52 | tools/check_two_matches.js | Two matches check | obsolete_script | MED | tools/ | LOW | None | DELETE | N/A | Debug script |
| 53 | tools/check_v17_ht.js | V17 HT check | obsolete_script | MED | tools/ | LOW | None | DELETE | N/A | Old V17 debug |
| 54 | tools/check_v17_results.js | V17 results check | obsolete_script | MED | tools/ | LOW | None | DELETE | N/A | Old V17 debug |
| 55 | tools/debug_ft1.js | FT1 debug | obsolete_script | MED | tools/ | LOW | None | DELETE | N/A | Debug script |
| 56 | tools/extract-utils.js | Extract utils | obsolete_script | MED | tools/ | LOW | None | DELETE | N/A | Debug script |
| 57 | tools/extract_apr26.js | Extract Apr26 | obsolete_script | MED | tools/ | LOW | None | DELETE | N/A | Debug script |
| 58 | tools/extract_v17.js | Extract V17 | obsolete_script | MED | tools/ | LOW | None | DELETE | N/A | Old V17 debug |
| 59 | tools/extract_v17_final.js | Extract V17 final | obsolete_script | MED | tools/ | LOW | None | DELETE | N/A | Old V17 debug |
| 60 | tools/final_ft_approach.js | Final FT approach | obsolete_script | MED | tools/ | LOW | None | DELETE | N/A | Debug script |
| 61 | tools/final_report.js | Final report | obsolete_script | MED | tools/ | LOW | None | DELETE | N/A | Debug script |
| 62 | tools/final_summary.js | Final summary | obsolete_script | MED | tools/ | LOW | None | DELETE | N/A | Debug script |
| 63 | tools/final_summary_v2.js | Final summary v2 | obsolete_script | MED | tools/ | LOW | None | DELETE | N/A | Debug script |
| 64 | tools/find-api.js | Find API | obsolete_script | MED | tools/ | LOW | None | DELETE | N/A | Debug script |
| 65 | tools/find_missing.js | Find missing | obsolete_script | MED | tools/ | LOW | None | DELETE | N/A | Debug script |
| 66 | tools/find_remaining.js | Find remaining | obsolete_script | MED | tools/ | LOW | None | DELETE | N/A | Debug script |
| 67 | tools/flashscore-scraper-v1.js | Flashscore scraper | old_worker | MED | tools/ | LOW | None | DELETE | N/A | Old scraper, not in use |
| 68 | tools/full-analysis.js | Full analysis | obsolete_script | MED | tools/ | LOW | None | DELETE | N/A | Debug script |
| 69 | tools/fund_server.js | Fund server | obsolete_script | MED | tools/ | LOW | None | DELETE | N/A | Fund server, not V4 |
| 70 | tools/get-ht-results.js | Get HT results | obsolete_script | MED | tools/ | LOW | None | DELETE | N/A | Debug script |
| 71 | tools/get-ht-v2.js | Get HT v2 | obsolete_script | MED | tools/ | LOW | None | DELETE | N/A | Debug script |
| 72 | tools/get-ht-v3.js | Get HT v3 | obsolete_script | MED | tools/ | LOW | None | DELETE | N/A | Debug script |
| 73 | tools/get-results.js | Get results | obsolete_script | MED | tools/ | LOW | None | DELETE | N/A | Debug script |
| 74 | tools/get_remaining.js | Get remaining | obsolete_script | MED | tools/ | LOW | None | DELETE | N/A | Debug script |
| 75 | tools/ht-debug.js | HT debug | obsolete_script | MED | tools/ | LOW | None | DELETE | N/A | Debug script |
| 76 | tools/ht-debug2.js | HT debug 2 | obsolete_script | MED | tools/ | LOW | None | DELETE | N/A | Debug script |
| 77 | tools/ht-live-check.js | HT live check | obsolete_script | MED | tools/ | LOW | None | DELETE | N/A | Debug script |
| 78 | tools/jiebao-scraper.js | Jiebao scraper | old_worker | MED | tools/ | LOW | None | DELETE | N/A | Old scraper, not in use |
| 79 | tools/jiebao_fetch.js | Jiebao fetch | obsolete_script | MED | tools/ | LOW | None | DELETE | N/A | Debug script |
| 80 | tools/jiebao_nowscore.js | Jiebao nowscore | obsolete_script | MED | tools/ | LOW | None | DELETE | N/A | Debug script |
| 81 | tools/parse_all_apr26.js | Parse all Apr26 | obsolete_script | MED | tools/ | LOW | None | DELETE | N/A | Debug script |
| 82 | tools/parse_bologna.js | Parse Bologna | obsolete_script | MED | tools/ | LOW | None | DELETE | N/A | Debug script |
| 83 | tools/post-cron.js | Post cron | obsolete_script | MED | tools/ | LOW | None | DELETE | N/A | Old cron script |
| 84 | tools/prematch-check.js | Prematch check | obsolete_script | MED | tools/ | LOW | None | DELETE | N/A | Debug script |
| 85 | tools/quick-verify.js | Quick verify | obsolete_script | MED | tools/ | LOW | None | DELETE | N/A | Debug script |
| 86 | tools/raw_text_search.js | Raw text search | obsolete_script | MED | tools/ | LOW | None | DELETE | N/A | Debug script |
| 87 | tools/scrape_page.js | Scrape page | obsolete_script | MED | tools/ | LOW | None | DELETE | N/A | Debug script |
| 88 | tools/scroll_long.js | Scroll long | obsolete_script | MED | tools/ | LOW | None | DELETE | N/A | Debug script |
| 89 | tools/search_all_data.js | Search all data | obsolete_script | MED | tools/ | LOW | None | DELETE | N/A | Debug script |
| 90 | tools/search_apr26_matches.js | Search Apr26 | obsolete_script | MED | tools/ | LOW | None | DELETE | N/A | Debug script |
| 91 | tools/simple_parse.js | Simple parse | obsolete_script | MED | tools/ | LOW | None | DELETE | N/A | Debug script |
| 92 | tools/team-cn-map.js | Team CN map | obsolete_script | MED | tools/ | LOW | None | DELETE | N/A | Debug script |
| 93 | tools/total_page_search.js | Total page search | obsolete_script | MED | tools/ | LOW | None | DELETE | N/A | Debug script |
| 94 | tools/update-stats.js | Update stats | obsolete_script | MED | tools/ | LOW | None | DELETE | N/A | Debug script |
| 95 | tools/v17_details.js | V17 details | obsolete_script | MED | tools/ | LOW | None | DELETE | N/A | Old V17 debug |
| 96 | tools/v17_full_check.js | V17 full check | obsolete_script | MED | tools/ | LOW | None | DELETE | N/A | Old V17 debug |
| 97 | tools/v17_vs_v24_comparison.js | V17 vs V24 | obsolete_script | MED | tools/ | LOW | None | DELETE | N/A | Old comparison |
| 98 | tools/v24_results.js | V24 results | obsolete_script | MED | tools/ | LOW | None | DELETE | N/A | Old V24 debug |
| 99 | tools/v25_backtest.js | V25 backtest | obsolete_script | MED | tools/ | LOW | None | DELETE | N/A | Old backtest |
| 100 | tools/verify-0429-v2.js | Verify 0429 v2 | obsolete_script | MED | tools/ | LOW | None | DELETE | N/A | Debug script |
| 101 | tools/verify-0429.js | Verify 0429 | obsolete_script | MED | tools/ | LOW | None | DELETE | N/A | Debug script |
| 102 | tools/verify-predictions.js | Verify predictions | obsolete_script | MED | tools/ | LOW | None | DELETE | N/A | Debug script |
| 103 | tools/verify_v26.js | Verify V26 | obsolete_script | MED | tools/ | LOW | None | DELETE | N/A | Debug script |
| 104 | tools/verify_v26_v2.js | Verify V26 v2 | obsolete_script | MED | tools/ | LOW | None | DELETE | N/A | Debug script |
| 105 | tools/verify_v26_v3.js | Verify V26 v3 | obsolete_script | MED | tools/ | LOW | None | DELETE | N/A | Debug script |
| 106 | .v2_football_quant/engine/v3_dashboard.py | V3 dashboard | V33/V38 reference | MED | v2_football_quant/engine/ | LOW | V2 code | KEEP_FORMAL_V2 | v2_football_quant/engine/ | V2 ecosystem |

## Formal V4 Candidates

Files identified as formal V4 candidates (from v2_football_quant/engine/v4_*.py):

- v4_api_budget_audit.py
- v4_calibration_report.py
- v4_daily_recommendation_brief.py
- v4_dashboard.py
- v4_data_logger.py
- v4_display_name_normalizer.py
- v4_ht_result_validator.py
- v4_ht_result_verifier.py
- v4_job_runner.py
- v4_live_capture_audit.py
- v4_live_capture_scheduler.py
- v4_live_odds_collector.py
- v4_live_stats_snapshot.py
- v4_master_run.py
- v4_match_intelligence.py
- v4_monthly_report.py
- v4_openclaw_brief.py
- v4_ops_alert.py
- v4_ops_dashboard.py
- v4_ops_doctor.py
- v4_ops_status.py
- v4_ops_summary.py
- v4_progress_reporter.py
- v4_qq_formatter.py
- v4_release_freeze.py
- v4_report.py
- v4_result_attribution.py
- v4_review_guard.py
- v4_review_renderer.py
- v4_review_report.py
- v4_review_result_refresh.py
- v4_review_with_watchdog.py
- v4_runner.py
- v4_scan_and_brief.py
- v4_scan_worker.py
- v4_scout_report.py
- v4_sh_result_verifier.py
- v4_sh_strategy_eval.py
- v4_strategy_eval.py
- v4_universe_gap_repair.py
- v4_validation_progress.py
- v4_versioning.py
- v4_weekly_report.py

All candidates currently reference A/B/C/SKIP grading. See V4_FORMAL_FILE_WHITELIST.md for eligibility verification.

## Inventory Notes

- `KEEP_FORMAL_V2` items are V2 production system modules and must not be touched.
- `KEEP_FORMAL_V4` items are V4 candidate modules and require formal V4 whitelisting.
- All tools/ `.js` files marked DELETE are legacy debug/experimental scripts with no current production reference.
- Archived docs go to `docs/archive/system_legacy/`.
- Archived data stays in place but must have DEPRECATED marker.
