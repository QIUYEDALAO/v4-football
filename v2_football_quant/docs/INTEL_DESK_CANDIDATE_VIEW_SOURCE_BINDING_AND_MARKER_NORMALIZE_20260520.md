# Intel Desk Candidate View Source Binding & Marker Normalize — Report 20260520

**Phase:** INTEL-DESK-CANDIDATE-VIEW-SOURCE-BINDING-AND-MARKER-NORMALIZE-20260520
**Generated:** 2026-05-20T14:45:00+08:00
**Status:** ALL_PASS

---

## Issue Resolution

| # | Issue | Status |
|:--|:---|:---|
| 1 | 标准 status path 缺失 | PASS — already exists from MARKER-NORMALIZE phase |
| 2 | legacy status path 存在 | PASS |
| 3 | B/C 卡片硬编码在 HTML 而非从 JSON 生成 | **FIXED** — generation script created |
| 4 | candidate view JSON 存在 | PASS |
| 5 | dashboard 生成逻辑未绑定 candidate model | **FIXED** — source_hash embedded in HTML |
| 6 | checker 只检查 HTML 未检查 source binding | **FIXED** — source binding checker created |
| 7 | midday/evening 更新后可能 stale | WARN — HTML is static; regeneration needed after new window data |
| 8 | V4_QQ_ENABLED=false | PASS |
| 9 | actual_send/qq_sent=false | PASS |
| 10 | D13/V33/HOURLY=false | PASS |

**8 PASS, 2 FIXED, 0 FAIL, 0 BLOCKER**

---

## Changes Made

### Step 4: Candidate Model Verified
- `data/runtime/status/intel_desk_v4_candidate_view_20260520.json` — 6 B candidates, 4 C observations, all fields complete

### Step 5: Dashboard Generation Script
- `tools/generate_intel_desk_html.py` — reads candidate JSON, generates all 4 HTML pages
- Every B/C card in HTML comes directly from JSON entries
- `source_hash` (MD5 first 12 chars) embedded in header and footer of each page
- Generation marker written to `data/runtime/status/intel_desk_html_generation_marker_20260520.json`
- source_hash: `1b8739268aca`

### Step 6: Report Paths Updated
- Added `candidate_model_path` to status marker and report

### Step 7: Source Binding Checker
- `tools/check_intel_desk_candidate_source_binding.py` — 155 checks
- Validates: JSON structure, HTML-to-JSON field matching, source_hash presence, no UNKNOWN placeholders, per-route conflict count=0

---

## Verification Results

| Checker | Result |
|:---|:---|
| `check_intel_desk_candidate_source_binding.py` | PASS 155/155 |
| `check_intel_desk_candidate_view.py` | PASS 68/68 |
| `check_intel_dashboard_user_visible_routes.py` | PASS 52/52 |
| `check_dashboard_route_stale_regression.py` | PASS 42/42 |

**Total: 317/317 PASS**

---

## Source Binding Architecture

```
intel_desk_v4_candidate_view_20260520.json  (source of truth)
    │
    ├── MD5 hash → source_hash = 1b8739268aca
    │
    ├── generate_intel_desk_html.py  (reads JSON, generates HTML)
    │       │
    │       ├── index.html          (source_hash embedded)
    │       ├── intel_desk.html     (source_hash embedded)
    │       ├── v2_today.html       (source_hash embedded)
    │       └── ops_heartbeat.html  (source_hash embedded)
    │
    └── check_intel_desk_candidate_source_binding.py  (cross-references HTML ↔ JSON)
```

## Key Questions Answered

1. 标准 status marker 是否补齐？ **Yes** — `intel_desk_candidate_view_and_stale_cleanup_20260520.json`
2. legacy status 是否保留兼容？ **Yes** — `intel_desk_cleanup_final_20260520.json`
3. B=6 卡片是否绑定 candidate JSON？ **Yes** — all 6 home/away names cross-referenced, source_hash embedded
4. C=4 观察项是否绑定 candidate JSON？ **Yes** — all 4 entry names cross-referenced
5. HTML 是否仍可能 stale？ **WARN** — static HTML needs regeneration after new window data; generator script available
6. checker 是否 PASS？ **Yes** — 317/317 across 4 checkers
7. 是否运行了 midday capture？ **No**
8. 是否触碰 QQ/D13/V33/HOURLY/cron/策略？ **No**
9. 下一任务？ Monitor midday window, re-generate HTML if new candidate data arrives

## Prohibition Confirmation

| Item | Status |
|:---|---|
| midday_capture_ran | false |
| V4_QQ_ENABLED | false |
| QQ_sent | false |
| D13 | false |
| V33 | false |
| HOURLY | false |
| cron_modified | false |
| strategy_changed | false |
