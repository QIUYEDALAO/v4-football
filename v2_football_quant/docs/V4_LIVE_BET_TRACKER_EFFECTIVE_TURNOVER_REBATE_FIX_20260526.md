# V4_LIVE_BET_TRACKER_EFFECTIVE_TURNOVER_REBATE_FIX_20260526

## 结果
已完成 effective turnover 返水修复，走水不再产生返水，且风险状态改为按投注盈亏（gross）判断。

## 关键修复
1. `tools/live_bet_settlement.py`
- 新增 `effective_turnover` 输出。
- 返水改为 `rebate = effective_turnover * rebate_rate`。
- `PUSH/VOID/PENDING` 强制 `effective_turnover=0, rebate=0`。

2. `tools/live_bet_store.py`
- summary 统一按公式重算（不信任旧行内 rebate 字段）。
- 新增字段：
  - `today_stake_amount`
  - `today_effective_turnover`
  - `today_betting_roi`
  - `today_effective_roi`
  - cumulative 对应字段
- 风险状态基准标记为 `risk_status_base=today_gross_pnl`。
- 新增 `rebate_formula_version=effective_turnover_v1`。

3. `data/runtime/dashboard/live_bet_tracker.html`
- KPI 拆分显示：投注本金、投注盈亏、有效流水、返水、净盈亏、ROI。
- 风险状态改为基于 `today_gross_pnl`。

4. checker
- 新增 `tools/check_v4_live_bet_tracker_rebate.py`。
- 修正 `tools/check_v4_live_bet_tracker.py` 误报逻辑。

## BOSS 关心样例（428 走水）
- `today_stake_amount=428.0`
- `today_gross_pnl=0.0`
- `today_effective_turnover=0.0`
- `today_rebate=0.0`
- `today_net_pnl=0.0`
- `today_roi_pct=0.0`
- `current_bankroll=30000.0`

## 必答
1. 之前为什么走水会显示 +10.70？
旧逻辑按 stake 直接算返水（`rebate = stake * 0.025`），导致 PUSH 也返现。

2. 新返水公式是什么？
`rebate = effective_turnover * 0.025`。

3. PUSH 是否返水？
否，`rebate=0`。

4. LOSS 如何算返水？
`effective_turnover=stake`，`rebate=stake*0.025`。

5. WIN 如何算返水？
`effective_turnover=win_profit`，`rebate=win_profit*0.025`。

6. HALF_WIN / HALF_LOSS 如何算返水？
- HALF_WIN：按 half_win_profit
- HALF_LOSS：按 half_loss_amount
均乘 2.5%。

7. 今日 428 走水修正后显示什么？
显示 0 返水、0 净盈亏、0 ROI（投注本金仍 428）。

8. 是否修改了原始投注记录？
否。

9. 是否只重建 summary？
是。

10. 风险状态现在按什么判断？
按 `today_gross_pnl`。

11. 是否保存皇冠账号？
否。

12. 是否自动下注？
否。

13. 是否改策略？
否。

14. 是否 cloud / QQ / cron？
均否。

15. 是否需要 BOSS 刷新页面验收？
需要，刷新 `8766` 页面可见新口径。

## 最终结论
V4_LIVE_BET_EFFECTIVE_TURNOVER_REBATE_FIX_PASS

## 禁止项确认
- raw_live_bet_records_modified=false
- auto_bet=false
- bookmaker_login=false
- bookmaker_credentials_saved=false
- strategy_changed=false
- candidate_changed=false
- validation_changed=false
- full_scan_ran=false
- capture_ran=false
- QQ_push=false
- cloud_publish=false
- cron_modified=false
- secrets_printed=false
- secrets_committed=false
