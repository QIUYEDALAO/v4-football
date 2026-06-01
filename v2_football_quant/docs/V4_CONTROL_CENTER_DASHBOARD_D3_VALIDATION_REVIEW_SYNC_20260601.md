# V4 Control Center Dashboard D3 Validation Review Sync

Date: 2026-06-01

## Scope

This pass syncs the dashboard with the locked 20260531 official A/B validation review.

Allowed files touched:
- `tools/build_v4_control_center_model.py`
- `data/runtime/dashboard/v4_control_center.html`
- `tools/check_v4_control_center_validation_sync.py`
- `docs/V4_CONTROL_CENTER_DASHBOARD_D3_VALIDATION_REVIEW_SYNC_20260601.md`

The earlier D2 league-list UX fix in `v4_control_center.html` is preserved: the candidate list shows only the league name, while the sample note remains available in detail views.

## Locked Sources

- `data/runtime/validation/v4_official_ab_validation_review_20260531.json`
- `data/daily_reports/V4_20260531_OFFICIAL_AB_VALIDATION_REVIEW.md`
- `data/runtime/validation/v4_league_performance_ledger_latest.json` when present

The dashboard reads these sources only. It does not recompute validation.

## Dashboard Additions

- Top KPI now prefers the locked 20260531 validation review when available.
- Overview validation cards show locked A/B values even on a quiet 20260601 candidate day.
- Validation tab now shows:
  - official A/B/C/SKIP = 1/36/0/55
  - AB 25/36 = 69.4%
  - A 1/1 = 100.0%
  - B 24/35 = 68.6%
  - pending 1, postponed excluded from denominator
  - rescue 6/9 = 66.7%
  - non-rescue 19/27 = 70.4%
  - system anomalies 0
  - rule change recommended NO
- Review tab now shows a 20260531 league validation snapshot:
  - 冰岛超 4/4 = 100.0%
  - 挪甲 4/4 = 100.0%
  - 巴西甲 3/5 = 60.0%
  - 智利甲 1/3 = 33.3%
  - 阿根廷杯 pending-only

## Safety

- official grade logic unchanged.
- 73.5 threshold unchanged.
- DEFAULT_RULES unchanged.
- A/B thresholds unchanged.
- QQ not pushed.
- pending not written.
- validation not recomputed.
- live bet records not written.
- cron not modified.
- C/SKIP/shadow-only remain outside official cards.

## Checker

Added `tools/check_v4_control_center_validation_sync.py`.

The checker validates the locked model values, required dashboard tokens, league snapshot, and read-only safety flags.
