# V3/V4 Dashboard Validation Display Contract - 20260523

Phase: V3V4-DASHBOARD-VALIDATION-VISIBILITY-RECOVERY-20260523

## Always Visible

The dashboard must always render one `V3/V4 比赛验证` card, even when validation data has no settled samples.

The card must include a two-column grid:

- Left: `昨日验证`
- Right: `累计验证`

Each column must show exactly these active rows:

- A
- B
- A+B

## N/A and Reason Policy

If a metric has no settled source data, render the row as `A N/A`, `B N/A`, or `A+B N/A`.

The card must display an explicit reason line:

- API disabled / match_date attribution not ready
- sample insufficient
- waiting settlement

The dashboard must not hide the card because values are N/A.

## Audit Fold

The folded audit area may include:

- source_files
- latest_validation_date
- unknown_count
- api_enabled
- brief_used_for_hit_rate=false
- C_observation_deprecated=true
- last_7d_removed=true

## Forbidden

- C validation in active card
- last-7-day validation in active card
- fake 0% hit rate
- brief-derived hit rate
- V2 / V33
- capture / QQ push / cloud publish / cron
