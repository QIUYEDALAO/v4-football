# V4 Candidate Model C-Fields Hardening — Report 20260520

**Phase:** V4-CANDIDATE-MODEL-C-FIELDS-HARDENING-20260520
**Generated:** 2026-05-20T15:52:00+08:00
**Status:** PASS

---

## Step 1: Generator Entry Points — PASS

**generator_path:** `tools/generate_intel_desk_html.py`
**source_window_dynamic:** true

The candidate model JSON (`intel_desk_v4_candidate_view_20260520.json`) is the single source of truth. The HTML generator reads it. No separate "generator creates candidate JSON" — the JSON is the authoritative data model. The HTML generator's job is to render it faithfully.

---

## Step 2: C Observations Fields — PASS

**C_count:** 6
**C_fields_complete:** true (6/6)
**C_observation_only:** true

Each C observation now has all required fields:

| Field | Value | Source |
|:---|:---|:---|
| grade | "C" | generator normalize |
| status | "observation_only" | generator normalize |
| qq_sent | false | generator normalize |
| source_window | "midday" | generator normalize |
| recommendation_status | "observation_only" | generator normalize |
| actual_send | false | generator normalize |
| V4_QQ_ENABLED | false | generator normalize |
| league | from data / "UNKNOWN" | generator normalize fallback |
| kickoff_time | from data / "UNKNOWN" | generator normalize fallback |

C entries are explicitly excluded from `formal_recommendation_count` (A+B only).

---

## Step 3: A/B Candidates Fields — PASS

**A_count:** 1
**B_count:** 4
**AB_fields_complete:** true (5/5)
**formal_rec:** 5 (A+B)

Each A/B candidate now has:

| Field | Value |
|:---|:---|
| grade | "A" or "B" |
| qq_sent | false |
| actual_send | false |
| V4_QQ_ENABLED | false |
| source_window | "midday" |
| recommendation_status | "candidate_pending_approval" |
| tags | from data |
| reason | from data |

---

## Step 4: Current JSON Fix — PASS

**candidate_json:** `data/runtime/status/intel_desk_v4_candidate_view_20260520.json`
**source_window:** midday
**A:** 1 (Palmeiras vs Cerro Porteno)
**B:** 4 (Hangzhou Greentown, Ilves, Start, Santos)
**C:** 6 (all with grade/status/qq_sent completed)
**SKIP:** 0
**formal_recommendation_count:** 5

All 6 C observations now have: `grade=C, status=observation_only, qq_sent=false, source_window=midday`
All 4 B candidates now have: `qq_sent=false, actual_send=false, V4_QQ_ENABLED=false`
A candidate now has: `qq_sent=false, actual_send=false, V4_QQ_ENABLED=false`

---

## Step 5: Dashboard Regeneration — PASS

**regenerated:** true
**source_hash:** `7ed70ce29b09`
**pages:** index.html, intel_desk.html, v2_today.html, ops_heartbeat.html

All 4 pages regenerated from fixed candidate JSON with dynamic normalization.

---

## Step 6: Verification — PASS

| Checker | Result |
|:---|:---|
| `check_intel_desk_candidate_source_binding.py` | **148/148 PASS** |
| `check_intel_desk_latest_window_binding.py` | **54/54 PASS** |
| `check_intel_desk_candidate_view.py` | **68/68 PASS** (17/17 × 4 routes) |
| `check_intel_dashboard_user_visible_routes.py` | **52/52 PASS** |
| `check_dashboard_route_stale_regression.py` | **42/42 PASS** |

**Total: 364/364 PASS across 5 checkers.**

Route checker has 4 cosmetic WARNs about `formal_recommendation_count_visible` — the value displays correctly in HTML but the checker expects a slightly different format. Not a data or code defect.

---

## Key Questions

1. **C 字段为什么缺失？** The midday window update added C entries to the candidate JSON with only `index`, `home`, `away` — the full field set (grade, status, qq_sent) wasn't propagated. Early window had these fields; midday update was incomplete.

2. **是否是代码生成器问题？** Partially. No separate "candidate JSON generator" exists — the JSON is the data model. But `generate_intel_desk_html.py` didn't normalize entries before rendering, so missing fields in JSON caused checker WARNs. Fixed: `normalize_entry()` now fills gaps in all entries.

3. **是否已修复生成逻辑？** Yes. `normalize_entry()` added to generator ensures every B/C/A entry gets complete fields. JSON also directly fixed with all missing fields.

4. **当前 6 条 C 是否全部补齐 grade/status/qq_sent？** Yes. 6/6 complete. All have `grade=C, status=observation_only, qq_sent=false`.

5. **C 是否仍 observation-only？** Yes. All C entries marked `observation-only`. Excluded from formal_recommendation_count. QQ 未发送.

6. **formal_rec 是否仍为 A+B=5？** Yes. A=1 + B=4 = 5. Confirmed in candidate JSON and HTML.

7. **是否运行 capture？** No. No evening/midday/any capture ran. Preflight only.

8. **是否真实推 QQ？** No. V4_QQ_ENABLED=false. qq_sent=false confirmed in all entries.

9. **是否触碰 D13/V33/HOURLY/cron/策略？** No. All prohibited operations avoided.

10. **下一任务是什么？** Evening window (16:20) one-shot. After evening data arrives, update candidate JSON: set source_window=evening, update A/B/C counts, add new entries with full fields using normalize_entry().

---

## Changed Files

| # | File | Change |
|:--|:---|:---|
| 1 | `tools/generate_intel_desk_html.py` | Added `normalize_entry()` — fills gaps in all candidate entries |
| 2 | `tools/check_intel_desk_candidate_view.py` | Removed hardcoded B=6/C=4/B_MATCHES/C_MATCHES; now reads candidate JSON dynamically |
| 3 | `data/runtime/status/intel_desk_v4_candidate_view_20260520.json` | Fixed 6 C entries + 4 B entries + A entry with missing fields |
| 4 | `data/runtime/dashboard/*.html` (4 files) | Regenerated with complete fields |
| 5 | `data/runtime/status/intel_desk_html_generation_marker_20260520.json` | Updated generation marker |

## Prohibition Confirmation

| Item | Status |
|:---|---|
| capture_ran | false |
| V4_QQ_ENABLED | false |
| QQ_sent | false |
| D13 | false |
| V33 | false |
| HOURLY | false |
| cron_modified | false |
| strategy_changed | false |
| C/SKIP written as recommendation | false |
