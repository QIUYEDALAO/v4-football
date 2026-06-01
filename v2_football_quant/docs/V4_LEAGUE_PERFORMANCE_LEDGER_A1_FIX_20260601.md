# V4 League Performance Ledger A1 Fix

Date: 2026-06-01

## Scope

This pass hardens the existing League Performance Ledger implementation. It does not rebuild the feature from scratch.

Allowed files touched:
- `tools/build_v4_league_performance_ledger.py`
- `tools/check_v4_league_performance_ledger.py`
- `tools/build_v4_control_center_model.py`
- `data/runtime/dashboard/v4_control_center.html`
- `docs/V4_LEAGUE_PERFORMANCE_LEDGER_A1_FIX_20260601.md`

## Fixes

### PENDING_ONLY Contract

For leagues with `validated_count = 0` and `pending_count > 0`:
- `sample_tag = PENDING_ONLY`
- `trust_tag = PENDING_ONLY`
- `hit_rate = 0.0`
- `miss_count = 0`
- `data_quality_status = PENDING_ONLY` or `OK`
- pending/postponed records are excluded from the denominator

Dashboard copy:
- `PENDING_ONLY`: 延期/未完赛，仅记录，不进分母
- `DO_NOT_CONCLUDE`: 样本不足，不下结论，仅观察
- `LOW_SAMPLE_ONLY`: 样本偏少，仅辅助参考
- `LOW_TRUST_ALERT`: 长期低命中预警，不自动排除
- `KEEP / WATCH / OBSERVE`: display-only tags; they do not change official grades

### Historical Source Resolver

The builder now resolves the historical ledger dynamically:
1. Prefer `data/runtime/validation/v4_ab_historical_ledger_latest.json`
2. Otherwise choose the latest `v4_ab_historical_ledger_*.json` by date/mtime
3. Exclude league performance output files
4. If no historical ledger exists, continue with the locked `20260531` validation review and mark `HISTORICAL_LEDGER_MISSING_WARN_ONLY`

The output includes:
- `source_ledger_resolved`
- `historical_ledger_status`

### Stable Trend Windows

`last_7d` and `last_30d` now anchor on the maximum date present in validated records, not wall-clock `datetime.now()`.

The output includes:
- `trend_anchor_date`

If no validated dated records exist, trend counts are `0` and rates are `0.0`.

## Locked Baseline

The `20260531` baseline remains reproducible:
- 冰岛超 4/4
- 挪甲 4/4
- 智利甲 1/3
- 巴西甲 3/5
- 阿根廷杯 0 validated / 1 pending-only

## Safety

This is a read-only aggregation/display hardening pass.

Not changed:
- V4 grading logic
- 73.5 threshold
- DEFAULT_RULES
- A/B thresholds
- QQ route
- pending route
- validation source-of-truth
- live bet records
- cron
- sent marker
- candidate_view / scout / brief artifacts
