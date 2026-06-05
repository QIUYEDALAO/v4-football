# V3_WC_2026_MATCHDAY_BRIEF_SIMULATION_PACK

本阶段新增赛前情报卡 dry-run 生成器。它只使用本地 104 schedule、Final26、venue stress 与 mock odds 数据，模拟一场小组赛的手机阅读版赛前 brief。

## 范围

- 不调用 live API。
- 不提交 runtime。
- 不生成首发。
- 不生成预测。
- 不生成资金流结论。
- 不影响 V4。

## 模拟时间点

- `T-24h`
- `T-6h`
- `T-90m`
- `T-30m`

## odds 字段

只展示：

- `first_seen_odds`
- `last_pre_kickoff_odds`
- `odds_observation_delta`

原生开盘/收盘缺失。mock odds 只用于模板演示，不生成盘口或资金流结论。

## 安全字段

- `observation_only=true`
- `no_starting_xi_generated=true`
- `no_prediction=true`
- `no_injury_judgment=true`
- `betting_recommendation=false`
- `affects_v4=false`
