# V4_MARKET_BOOKMAKER_FALLBACK_FIX (2026-05-31)

## 背景
本轮修复 V4 在半场大小球（HT OU）解析中的 Pinnacle-only 过滤过窄问题。

旧逻辑在 `engine/v4_runner.py::_capture_ht_ou_lines()` 中只接受 Pinnacle：
- 若某场 API 有赔率、有 HT OU，但无 Pinnacle，则会被误判为 `MARKET_NO_DATA`。

## 问题证据
在 20260531 dryrun B 样本中，存在“有 bookmaker + 有 HT OU + 无 Pinnacle”场景：
- `1518102` Thanh Hóa vs Phu Dong（越南联）
- `1544804` Singapore vs Mongolia（友谊赛）

## 修复策略
1. 保留 Pinnacle 优先。
2. 当 Pinnacle 无 HT OU 时，按优先级回退到可信 bookmaker：
   - Pinnacle
   - Bet365
   - William Hill
   - 10Bet
   - Marathonbet
   - 1xBet
   - Betfair
   - 其他（仅当明确存在 HT OU）
3. 严格只接受 HT OU：
   - 必须具备 First Half / 1st Half / Half Time / HT / 1H 语义
   - 且具备 Over/Under/Goals 语义
4. 显式拒绝全场盘口冒充半场盘口：
   - Match Goals / Full Time / Total Goals 等

## 新增字段
新增并透传：
- `opening_market_bookmaker_used`
- `opening_market_bookmaker_priority`
- `opening_market_market_name`
- `opening_market_bet_name`
- `opening_market_source`（`PINNACLE_PRIMARY` / `BOOKMAKER_FALLBACK` / `NO_HT_OU` / `NO_ODDS`）
- `no_ht_ou_reason`

当 API 有 odds 但没有 HT OU 时：
- `opening_market_data_status = API_HAS_ODDS_BUT_NO_HT_OU`
- 保持 `opening_market_support_status = MARKET_NO_DATA`

## 为什么不能用全场 OU 冒充半场 OU
半场与全场在进球分布、赔率结构、策略语义上都不同。将全场盘口误作半场盘口会直接污染 shadow 市场判断，造成错误 confirm/veto。

## 预计受益场景
- 非 Pinnacle 覆盖联赛或友谊赛中，API 已有 HT OU 的比赛不再被误判为 `MARKET_NO_DATA`。

## 仍然无解的场景
以下场景在 API 本身无可用赔率时，仍应保持 NO_DATA：
- U19 友谊赛（API 真无 odds）
- 阿尔巴超部分场次（API 真无 odds）

## 本轮边界与安全
- 未重新全量 scan
- 未推 QQ
- 未改 cron
- 未写正式推荐
- 未写 pending_bet_candidates
- 未重算 validation
- 未修改 official grade

## 后续
需要由 OpenClaw 按既有流程重跑 dryrun 观察产物口径变化（本轮仅做代码修复与最小验证）。
