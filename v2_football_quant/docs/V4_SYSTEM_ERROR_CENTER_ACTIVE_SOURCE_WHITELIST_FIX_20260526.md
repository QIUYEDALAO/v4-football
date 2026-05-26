# V4_SYSTEM_ERROR_CENTER_ACTIVE_SOURCE_WHITELIST_FIX_20260526

- Phase: V4-SYSTEM-ERROR-CENTER-ACTIVE-SOURCE-WHITELIST-FIX-20260526
- Generated at: 2026-05-27T00:37:27.034668

## 结果概览
- false_positive_freeze / freeze / audit / verify / manifest / report 过程产物已从 ACTIVE 移除。
- ACTIVE 由 8 降至 4；BLOCKER 由 3 变为 2。
- 当前 ACTIVE 仅保留未恢复且符合白名单条件的真实失败项。

## 根因
1. 之前 collector 主要按关键词和计数粗判，过程文件（freeze/audit/verify）被误当 ACTIVE。
2. phase 级恢复判定不足，中间产物无法被最终 PASS/最终阶段结果覆盖。
3. 采集器自身及周边过程文件没有完整 active-source 白名单/黑名单隔离。

## 本轮修复
1. 在 `tools/collect_v4_system_error_summary.py` 新增 ACTIVE 来源白名单和 process_artifact 排除逻辑。
2. 增强 JSON 结构判定：优先解析 `final_status/conclusion/status/all_pass/ok/blockers/errors`，不再靠文件名关键词粗判。
3. 增强 phase 级恢复：同 phase 后续 PASS/最终结果可覆盖中间过程产物。
4. 防止 summary 自反馈和过程产物进入 ACTIVE。
5. 加固 `tools/check_v4_system_error_center.py`，新增 process artifact 与 resolved-in-active 拦截。
6. 修复 8766 模型读取位点（`tools/serve_live_bet_tracker.py`）：改为按最新 mtime 取 model，避免 UTC 日期错位导致读旧模型。

## 当前状态
- active_blocker_count: 2
- active_error_count: 4
- recent_error_count_24h: 10
- system_error_status: BLOCKER

ACTIVE 残留（当前仍未恢复，非本轮误报）：
- check_v3v4_dashboard_daily_auto_update_pipeline_result_20260525.json (BLOCKER)
- api_controlled_ingest_real_20260524.json (BLOCKER)
- v4_control_center_codex_frontend_binding_complete_20260526.json (FAIL)
- qq_notify_done_V4_DAILY_SCAN_READONLY_20260526_20260526_20260526_120007.json (FAIL)

## 必答
1. 为什么上一轮修完还有 3/8？
- 因为 collector 仍把过程产物（freeze/audit/verify/phase中间文件）视作 ACTIVE 来源。
2. 是否因为 freeze/audit/verify 过程文件误入 ACTIVE？
- 是。
3. 是否因为 phase-level resolved 判断不足？
- 是。
4. 是否修复 ACTIVE 来源白名单？
- 是。
5. 当前 active_blocker_count 是多少？
- 2
6. 当前 active_error_count 是多少？
- 4
7. 当前 recent_error_count_24h 是多少？
- 10
8. false_positive_freeze 是否还在 ACTIVE？
- 否。
9. ACTIVE 是否还显示已恢复？
- 否（collector 侧已禁止 resolved=true 进入 ACTIVE）。
10. 顶部现在显示什么？
- 按当前真实计数显示 `BLOCKER` 对应状态。
11. 是否展示 raw log？
- 否。
12. 是否泄露 secret？
- 否。
13. 是否自动修复/retry/kill？
- 否。
14. 是否运行 scan/validation？
- 否。
15. 是否改策略/candidate/live bet/cron？
- 否。
16. BOSS 是否可以刷新验收？
- 可以。

## 禁止项确认
- freeze_not_active=true
- audit_not_active=true
- verify_not_active=true
- manifest_not_active=true
- report_not_active=true
- resolved_not_in_active=true
- phase_resolution_fixed=true
- raw_logs_exposed=false
- secrets_exposed=false
- kill_button_added=false
- retry_button_added=false
- rerun_button_added=false
- full_scan_ran=false
- validation_recomputed=false
- strategy_changed=false
- candidate_changed=false
- live_bet_raw_records_modified=false
- QQ_recommendation_pushed=false
- cloud_publish=false
- cron_schedule_modified=false
- secrets_printed=false
- secrets_committed=false

## Final
V4_SYSTEM_ERROR_CENTER_ACTIVE_SOURCE_WHITELIST_FIX_PASS
