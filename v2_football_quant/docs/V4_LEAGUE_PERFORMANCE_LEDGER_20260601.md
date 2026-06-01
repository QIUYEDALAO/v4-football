# V4 League Performance Ledger

## Purpose

The V4 league performance ledger is a long-term observation library for official
A/B recommendations. It supports dashboard risk tags and future daily, weekly,
and monthly reporting. It is not a strategy input.

## Data Boundary

- Include only official A/B records.
- Exclude C, SKIP, shadow-only, and dryrun-only records.
- Merge the locked `20260531` official A/B validation review with the historical
  official A/B ledger.
- Deduplicate by `fixture_id + date + grade`.
- Keep pending, postponed, void, abandoned, and result-missing records visible,
  but never count them in the hit-rate denominator or as misses.
- A locked official A/B review remains eligible even when its source group is
  `OUTSIDE_57`. The builder does not read an outside57-only source.

## Dashboard-Only Tags

`trust_tag` is a dashboard warning label. It must not change an official grade,
automatically blacklist a league, or automatically exclude a candidate.

| Tag | Meaning |
| --- | --- |
| `KEEP` | At least 20 validated samples with hit rate at least 60%. |
| `WATCH` | At least 20 validated samples with hit rate from 55% to below 60%. |
| `LOW_TRUST_ALERT` | At least 20 validated samples with hit rate below 55%. Observe risk; do not automatically exclude. |
| `LOW_SAMPLE_ONLY` | Five to nine validated samples. Sample is insufficient. |
| `DO_NOT_CONCLUDE` | Fewer than five validated samples. Do not conclude. |
| `PENDING_ONLY` | Pending records exist but no validated denominator exists. |
| `DATA_GAP` | Required league data is missing. |

No single-day result may trigger a rule change. Any future strategy-layer use
requires a separate BOSS review and approval.

## 20260531 Locked Baseline

| League | Result | Sample Note |
| --- | --- | --- |
| 冰岛超 | 4/4 = 100.0% | VERY_LOW_SAMPLE |
| 挪甲 | 4/4 = 100.0% | VERY_LOW_SAMPLE |
| 乌拉甲 | 2/2 = 100.0% | SINGLE_OR_TINY_SAMPLE |
| 越南联 | 3/4 = 75.0% | SINGLE_OR_TINY_SAMPLE |
| 巴西甲 | 3/5 = 60.0% | VERY_LOW_SAMPLE |
| 丹麦甲升 | 1/2 = 50.0% | SINGLE_OR_TINY_SAMPLE |
| 西乙 | 1/2 = 50.0% | SINGLE_OR_TINY_SAMPLE |
| 智利甲 | 1/3 = 33.3% | SINGLE_OR_TINY_SAMPLE |
| 中超 | 0/1 | SINGLE_OR_TINY_SAMPLE |
| 瑞典甲 | 0/1 | SINGLE_OR_TINY_SAMPLE |
| 立陶甲 | 0/1 | SINGLE_OR_TINY_SAMPLE |
| 芬超 | 0/1 | SINGLE_OR_TINY_SAMPLE |
| 瑞典超 | 1/1 | SINGLE_OR_TINY_SAMPLE |
| 厄瓜甲 | 1/1 | SINGLE_OR_TINY_SAMPLE |
| 捷克甲 | 1/1 | SINGLE_OR_TINY_SAMPLE |
| 爱沙甲 | 1/1 | SINGLE_OR_TINY_SAMPLE |
| 秘鲁甲春 | 1/1 | SINGLE_OR_TINY_SAMPLE |
| 阿尔巴超 | 1/1 | SINGLE_OR_TINY_SAMPLE |
| 阿根廷杯 | 0 validated / 1 postponed pending | PENDING_ONLY |

The `20260531` breakdown is a reproducibility baseline, not a league ranking.
智利甲 `1/3` and 中超 `0/1` are too small to justify a negative conclusion.
冰岛超 and 挪甲 `4/4` are also too small to justify relaxed rules.

## Outputs

- `data/runtime/validation/v4_league_performance_ledger_latest.json`
- `data/runtime/validation/v4_league_performance_ledger_latest.csv`

These runtime outputs are generated for validation and must not be committed.
