# Claude Code Systematic Review WARN Fix — Issue List 20260520

**Phase:** CLAUDE-CODE-SYSTEMATIC-REVIEW-WARN-FIX-20260520
**Based on:** CLAUDE-CODE-SYSTEMATIC-CODE-REVIEW-20260520

| # | Grade | File | Title | Status |
|:--|:---|:---|:---|:---|
| P1-001 | P1 | `engine/v4_scan_and_brief.py` | Inverted push semantics: --push always default vs --no-push convention | pending |
| P1-002 | P1 | `engine/v4_scan_and_brief.py` | Parameter name mismatch: --date vs --scan-date | pending |
| P2-001 | P2 | `engine/v4_scan_and_brief.py` | Missing --scan-date/--no-push/--no-d13/--no-v33/--no-hourly/--preflight args | pending |
| P2-002 | P2 | `tools/run_v4_window_scan_capture_readonly.py` | Wrapper passes --date not --scan-date to engine | pending |
| P2-003 | P2 | `tools/check_v4_next_scan_window_capture.py` | Auto-runner fallback triggers production scan as checker side-effect | pending |
| P2-004 | P2 | `tools/check_v4_next_scan_window_capture.py` | Log content window check only reads first 500 chars | pending |
| P2-005 | P2 | `tools/check_intel_dashboard_user_visible_routes.py` | C value regex r'C[:\s]*(\d+)' matches C1/C2/C3/C4 labels | pending |
| P2-006 | P2 | `tools/check_ops_daily_operation.py` | V4 review file schema mismatch: nested official_counts causes KeyError | pending |
| P2-007 | P2 | `tools/check_intel_dashboard_user_visible_routes.py` | Accepts --no-* flags but ignores them silently | pending |

**Summary:** 2 P1 + 7 P2 = 9 items, 0 resolved.
