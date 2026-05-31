# V4_RF_PROMOTION_MARKET_VETO_POLICY_FIX (2026-05-31)

## 本轮目标
修复 RF promotion 中“盘口 veto 权限过大”问题，恢复以下口径：
- RF 是主因子。
- H2H 只加分，不降级，不硬杀，不制造 A/B。
- Opening Market 只做确认、降级、风险提示、极端熔断。

## 根因
旧链路中，`MARKET_HARD_VETO` 在 shadow/promotion 端会把大量 RF A/B 信号直接打到 SKIP 侧，导致 20260531 全量 replay 出现“RF 信号存在但 promotion 近乎清空”的偏差。

同时，盘口赔率源存在数值编码差异（例如 `67` 实际应解释为 `1.67`），放大了 veto 触发概率。

## 策略修复
### 1) Market 冲突分层
新增并透传：
- `opening_market_conflict_level`
- `opening_market_action`
- `market_veto_severity`
- `market_veto_reason`
- `market_policy_version`
- `dryrun_action`

分层动作：
- `MARKET_CONFIRM`：保持级别，仅加信心。
- `MARKET_LIGHT_CONFLICT`：轻降级（A→B，B→C）。
- `MARKET_STRONG_CONFLICT`：强降级（强 RF 可进 C观察，弱 RF 才 SKIP）。
- `MARKET_EXTREME_VETO`：仅极端异常才直接 SKIP。
- `MARKET_NO_DATA`：不升A，但强 RF 保留 B/C观察。
- `MARKET_NO_MARKET`：保持 skip（不进入待投）。

### 2) H2H bonus-only 保持
- `H2H_LOW_SAMPLE` 仅标注忽略，不参与降级。
- `H2H_NO_BONUS` 不降级。
- `H2H_STRONG_BONUS` 仅提升信心，不制造 A/B。

### 3) 赔率值标准化
对赔率编码 `67/26/...` 做标准化（解释为 `1.67/1.26/...`），避免误触发强反向。

## Replay 结果（20260531，本地产物重放）
- 不重扫、不调用 API。
- official 仍 `0/0/94`（不变）。
- dryrun 变为：
  - `DRYRUN_A=0`
  - `DRYRUN_B=2`
  - `DRYRUN_C_OBSERVE=58`
  - `DRYRUN_SKIP=33`
  - `DRYRUN_EXTREME_VETO=1`

结论：普通盘口反向不再一刀切清空 RF A/B，大量样本回落到 C观察层，符合“RF主因子 + 盘口风险修正”预期。

## 安全边界确认
本轮未做以下操作：
- 未修改 official grade
- 未写 pending_bet_candidates
- 未进入 validation
- 未修改 live bet
- 未推 QQ
- 未修改 cron
- 未修改 DEFAULT_RULES / A/B 阈值
- 未重扫 / 未调用 API

## 后续
需要 OpenClaw 基于最新 dryrun artifact 做后续复核报告；本轮仍是 shadow/promotion policy 修复，不是正式推荐切换。
