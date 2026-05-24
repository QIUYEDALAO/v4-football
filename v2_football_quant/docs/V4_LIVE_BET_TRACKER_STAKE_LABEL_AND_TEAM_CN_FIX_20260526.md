# V4-LIVE-BET-TRACKER-STAKE-LABEL-AND-TEAM-CN-FIX-20260526

## 结论
- 已把 stake 输入文案改为清晰中文：`下注金额（建议值，可手改）`。
- 已补充提示：系统建议金额与“最终实际下注金额”的关系，且 stake=0 时提示优先 NO_BET。
- 已修复 candidates API 中文显示链路，当前 official 候选中文缺失率为 0%。

## 本轮变更
1. 页面文案（live_bet_tracker.html）
- 移除：`建议 stake / 实际 stake`
- 新增：`下注金额（建议值，可手改）`
- 新增辅助文案：
  - `系统建议：xxx 元；你可按实际下注金额修改。`
  - `系统建议跳过；如仍需记录，请用 NO_BET 或手工填写。`

2. candidates API（serve_live_bet_tracker.py）
- 强制复用 `team_cn_resolver`。
- 对上游占位字符串 `中文名缺失：...` 不当作有效 hint。
- 对 `_en` 字段中的中文文本做兜底回填，避免卡片主标题继续显示缺失占位。

3. alias 扩充（team_cn_aliases.json）
- 补齐：Liverpool, Brentford, Club Brugge, Gent。

4. checker（check_v4_live_bet_tracker.py）
- 检查新 stake 文案存在、旧文案不存在。
- 检查 official 候选中文缺失率：
  - >0 记 WARN
  - >20% 记 BLOCKER

## 本地验证
- `http://127.0.0.1:8766/live_bet_tracker.html` -> 200
- `http://192.168.1.2:8766/live_bet_tracker.html` -> 200
- `/api/live_bets/candidates?date=20260525` -> official=10, missing=0, rate=0%
- `python3 tools/check_v4_live_bet_tracker.py` -> PASS

## 约束确认
- 未自动下注
- 未连接皇冠
- 未保存凭据
- 未改策略
- 未改 candidate 评级/数量
- 未改 validation
- 未 cloud publish
- 未改 cron
