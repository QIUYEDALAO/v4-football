# V4_SYSTEM_ERROR_CENTER_FALSE_POSITIVE_FIX_20260526

## 结论
- 本轮已修复“PASS 文件被误判为 ACTIVE BLOCKER”的核心误报链路。
- 异常中心从“关键词粗判”切换为“JSON结构化判定优先”。
- 已加入自反馈隔离，采集器不再扫描自己的 summary/checker/verify/manifest 输出。
- 当前状态为 **WARN_ONLY**：误报已清理，但仍有真实未恢复异常（ACTIVE: 8, BLOCKER: 3）。

## 根因复盘
1. 旧采集器用 `文件名+前200字符关键词` 推断 severity，导致 `conclusion=PASS/all_pass=true/blockers=[]` 文件仍被推入 ACTIVE。
2. 采集器未隔离自身产物，`v4_system_error_summary_*.json` 可被再次扫描，造成递归污染与放大。
3. ACTIVE/RECENT 分流前，resolved 项可能因粗判残留在 ACTIVE 视图。

## 本轮修复
1. `tools/collect_v4_system_error_summary.py`
- 新增 `SELF_FEEDBACK_EXCLUDES`，排除：
  - `v4_system_error_summary_*.json`
  - `v4_control_center_system_error_center_*.json`
  - `v4_system_error_center_checker_*.json`
  - `v4_system_error_center_http_verify_*.json`
  - `v4_system_error_center_git_manifest_*.json`
- 新增 `_status_from_json_obj()`：
  - PASS 信号：`final_status/conclusion/status==PASS`、`all_pass=true`、`ok=true & blockers=[]`、`checker_pass=true`、`errors=[]` 等，不得进 ACTIVE。
  - 异常信号：`FAIL/BLOCKER/BLOCKED`、`all_pass=false`、`ok=false`、`blocker_count>0`、`traceback/exception/exit_code!=0` 才进入异常。
- `collect_status_errors()` 改为“结构化判定优先，关键词判定仅 fallback”。

2. `tools/check_v4_system_error_center.py`
- 重写为口径一致性守卫：
  - PASS/all_pass/blockers=[] 不得进入 ACTIVE
  - self-feedback 不得进入 ACTIVE
  - ACTIVE 不得含 resolved=true
  - `active_error_count/active_blocker_count` 必须与 ACTIVE 明细一致

3. `tools/build_v4_control_center_model.py`
- 保持只读接入，不引入 raw log，不暴露 secret；基于新的 summary 直接映射前端状态。

## 验收结果
- 新采集输出：`data/runtime/status/v4_system_error_summary_20260526.json`
- 当前模型：
  - `active_error_count=8`
  - `active_blocker_count=3`
  - `recent_error_count_24h=0`
  - `system_error_status=BLOCKER`
  - `display_text=阻塞：3 项阻塞`
- 说明：旧“19/41”假阻塞已消除，剩余为真实未恢复项。

## 关键问答
1. 19个阻塞和41个异常是否真实？
- 否，属于误报放大。
2. 误报根因是什么？
- 关键词粗判 + 自反馈递归扫描。
3. 是否因为 PASS checker 被误判？
- 是，已修复。
4. 是否因为 summary 自己扫描自己？
- 是，已修复。
5. 是否已修复 ACTIVE/RECENT 分类？
- 是。
6. 当前 active_blocker_count 多少？
- 3。
7. 当前 active_error_count 多少？
- 8。
8. 当前 recent_error_count_24h 多少？
- 0。
9. 当前前端应显示什么？
- “系统阻塞(3)”（若后续归零则自动显示正常）。
10. 是否展示 raw log？
- 否。
11. 是否泄露 secret？
- 否。
12. 是否自动修复/retry/kill？
- 否。
13. 是否运行 full scan？
- 否。
14. 是否运行 validation？
- 否。
15. 是否改策略？
- 否。
16. 是否改 candidate？
- 否。
17. 是否改 live bet 原始记录？
- 否。
18. 是否改 cron？
- 否。
19. BOSS 是否可以刷新验收？
- 可以，建议强刷页面。

## 最终状态
- `V4_SYSTEM_ERROR_CENTER_FALSE_POSITIVE_FIX_WARN_ONLY`
