# V3 AI Match Judge Lite - 2026-06-08

## Lite Card

- match: Denmark vs Ukraine
- mode: SIMULATION_ONLY
- ai_direction: Denmark -0.75
- confidence: MEDIUM-LOW
- final_decision: OBSERVE
- ledger_required: true

## Top Reasons

- AI主判断给出丹麦方向，但置信度未达到高档。
- 首发与赔率/盘口检查均通过固定guard。
- 友谊赛模式触发固定降级规则。
- 赛后模拟记录为2-1，对-0.75方向仅为半赢结算。

## Top Risks

- 友谊赛模式不可直接升级为执行判断。
- 轮换风险虽非HIGH，但仍保留观察折扣。
- 友谊赛样本不可外推，不能形成稳定结论。

## Guard

- lineup_check: PASS
- odds_handicap_check: PASS
- mode_check: DOWNGRADE_FRIENDLY
- ledger_check: REQUIRED
- overall: OBSERVE

## Ledger

- ledger_ref: `data/v3_worldcup/friendly_simulation/v3_friendly_simulation_ledger_20260608.json`
- score: 2-1
- settlement: HALF_WIN

## Lite Boundary

- simulation_only: true
- dashboard_required: false
- read_model_required: false
- pending_written: false
- qq_sent: false
- affects_v4: false
