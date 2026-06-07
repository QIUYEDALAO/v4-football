# V4 Football-Data CSV Replay Dataset

Date: 2026-06-07

## Purpose

This pack converts the committed football-data.co.uk CSV files into one
price-aware replay dataset for offline V4 research.

It is not a production scan input and does not change official V4 grading,
pending writes, QQ notification, cron, launchd, or live-bet state.

## Dataset Scope

Included in the main replay dataset:

- 9 leagues: E0, SP1, D1, I1, F1, P1, N1, B1, T1
- 5 complete seasons: 2020/21, 2021/22, 2022/23, 2023/24, 2024/25
- Source: football-data.co.uk

Excluded from the main replay dataset:

- 2025/26

The 2025/26 CSV files are treated as `CURRENT_PARTIAL` and are counted only in
the excluded summary. They must not be used by the main replay backtest.

## Unified Schema

The processed dataset normalizes:

- FT and HT score/result fields
- basic match statistics
- Bet365 1X2 opening and closing prices
- Bet365 Over/Under 2.5 opening and closing prices
- Bet365 Asian Handicap line and opening/closing prices
- row-level data quality flags

Output files:

- `processed/v4_football_data_replay_dataset.csv`
- `processed/v4_football_data_replay_summary.json`

## Safety Policy

This dataset can support future offline replay for:

- full-time over research
- Asian handicap research
- 1X2 and Double Chance research

It must not create any live strategy, official grade, pending candidate, QQ
message, cron job, launchd job, or production change.

The dataset is price-aware, but it still needs separate replay logic before any
research conclusion can be discussed.

## Validation

Run:

```bash
python3 v4-football/data/manual_sources/v4_football_data_csv/build_v4_football_data_replay_dataset.py
python3 v4-football/data/manual_sources/v4_football_data_csv/check_v4_football_data_replay_dataset.py
python3 v4-football/data/manual_sources/v4_football_data_csv/check_v4_football_data_csv_audit.py
python3 v2_football_quant/tools/check_v4_production_default_rules_guard.py
python3 v2_football_quant/tools/check_working_tree_dirty_hygiene.py
```
