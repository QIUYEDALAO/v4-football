# V4 Dashboard Candidate List Spacing Fix

**Date**: 2026-05-29
**Status**: V4_DASHBOARD_CANDIDATE_LIST_SPACING_FIX_PASS

## Root Cause

The candidate list area inherited fixed 440px height constraints from the old card layout:
- `.candidate-panel` was set to `height:var(--pane-h)` = 440px
- `.side-sticky` was also locked to 440px
- Mode-specific variables `--action-zone-h-two` and `--action-zone-h-four` were both 440px

With only 5 candidates (~200px of content), this created ~240px of dead whitespace.

Additionally, the candidate table had no `table-layout:fixed`, column widths were unconstrained, and the distribution column (`dist-col`) had `white-space:nowrap` with long text causing horizontal overflow.

## Fixes

1. Changed `.candidate-panel` from fixed 440px to `height:auto; min-height:unset; max-height:none`
2. Changed `.side-sticky` from fixed 440px to `height:auto`
3. Changed mode variables from 440px to `auto`
4. Added `table-layout:fixed` to `.candidate-table`
5. Added percentage-based column widths via inline `th` styles
6. Reduced font sizes slightly for tighter fit
7. Added `overflow:hidden; text-overflow:ellipsis` to `dist-col`
8. Updated mobile media query to handle narrower viewports

## Verification

- All 28 spacing checks PASS
- Data binding: 22/22 PASS
- playbook_script and true goal distribution preserved
- Bet forms still collapsed by default, expandable one at a time
