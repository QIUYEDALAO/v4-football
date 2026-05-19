# V4 Report Sample Contract

Phase: V4-G
Date: 2026-05-19
Status: CONTRACT ONLY (no execution, no verified, no QQ)

## Daily Report Sample (Full)

```
report_type = "daily"
date = "2026-05-19"
A_count = 3
B_count = 5
C_count = 4
SKIP_count = 8
unknown_count = 1
api_disabled_count = 2
A_B_primary = { "A": { "hit": 2, "miss": 1 }, "B": { "hit": 3, "miss": 2 } }
C_observation = { "entries": 4, "note": "observation-only, not primary" }
SKIP_behavior = { "entries": 8, "note": "not recommendation" }
guard_summary = { "schema_guard": "PASS", "qq_guard": "PASS", "no_push": true }
qq_allowed = false
rule_change_allowed = false
```

## QQ Brief Sample (Mobile)

```
【V4 情报系统】
📌 昨日V4复盘 · 2026-05-19
Guard: PASS | No-Push: true

【正式推荐】
A：3｜B：5
A/B主推：8场（命中5/8 · 62.5%）

【C/SKIP汇总】
C级（观察）：4场
SKIP：8场
详细已入库。

【结论】
样本量充足。规则未调整。
⚠️ 赛后归因报告，不代表今日实盘推荐
```

## Weekly Report Sample

```
report_type = "weekly"
week = "2026-05-12 to 2026-05-18"
total_samples = 56
A_B_primary = { "A": 12, "B": 20, "hit": 18, "miss": 14 }
C_observation = 15
SKIP_behavior = 21
unknown_excluded = 5
api_disabled_excluded = 3
rolling_7d_ab_rate = "18/32 = 56.25%"
rule_change_allowed = false
```

## Monthly Report Sample

```
report_type = "monthly"
month = "2026-05"
rolling_30d_ab_rate = "72/120 = 60.0%"
monthly_ab_rate = "35/56 = 62.5%"
sample_size_note = "A+B >= 100: HIGH confidence"
rule_change_note = "Review only. Requires BOSS approval."
rule_change_recommendation_allowed = false
```

## Contract Enforcement

- These samples are CONTRACT ONLY
- No report execution in this phase
- No verified files written
- No QQ pushed
- No rule changes applied
