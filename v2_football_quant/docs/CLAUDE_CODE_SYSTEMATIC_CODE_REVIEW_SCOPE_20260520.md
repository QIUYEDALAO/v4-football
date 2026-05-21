# Claude Code Systematic Code Review — Scope 20260520

**Phase:** CLAUDE-CODE-SYSTEMATIC-CODE-REVIEW-20260520
**Generated:** 2026-05-20T12:05:00+08:00

## Audit Scope

### Core Execution Files
| File | Lines | Role |
|:---|:---|:---|
| `engine/v4_scan_and_brief.py` | 243 | V4 supervisor — spawns worker, builds brief, push logic |
| `engine/v4_runner.py` | 718 | V4 main runner (not directly audited here) |
| `tools/run_v4_window_scan_capture_readonly.py` | 117 | Wrapper — before/after hash, binds evidence to real run |

### Checker Files
| File | Lines | Role |
|:---|:---|:---|
| `tools/check_ops_daily_operation.py` | 292 | OPS daily strong monitoring — V2/V4 markers, scan windows |
| `tools/check_v4_next_scan_window_capture.py` | 159 | Window-specific capture checker — requires window evidence |
| `tools/check_v4_wrapper_regression.py` | 172 | Validates wrapper supports all required flags |
| `tools/check_v4_midday_one_shot_job.py` | 144 | Validates one-shot job configuration |
| `tools/check_v4_qq_decision_pack_consistency.py` | 228 | Cross-verifies QQ decision markers |
| `tools/check_v33_residual_audit.py` | 204 | Classifies all V33 references |
| `tools/check_intel_desk_candidate_view.py` | ~200 | 17 checks × 4 dashboard routes |
| `tools/check_intel_dashboard_user_visible_routes.py` | 239 | HTTP/local dashboard content checker |
| `tools/check_dashboard_route_stale_regression.py` | 270 | Staleness and conflict detection |

## Audit Dimensions
1. Parameter contracts (--scan-date, --review-date, --ops-date, --window, --no-push, etc.)
2. Evidence authenticity (synthetic_evidence, production_evidence, window-specific)
3. Dashboard CURRENT/History partition correctness
4. Regex and text matching precision
5. One-shot / cron boundary safety
6. V33/D13/HOURLY safety gate integrity
7. Non-production verification coverage
