# V4 Football-Data Price-Aware Replay Core

Date: 2026-06-07

## Purpose

This pack builds an offline price-aware replay core from the processed
Football-Data dataset. It is for research only and is not connected to V4
production execution.

## Input

- `processed/v4_football_data_replay_dataset.csv`
- 15448 rows
- 9 leagues
- 5 complete seasons from 2020/21 through 2024/25
- 2025/26 remains excluded as current partial data

## Markets

The replay core creates one ledger with these market groups:

- `FT_OVER25`
- `1X2`
- `DOUBLE_CHANCE_PROXY`
- `ASIAN_HANDICAP`

## Settlement

`FT_OVER25` uses final total goals and `odds_over25_close`.

`1X2` settles home, draw, and away selections against `full_time_result` and
uses closing 1X2 prices.

`DOUBLE_CHANCE_PROXY` settles 1X, X2, and 12 hit rate from full-time result. It
does not have real Double Chance prices in this dataset, so ROI is not computed.

`ASIAN_HANDICAP` uses `asian_handicap_line` and closing AH prices. Quarter lines
are split into two half-stake settlements. Any unparseable AH line is marked
`AH_SETTLEMENT_UNCERTAIN` and excluded from ROI.

## Output

- `processed/v4_price_aware_replay_core_ledger.csv`
- `processed/v4_price_aware_replay_core_summary.json`

Metrics include:

- sample count
- settled count
- hit count
- hit rate
- average close odds
- flat 1u ROI proxy
- max fail streak
- max drawdown proxy
- price missing count
- settlement uncertain count

## Safety

This pack does not call api-football, does not execute a V4 scan, does not write
pending state, does not send QQ, does not change cron or launchd, and does not
modify official grades or thresholds.

## Validation

Run:

```bash
python3 v4-football/data/manual_sources/v4_football_data_csv/build_v4_price_aware_replay_core.py
python3 v4-football/data/manual_sources/v4_football_data_csv/check_v4_price_aware_replay_core.py
python3 v4-football/data/manual_sources/v4_football_data_csv/check_v4_football_data_replay_dataset.py
python3 v4-football/data/manual_sources/v4_football_data_csv/check_v4_football_data_csv_audit.py
python3 v2_football_quant/tools/check_v4_production_default_rules_guard.py
python3 v2_football_quant/tools/check_working_tree_dirty_hygiene.py
```
