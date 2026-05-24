# V4-LIVE-BET-TRACKER-MOBILE-COMPACT-AND-CANDIDATE-PREFILL-HOTFIX-20260526

## 结果
- 已完成 iPhone 紧凑版改造：首屏可直接完成实盘记录。
- 已新增候选预填：可从今日官方 A/B 候选自动带出队名、联赛、评级、剧本、HT分。
- 已修复测试污染口径：测试/VOID 不再计入 bankroll 与 ROI。
- 未自动下注、未连接皇冠、未保存账号信息。

## 关键审计结论
1. 为什么之前页面不实用：
- 表单字段过多且平铺，核心操作不在首屏。
- 每次需要手填球队/联赛，移动端录入成本高。

2. 是否还需要手填球队名：
- 不需要。默认用“选择今日候选”自动带入；手工仅作为兜底。

3. 今日候选如何自动带入：
- 新增 API：`GET /api/live_bets/candidates?date=YYYYMMDD`
- 优先读当天 `v3v4_dashboard_candidate_view_YYYYMMDD.json` 的 A/B。
- 当天未就绪则 fallback 到 last_good，并在页面显示 `候选来源日期`。

4. 默认日期是否已修复：
- 已修复，前端使用 `todayLocal()`，不再固定旧日期。

5. 累计 ROI 是否已修复：
- 已修复。`turnover=0` 显示 `N/A`，不再显示 102.50%。

6. 当前本金 30102.50 是否为测试污染：
- 是。来源为测试 BET 已结算记录（net=102.5）。
- 已标记 `is_test=true`，summary 过滤后当前本金恢复 `30000.00`。

7. NO_BET 如何记录：
- 新增“记录为未下注”按钮 + 快捷原因：
  盘口太高 / 水位太差 / 已进球 / 红牌异常 / 超过风控 / 手动跳过 / 非57联赛。

8. iPhone 页面是否首屏可操作：
- 是。首屏包含：sticky 总览、建议摘要、日期+候选、评级+盘口+水位+stake、入场字段、BET/NO_BET 按钮。

9. 是否自动下注：
- 否。

10. 是否连接皇冠：
- 否。

11. 是否 cloud publish：
- 否。

12. 是否可明天实盘使用：
- 可以。若当日候选未 ready，会自动回退 last_good 并提示来源日期。

## 变更文件
- `tools/live_bet_store.py`
- `tools/serve_live_bet_tracker.py`
- `data/runtime/dashboard/live_bet_tracker.html`
- `tools/check_v4_live_bet_tracker.py`
- `data/runtime/status/v4_live_bet_tracker_mobile_compact_issue_audit_20260526.json`
- `data/runtime/status/v4_live_bet_tracker_mobile_compact_and_candidate_prefill_hotfix_20260526.json`
