# V4 Single Daily 1200 Scan Policy

**Phase:** V4-SINGLE-DAILY-1200-SCAN-POLICY-20260523
**Generated:2026-05-23 19:10 CST**

## Fixed Rules

| Rule | Value |
|:-----|:------|
| active_scan_count | 1 |
| active_scan_time | 12:00 |
| active_scan_window | daily_1200 |
| early_active | false |
| midday_active | false |
| evening_active | false |
| night_active | false |
| one_shot_active | false |
| live_snapshot_allowed | true (only stats, no scout trigger) |
| v4_review_allowed | true (REPORT_ONLY, no scan trigger) |
| multi_window_allowed | false |

## Forbidden Windows

night, evening, midday (as window name), early, late
