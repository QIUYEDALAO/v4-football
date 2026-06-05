# V3_WC_2026_MATCHDAY_RUNBOOK_PACK

本 runbook 定义 V3 世界杯比赛日赛前情报卡执行流程。它只服务 observation-only 简报，不调用 live API，不生成预测首发，不生成投注建议，不生成盘口/资金流结论，不影响 V4 official。

## 总原则

- 104 canonical schedule 是比赛清单来源。
- 72 场小组赛可生成赛前情报卡；32 场淘汰赛在真实对阵未出前只保留 structural placeholder。
- 官方首发未到前，阵容状态必须固定为 `WAIT_OFFICIAL_LINEUP`。
- 赔率只允许展示 `first_seen_odds`、`last_pre_kickoff_odds`、`odds_observation_delta`。
- 原生开盘/收盘缺失时，不生成盘口变化结论，不生成资金流结论。
- 所有输出必须保留 `observation_only=true`、`betting_recommendation=false`、`affects_v4=false`。

## 比赛日时间线

### T-24h

输出：
- 赛前简报初版。
- Final26 摘要。
- 场馆/环境观察。
- 赔率观察：如本地时间线已有快照，只登记首见赔率。
- 当前缺口。

必须 WAIT_EVENT：
- 官方首发。
- 官方伤停确认源。
- 原生开盘/收盘。
- 淘汰赛真实对阵。

### T-6h

输出：
- 赛前简报更新版。
- 赔率观察：只更新本地观察差。
- 首发状态仍显示 `WAIT_OFFICIAL_LINEUP`，除非官方首发源已到。
- 当前缺口。

必须 WAIT_EVENT：
- 官方首发。
- 官方伤停确认源。
- 原生开盘/收盘。
- 淘汰赛真实对阵。

### T-90m

输出：
- 临场前简报。
- 首发状态检查：官方首发未到时仍为 `WAIT_OFFICIAL_LINEUP`。
- 赔率观察：只展示首见赔率、赛前最后快照候选、观察差。
- 当前缺口。

必须 WAIT_EVENT：
- 官方首发。
- 官方伤停确认源。
- 原生开盘/收盘。
- 淘汰赛真实对阵。

### T-60m

输出：
- 官方首发窗口检查记录。
- 若官方首发源未到，不生成 11 人名单，不猜首发。
- 赛前简报只更新状态与缺口。

必须 WAIT_EVENT：
- 官方首发。
- 官方伤停确认源。
- 原生开盘/收盘。
- 淘汰赛真实对阵。

### T-30m

输出：
- 赛前最后手机简报。
- 赔率观察：只展示 `first_seen_odds`、`last_pre_kickoff_odds`、`odds_observation_delta`。
- 首发未到时继续显示 `WAIT_OFFICIAL_LINEUP`。
- 当前缺口与安全结论。

必须 WAIT_EVENT：
- 官方首发。
- 官方伤停确认源。
- 原生开盘/收盘。
- 淘汰赛真实对阵。

## 输出结构

每个时间点输出保持手机阅读结构：

1. 比赛信息
2. 战备状态
3. 阵容状态
4. 场馆/环境
5. 赔率观察
6. 当前缺口
7. 结论：仅观察，不推荐

## 禁止事项

- 禁止调用 live API。
- 禁止生成预测首发或任何 11 人名单。
- 禁止生成投注建议。
- 禁止生成盘口变化结论。
- 禁止生成资金流结论。
- 禁止修改 V4 official。
