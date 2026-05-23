# V3V4 Dashboard Brief Validation Auto Refresh — 20260523

final_conclusion: V3V4_DASHBOARD_BRIEF_VALIDATION_AUTO_REFRESH_PASS
phase: V3V4-DASHBOARD-BRIEF-VALIDATION-AUTO-REFRESH-20260523

## Summary

The V3/V4 dashboard data chain now prioritizes the formal daily V4 brief for the requested date, keeps validation metrics sourced only from formal validation/attribution/review artifacts, and prevents stale candidate data from being displayed as today's data. The dashboard remains V3/V4 only; no V2/V33 active source was restored.

## Answers

1. 今日 brief 是否存在？true.
2. brief 路径是什么？`data/daily_reports/v4_openclaw_brief_20260523.txt`.
3. dashboard 是否使用 20260523 数据？true. Dashboard A/B/C/SKIP = 3/9/9/12 from the 20260523 formal brief.
4. 是否仍显示 20260522 为今日？false.
5. 主验证区是否只显示昨日 + 累计？true.
6. 近7天是否折叠？true. It is under `details.validation-last7` and closed by default.
7. 验证数据来源文件是什么？`v4_yesterday_validation_rebuilt_20260519.json`, `v4_rolling_validation_rebuilt_20260520.json`, `v4_validation_raw_records_20260520.json`.
8. C 是否仍为观察层？true.
9. A+B 是否排除 C？true.
10. 中文队名是否主显示？true.
11. A/B/C 背景是否统一？true.
12. daily refresh 是否可每日自动执行？true; entrypoint supports `--date`, `--mode dry-run|apply`, `--source-window`, `--no-capture`, `--no-push`, `--no-cloud`, and `--strict`.
13. 是否运行 capture？false.
14. 是否真实推 QQ？false.
15. 是否 cloud publish？false.
16. 是否创建 cron？false.
17. 是否可以进入 OpenClaw apply 验收？true.
18. 是否可以进入 Git commit 阶段？false in this phase; BOSS prohibited commit/push.

## Resolvers

- Brief resolver: `tools/v3v4_dashboard_brief_resolver.py`.
- Validation resolver: `tools/v3v4_dashboard_validation_resolver.py`.
- Daily refresh runner: `tools/run_v3v4_intel_ops_console_daily_refresh.py`.
- Auto-refresh checker: `tools/check_v3v4_dashboard_brief_validation_auto_refresh.py`.

## Validation

- `tools/run_v3v4_intel_ops_console_daily_refresh.py --date 20260523 --mode dry-run --source-window auto --no-capture --no-push --no-cloud --strict`: PASS.
- `tools/check_v3v4_dashboard_brief_validation_auto_refresh.py`: PASS.
- `tools/check_v3v4_intel_ops_console_ui_data_validation.py`: PASS.
- `tools/check_v3v4_intel_ops_console_ui.py`: PASS.
- `tools/check_v2_decommission_v3_v4_only.py`: PASS.
- `tools/check_repo_active_file_singleton.py`: PASS.
- `tools/check_openclaw_active_source_manifest.py`: PASS.
- `tools/check_cloud_bundle_excludes_archive.py`: PASS.
- `tools/check_cloud_autosync_guard.py`: PASS.
- `tools/check_gateway_cron_policy_hardening.py`: PASS.
- `tools/check_v4_review_report_only_mode.py`: PASS.
- `tools/check_v3v4_intel_ops_console_daily_refresh_pipeline.py`: PASS.
- HTTP 127.0.0.1: 200.
- HTTP 192.168.1.2: 200.

## Forbidden Actions

- v2_restored=false
- v2_visible_in_dashboard=false
- v2_active_source=false
- v33_active=false
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
