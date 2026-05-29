# V4 Dashboard Candidate List Runtime Fix

**Date**: 2026-05-29
**Status**: V4_DASHBOARD_CANDIDATE_LIST_RUNTIME_FIX_PASS

## Root Cause

commit 8cf04ae modified `data/runtime/dashboard/index.html` but the 8766 service actually serves `data/runtime/dashboard/v4_control_center.html`. The `index.html` is not in the service's route table. All checkers reference `v4_control_center.html` as the primary dashboard page.

## Fix

1. Applied list layout changes to `v4_control_center.html` (the actual runtime file)
2. Replaced `renderCandidate()` card renderer with `renderListRow()` compact list renderer
3. Added `toggleBetPanel()` single-expand logic
4. Removed inline time-bin re-derivation; now uses model's `playbook_script` and `fh_goal_dist_*` fields directly
5. Simplified `matchName()` to use model's `home_cn`/`away_cn` display names
6. Replaced "57白名单"/"全量合规"/"正式候选" with neutral labels
7. Bet forms collapsed by default, expandable one at a time
