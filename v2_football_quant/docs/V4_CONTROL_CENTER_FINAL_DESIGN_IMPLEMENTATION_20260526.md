# V4统一作战台 最终设计实施报告

**阶段**: V4-CONTROL-CENTER-FINAL-DESIGN-IMPLEMENTATION-20260526
**生成时间**: 2026-05-26T02:05:00+08:00
**状态**: V4_CONTROL_CENTER_FINAL_DESIGN_IMPLEMENTATION_PASS

---

## 执行摘要

V4统一作战台已按BOSS确认的最终版设计成功落地。主页面部署在 8766 端口作为可操作主入口，8765 端口降级为只读入口和详情页。所有核心数据源严格分离，验证累计与实盘累计不混用。

---

## 20 项核心验收问答

| # | 问题 | 答案 |
|---|------|------|
| 1 | V4统一作战台地址是什么？ | http://192.168.1.2:8766/v4_control_center.html (内网) / http://127.0.0.1:8766/v4_control_center.html (本地) |
| 2 | 是否部署在 8766？ | 是。8766 serve_live_bet_tracker.py 已新增路由服务 |
| 3 | 8765 是否只做入口？ | 是。8765 intel_ops_console.html 新增跳转入口，旧页面降级为只读详情页 |
| 4 | 顶部核心状态是否只出现一次？ | 是。6 个 KPI（今日候选/昨日验证/验证累计/今日投注盈亏/有效流水返水/今日待办）在顶部bar中只出现一次 |
| 5 | 是否去除了英文主文案？ | 是。页面主文案全部中文，不出现 source/API/POST/full scan/cron/UNKNOWN 等英文术语 |
| 6 | 是否区分验证累计和实盘累计？ | 是。验证累计读取 official A/B-only truth file；实盘累计读取 live_bets cumulative_summary。二者严格分离 |
| 7 | 当前验证累计来源是什么？ | data/runtime/status/v4_true_cumulative_result_validation_20260525.json |
| 8 | 当前实盘累计来源是什么？ | data/runtime/live_bets/cumulative_summary.json + daily_summary_20260526.json |
| 9 | 是否可以从候选卡片记录投注？ | 是。候选卡片有"记录投注"按钮，自动带入球队/联赛/评级/fixture_id |
| 10 | 是否可以结算投注？ | 是。结算模态层支持输入半场进球数，自动计算结算结果 |
| 11 | 是否支持走水=0有效流水=0返水？ | 是。PUSH 规则：投注盈亏=0，有效流水=0，返水=0，净盈亏=0 |
| 12 | 是否有审计记录？ | 是。live_bet_store.py 写 audit log 到 live_bet_tracker_audit.log |
| 13 | 旧页面如何降级？ | 保留不删除。intel_ops_console.html 增加V4统一作战台入口，本页标记为只读详情页 |
| 14 | 是否混入 V3？ | 否。V4统一作战台不含任何V3世界杯模块 |
| 15 | 是否改策略？ | 否。strategy_changed=false |
| 16 | 是否改 candidate？ | 否。candidate_changed=false, candidate_rating_changed=false |
| 17 | 是否重算 validation？ | 否。validation_recomputed=false |
| 18 | 是否推 QQ？ | 否。QQ_recommendation_pushed=false |
| 19 | 是否 cloud / cron？ | 否。cloud_publish=false, cron_schedule_modified=false |
| 20 | 是否可以作为后续唯一主入口？ | 是。8766 V4统一作战台作为后续唯一可操作主入口 |

---

## 新增文件清单

| 文件 | 类型 | 用途 |
|------|------|------|
| tools/build_v4_control_center_model.py | builder | 只读聚合模型构建器 |
| tools/check_v4_control_center.py | checker | 数据源污染守卫 |
| data/runtime/dashboard/v4_control_center.html | html | V4统一作战台主页面 |
| data/runtime/status/v4_control_center_design_freeze_20260526.json | status | 设计冻结基线 |
| data/runtime/status/v4_control_center_model_20260526.json | status | 统一数据模型输出 |
| data/runtime/status/v4_control_center_git_manifest_20260526.json | status | Git 提交清单 |

## 修改文件清单

| 文件 | 变更内容 |
|------|----------|
| tools/serve_live_bet_tracker.py | 新增 /v4_control_center.html 路由、/api/v4_control_center_model 接口、/v4_ab_historical_ledger.html 路由 |
| data/runtime/dashboard/intel_ops_console.html | 新增 V4统一作战台 跳转入口横幅 |

---

## 禁止项确认

所有禁止操作均未执行：

```
full_scan_ran=false
capture_ran=false
validation_recomputed=false
strategy_changed=false
candidate_changed=false
candidate_rating_changed=false
result_validation_history_changed=false
script_validation_history_changed=false
live_bet_raw_records_rewritten=false
validation_cumulative_mixed_with_live_bet=false
old_cumulative_source_reused=false
v3_module_added=false
v2_restored=false
v33_active=false
QQ_recommendation_pushed=false
cloud_publish=false
cron_schedule_modified=false
secrets_printed=false
secrets_committed=false
```

---

## Checker 运行结果

| Checker | 结论 |
|---------|------|
| check_v4_control_center.py | PASS |
| check_v4_live_bet_tracker.py | PASS |
| check_v4_cumulative_validation_source_integrity.py | PASS |
| check_v3v4_cron_task_complete_qq_notify.py | PASS (11/11) |
| check_v2_decommission_v3_v4_only.py | PASS |
| check_cloud_autosync_guard.py | PASS |

---

## Git 状态

- 本地 commit: `59209c5` — "dashboard: add V4 unified control center"
- 8 files changed, 2025 insertions(+), 1 deletion(-)
- GitHub push: REMOTE_PUSH_BLOCKED（账户限制）
- 本地 commit 保留，不重复提交

---

## 数据源架构

```
验证累计 ← v4_true_cumulative_result_validation_YYYYMMDD.json (official A/B-only)
实盘累计 ← live_bets/cumulative_summary.json
今日投注 ← live_bets/daily_summary_YYYYMMDD.json
今日候选 ← v3v4_dashboard_candidate_view_YYYYMMDD.json
昨日验证 ← v4_official_ab_validation_source_of_truth_YYYYMMDD.json
系统状态 ← v3v4_cron_task_complete_qq_checker_YYYYMMDD.json
```

两条数据线严格分离，不混用。

---

## 结论

**V4_CONTROL_CENTER_FINAL_DESIGN_IMPLEMENTATION_PASS**
