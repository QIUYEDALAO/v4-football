# V4_TODAY_LIVE_BET_DATE_ISOLATION_FIX_20260526

## 结论
- 已完成“今日实盘日期隔离”修复。
- 今日无真实在途投注时，作战台“今日已投”显示 `0.00`。
- 默认金额 `428` 仍保留为候选输入默认值，但不再计入今日已投。

## 核心修复
1. `tools/build_v4_control_center_model.py`
- 新增按 `today_date` 原始 jsonl 重算今日实盘状态。
- `today_stake/today_real_stake` 改为仅统计当日有效在途单（不含 VOID/test）。
- `today_default_stake` 单独字段输出，和今日真实投注彻底分离。
- 新增 `cross_day_open_bets_count/cross_day_open_bet_items`。
- 候选状态改为 `fixture_id + record_date(today)` 匹配，跨日命中仅写 forensic，不污染主状态。

2. `data/runtime/dashboard/v4_control_center.html`
- 文案“投注本金”改为“今日已投”。
- 绑定 `live_bet_summary.today_real_stake` 显示。
- 存在跨日在途单时显示“跨日待结算 N 笔（不计入今日已投）”。

3. 新增 checker
- `tools/check_v4_today_live_bet_date_isolation.py`
- 拦截 today/default 混淆、候选状态跨日污染、前端旧文案残留。

## 结果验收
- today_real_stake: `0.0`
- today_default_stake: `428.0`
- candidate state: `already_bet=false`, `settled=false`（不再误显示已结算）
- 待补验: 0（与昨日2场口径一致）

## 回答 BOSS 关心点
1. 428 的来源是什么？
- 历史 daily summary / 默认输入值链路。
2. 是否来自昨日投注？
- 存在跨日/历史残留影响，已隔离出今日口径。
3. 是否来自默认投注金额？
- 是，428 现在只作为默认输入金额。
4. 今日真实投注数是多少？
- 当前模型为 0（无今日有效在途实投）。
5. 今日已投现在是多少？
- `0.00`。
6. 默认金额现在是多少？
- `428.00`。
7. 候选卡状态是否按 today_date + fixture_id 匹配？
- 是。
8. 是否清除了今日候选误显示已结算？
- 是。
9. 跨日待结算是否单独显示？
- 是（如存在则单独提示，不计入今日已投）。
10. 是否修改 live bet 原始记录？
- 否。
11. 是否删除昨日记录？
- 否。
12. 是否改策略？
- 否。
13. 是否改 candidate？
- 否。
14. 是否重算 validation？
- 否。
15. 是否推 QQ？
- 否。
16. 是否改 cloud / cron？
- 否。
