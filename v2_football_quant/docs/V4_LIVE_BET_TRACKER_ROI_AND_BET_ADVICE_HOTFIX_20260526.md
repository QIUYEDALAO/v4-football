# V4-LIVE-BET-TRACKER-ROI-AND-BET-ADVICE-HOTFIX-20260526

## 结果概览
- 已修复 ROI 计算与展示口径：ROI 始终按 `净盈亏 / 总投注额`。
- 已新增“今日投注建议”模块与日内风控提示。
- 已实现表单按评级+盘口自动建议 stake，stake=0 时显示“建议跳过，不建议下注”。
- 未删除 live_bets 记录，未改已结算记录，未触发 scan/validation/QQ/cloud/cron。

## 根因
- 原页面显示依赖 `today_roi/cumulative_roi * 100`，缺少“turnover=0”的显示保护。
- 在“净盈亏有值但投注额为 0”的异常场景下，UI 可能出现误导性 ROI。

## 修复内容
1. `tools/live_bet_store.py`
- 新增 `today_turnover` / `cumulative_turnover`（与 stake 同源）。
- `today_roi` / `cumulative_roi` 在 turnover=0 时返回 `null`。
- 新增 `today_roi_pct` / `cumulative_roi_pct`（只作辅助字段）。
- `current_bankroll` 保持 `initial_bankroll + cumulative_net_pnl`。

2. `data/runtime/dashboard/live_bet_tracker.html`
- 新增“今日投注建议”卡片（A/B/C/SKIP 与风控规则）。
- 新增 `roiText()`：turnover<=0 或 roi=null 时显示 `N/A`。
- KPI 改为优先读取 `today_turnover` / `cumulative_turnover`。
- 强化风险状态文案。
- stake 自动建议逻辑接入提示文案（`stake_hint`）。

3. `tools/check_v4_live_bet_tracker.py`
- 增加页面建议模块关键文案检查。
- 增加 ROI 误算守卫：
  - turnover=0 时 cumulative_roi 不得非 0；
  - turnover>0 时 cumulative_roi 不得等于 cumulative_net_pnl。
- 调整为只读检查，不再写入测试投注，避免数据污染。

## 本地验证
- `python3 tools/check_v4_live_bet_tracker.py` => PASS
- `http://127.0.0.1:8766/live_bet_tracker.html` => HTTP 200
- `http://192.168.1.2:8766/live_bet_tracker.html` => HTTP 200
- `/api/live_bets/cumulative` 返回累计 summary 正常。
- `/api/live_bets/summary?date=20260527`（无记录日）返回 `today_turnover=0, today_roi=null`，页面显示 `N/A`。

## 禁止项确认
- auto_bet=false
- bookmaker_login=false
- bookmaker_credentials_saved=false
- live_bet_records_deleted=false
- settled_records_modified=false
- full_scan_ran=false
- validation_recomputed=false
- strategy_changed=false
- candidate_changed=false
- QQ_push=false
- cloud_publish=false
- cron_modified=false
- secrets_printed=false
- secrets_saved=false
