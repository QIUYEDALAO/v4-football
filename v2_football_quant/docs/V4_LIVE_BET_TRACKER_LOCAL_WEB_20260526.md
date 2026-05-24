# V4 Live Bet Tracker Local Web (20260526)

## Phase
V4-LIVE-BET-TRACKER-LOCAL-WEB-20260526

## 交付内容
- 页面: `data/runtime/dashboard/live_bet_tracker.html`
- 本地 API server: `tools/serve_live_bet_tracker.py` (默认端口 8766)
- 数据模型: `tools/live_bet_tracker_schema.py`
- 结算引擎: `tools/live_bet_settlement.py`
- 文件存储: `tools/live_bet_store.py`
- Checker: `tools/check_v4_live_bet_tracker.py`

## 问题回答
1. 页面地址是什么？
- http://127.0.0.1:8766/live_bet_tracker.html
2. API 端口是什么？
- 8766
3. 数据保存在哪里？
- data/runtime/live_bets/v4_live_bets_YYYYMMDD.jsonl
4. 每日 summary 保存在哪里？
- data/runtime/live_bets/daily_summary_YYYYMMDD.json
5. 累计 summary 保存在哪里？
- data/runtime/live_bets/cumulative_summary.json
6. 如何录入一笔 A 级 O0.75？
- 表单中选择 `A` + `O0.75`，输入水位/Stake（默认300可改），点击“添加记录”。
7. 如何结算？
- 在今日列表输入 HT 进球数，点击“一键结算”。
8. 返水如何计算？
- rebate = stake × 0.025；net_pnl = gross_pnl + rebate。
9. 是否自动下注？
- 否。
10. 是否保存皇冠账号？
- 否。
11. 是否 cloud publish？
- 否。
12. 是否可以明天实盘使用？
- 可以（本地/内网模式）。

## 本地验证
- live_bet_tracker 页面 HTTP 200
- API add / settle / void / summary / cumulative 正常
- O0.75/O1/O1.25/O1.5 + 返水计算通过 checker

## 禁止项确认
- auto_bet=false
- bookmaker_login=false
- bookmaker_credentials_saved=false
- full_scan_ran=false
- validation_recomputed=false
- strategy_changed=false
- candidate_changed=false
- QQ_push=false
- cloud_publish=false
- cron_modified=false
- v2_restored=false
- v33_active=false
- secrets_printed=false
- secrets_saved=false

## 最终结论
V4_LIVE_BET_TRACKER_LOCAL_WEB_PASS
