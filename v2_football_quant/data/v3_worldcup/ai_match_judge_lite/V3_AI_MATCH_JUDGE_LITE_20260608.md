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
- 友谊赛模式下轮换与临场信息不确定。
- 赛后模拟记录为2-1，对-0.75方向仅为半赢结算。

## Top Risks

- 首发确认需要临场检查。
- 赔率/盘口需要赛前复核。
- 友谊赛样本不可外推，不能形成稳定结论。

## Guard

- lineup_check: WAIT
- odds_handicap_check: WAIT
- mode_check: PASS
- ledger_check: PASS
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
