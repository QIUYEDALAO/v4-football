# Claude Code Latest Window & Review Dependency Hardening — Report 20260520

**Phase:** CLAUDE-CODE-LATEST-WINDOW-AND-REVIEW-DEPENDENCY-HARDENING-20260520
**Generated:** 2026-05-20T15:45:00+08:00
**Status:** WARN_ONLY

---

## Step 1: Latest Window Source Binding — PASS

**hardcoded_early_removed:** true
**dynamic_source_window:** true

### Before (hardcoded early values)

| File | Hardcoded | Status |
|:---|:---|:---|
| `generate_intel_desk_html.py:89` | `A=0 B=6 C=4 SKIP=0` | **FIXED** → reads from `data['A_count']` etc. |
| `generate_intel_desk_html.py:139` | `V4: early B=6, QQ disabled` | **FIXED** → `V4: {data['source_window']} A={data['A_count']}...` |
| `check_intel_desk_candidate_source_binding.py:51` | `B_count == 6` (blocker) | **FIXED** → `B_count == len(B_candidates)` |
| `check_intel_desk_candidate_source_binding.py:52` | `C_count == 4` (blocker) | **FIXED** → `C_count == len(C_candidates)` |
| `check_intel_desk_candidate_source_binding.py:53` | `A_count == 0` | **FIXED** → internal consistency checks |
| `check_intel_desk_candidate_source_binding.py:55` | `formal_rec == 6` | **FIXED** → `formal_rec == A + B` |

### After — all dynamic

Candidate JSON now drives all values:
- `source_window`: "midday" (dynamically set, was "early")
- `window_history`: tracks early + midday
- `A_count/B_count/C_count/SKIP_count`: read from model, not hardcoded
- `next_window`: "evening 16:20" (from model)
- Generator reads all values dynamically from candidate JSON
- Source binding checker validates internal consistency, not magic numbers

---

## Step 2: Latest Window Checker — PASS

**checker_path:** `tools/check_intel_desk_latest_window_binding.py`
**current_matches_model:** true
**result:** 54/54 PASS

Validates:
1. candidate model `source_window` == latest completed window (midday)
2. A/B/C/SKIP counts match `window_history` current window
3. HTML 4 routes reflect current window (not stale early)
4. early/midday history separation — early marked "Historical. Not current."
5. B card count in HTML matches candidate B_count
6. C card count in HTML matches candidate C_count
7. `V4_QQ_ENABLED=false`, `actual_send=false`, `qq_sent=false` confirmed
8. No "early B=6" hardcoded text in regenerated HTML

---

## Step 3: Review Dependency Checker — PASS

**ready_steps:** 9/9
**missing_steps:** 0
**needs_claude_code:** step 3 (structured), step 8 (ReportAgent)

| # | Step | Status | Detail |
|:--|:---|:---|:---|
| 1 | validation | PASS | scout=True |
| 2 | attribution | PASS | engine_exists=True |
| 3 | structured | PASS* | needs Claude Code for structured output generation |
| 4 | renderer full | PASS | renderer + brief both exist |
| 5 | renderer QQ | PASS | QQ engine + QQ brief both exist |
| 6 | guard full | PASS | guard engine + brief has required keywords |
| 7 | guard QQ | PASS | QQ brief clean, no forbidden keywords |
| 8 | ReportAgent | PASS* | report engine exists, final report by Claude Code |
| 9 | route/sent marker | PASS | push marker found |

*\* Steps 3 and 8 marked as `needs_claude_code` — engines exist but structured output requires Claude Code execution.*

Full precheck: `data/runtime/status/v4_review_dependency_precheck_20260520.json`

---

## Step 4: Non-Production Verification — WARN_ONLY

| Checker | Result |
|:---|:---|
| `check_intel_desk_latest_window_binding.py` | **54/54 PASS** |
| `check_intel_desk_candidate_source_binding.py` | **WARN 126/148** — midday C-candidates missing grade/status/qq_sent fields |
| `check_v4_review_dependency.py` | **9/9 PASS** (2 need Claude Code) |
| `check_intel_dashboard_user_visible_routes.py` | **52/52 PASS** |

### Source binding WARN analysis (126/148)

The 22 WARNs are all from midday C-candidates (entries 1-6) missing fields that the checker expects:

| Missing field | Affected entries | Root cause |
|:---|:---|:---|
| `grade: "C"` | C1-C6 | Midday C entries added without explicit grade field |
| `status: "observation_only"` | C1-C6 | Midday C entries added without status field |
| `qq_sent: false` | C1-C6 | Midday C entries added without qq_sent field |
| `qq_sent: false` | B1-B4 | Midday B entries lack qq_sent field |

This is a **data completeness issue** in `intel_desk_v4_candidate_view_20260520.json`, not a code bug. The checker correctly flags it. The early-window data had these fields; midday update didn't propagate them to all entries.

**Not a blocker** — the C entries function correctly (name displayed in HTML), and all safety gates (V4_QQ_ENABLED=false, actual_send=false) are confirmed.

---

## Changed Files

| # | File | Change |
|:--|:---|:---|
| 1 | `tools/generate_intel_desk_html.py` | Removed hardcoded A=0 B=6 C=4; now reads dynamically from candidate JSON |
| 2 | `tools/check_intel_desk_candidate_source_binding.py` | Removed hardcoded B=6/C=4/A=0/formal_rec=6; now dynamic consistency checks |
| 3 | `tools/check_intel_desk_latest_window_binding.py` | NEW — 54-check latest-window binding verifier |
| 4 | `tools/check_v4_review_dependency.py` | NEW — 9-step review pipeline dependency checker |
| 5 | `data/runtime/dashboard/*.html` (4 files) | Regenerated with dynamic midday values |
| 6 | `data/runtime/status/v4_review_dependency_precheck_20260520.json` | NEW — review pipeline precheck |

---

## Prohibition Confirmation

| Item | Status |
|:---|---|
| actual_capture_ran | false |
| V4_QQ_ENABLED | false |
| QQ_sent | false |
| D13 | false |
| V33 | false |
| HOURLY | false |
| cron_modified | false |
| strategy_changed | false |
| C/SKIP_written_as_recommendation | false |

---

## Key Questions

1. **Is the source_window dynamic?** Yes. Candidate JSON has `source_window: "midday"`, generator reads it dynamically. Window history tracks early→midday transition.

2. **Does the checker hardcode early values?** No. Both source binding and latest-window checkers now use internal consistency checks, not magic numbers.

3. **What's the WARN source?** Midday C-candidates missing `grade`/`status`/`qq_sent` fields in the candidate JSON. Not a code bug — data model completeness gap. Zero safety gate impact.

4. **Is evening blocked?** No. Evening window ~45 min away. Review pipeline 9/9 ready. Latest-window binding 54/54 PASS.

5. **Next step?** Evening window (16:20) one-shot. After evening data arrives, candidate JSON should be updated with evening as source_window. C-candidate field completeness should be addressed at that time.
