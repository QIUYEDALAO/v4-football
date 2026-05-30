# V4 Dashboard Goal Distribution Display Fix — 2026-05-30

## Problem

V4 dashboard candidate list showed truncated goal time distribution.
The `dist-col` CSS had `white-space:nowrap;overflow:hidden;text-overflow:ellipsis`,
causing the third segment (31-45) to be cut off with "..." on narrow columns.

On mobile (≤760px), the distribution column was completely hidden (`display:none`).

## Fix

### CSS changes (`data/runtime/dashboard/v4_control_center.html`)
- Desktop `dist-col`: removed `overflow:hidden;text-overflow:ellipsis;white-space:nowrap`
  → replaced with `white-space:normal;word-break:keep-all`
- Mobile `dist-col`: removed `display:none`
  → replaced with `white-space:normal;word-break:keep-all`
- Mobile `playbook-col`: keep `display:none` (short text, low priority on mobile)
- Mobile table headers: league (3), playbook (5), dist (6) hidden — data cells still show

### Result
- All three segments (0-15, 16-30, 31-45) fully visible on desktop and mobile
- Text wraps to two lines if space is insufficient
- Candidate list layout, sorting, status, expand buttons remain intact
- NO_MARKET status preserved

## Files Changed

- `data/runtime/dashboard/v4_control_center.html` — CSS fix for dist-col
- `data/runtime/dashboard/index.html` — CSS fix for dist-col
- `tools/check_v4_dashboard_goal_distribution_display.py` — new checker

## Verification

- 0/5 A/B candidates have ellipsis truncation
- 5/5 A/B candidates show 0-15, 16-30, 31-45
- 5/5 A/B candidates use events_goal_counts
- No forbidden labels in HTML
- Sort, expand, bet-panel, NO_MARKET preserved
- DEFAULT_RULES unchanged (b04f3da9b770)
