# Intel Desk Candidate View & Stale Cleanup — Final Report 20260520

**Phase:** INTEL-DESK-CANDIDATE-VIEW-AND-STALE-CLEANUP-20260520
**Generated:** 2026-05-20T12:00+08:00
**Status:** ALL PASS
**primary_status_path:** `data/runtime/status/intel_desk_candidate_view_and_stale_cleanup_20260520.json`
**legacy_status_path:** `data/runtime/status/intel_desk_cleanup_final_20260520.json`
**candidate_model_path:** `data/runtime/status/intel_desk_v4_candidate_view_20260520.json`

## Issue Resolution

| # | Issue | Status |
|:--|:------|:-------|
| 1 | B=6 只显示汇总数字，不显示具体比赛 | PASS |
| 2 | C=4 只显示汇总数字，不显示观察项明细 | PASS |
| 3 | CURRENT 区仍有 CODE_READY 作为主状态 | PASS |
| 4 | CURRENT 区仍有 PIPELINE=false / PROD_VERIFIED=false | PASS |
| 5 | CURRENT 区仍有 readonly_only 标签 | PASS |
| 6 | CURRENT 区仍有 no_formal_daily_pool | PASS |
| 7 | CURRENT 区仍有 cron_removed / crontool removed | PASS |
| 8 | footer 仍有 只读/不推QQ/不写state 旧文案 | PASS |
| 9 | V4 QQ approval 状态不够醒目 | PASS |
| 10 | next_window 不够结构化 | PASS |
| 11 | iPhone 阅读不够清楚（缺少卡片式布局） | PASS |

**Summary:** 11/11 PASS, 0 FAIL, 0 WARN, 0 BLOCKER

## Changes Made

### Dashboard HTML (4 files rewritten)
- `data/runtime/dashboard/index.html` — full rewrite with B candidate cards + C observation + clean CURRENT sections
- `data/runtime/dashboard/intel_desk.html` — synced from stale 0/0/3/2 to current 0/6/4/0 with B cards
- `data/runtime/dashboard/ops_heartbeat.html` — added B candidate cards + C observation + INTEL_DESK_CANDIDATE_VIEW PASS status
- `data/runtime/dashboard/v2_today.html` — synced with index.html

### New Tool
- `tools/check_intel_desk_candidate_view.py` — 17 checks × 4 routes = 68 total checks

### Tools Fixed (regression)
- `tools/check_dashboard_route_stale_regression.py` — fixed C value regex to not match C1/C2/C3/C4 labels as conflicting C counts

## Verification Results

### Candidate View Checker: 68/68 PASS
- Routes: index (17/17), intel_desk (17/17), ops_heartbeat (17/17), v2_today (17/17)
- All 17 checks passed on all 4 routes

### User Visible Routes Checker: 52/52 PASS
- No conflicts detected, all routes consistent

### Dashboard Stale Regression Checker: 42/42 PASS
- 0 dashboard conflicts across all 4 routes

## Key Design Decisions
- B candidate cards show: league, kickoff time, home vs away, market_type, HT score, Best score, tags
- Stale hardening tags (cron_removed, readonly_only, etc.) quarantined to 历史审计 section only
- All CURRENT sections use "CURRENT:" prefix to distinguish from historical "not_current=true" markers
- V4_QQ_ENABLED=false, actual_send=false, qq_sent=false clearly visible on all routes
- BOSS approval required prominently shown
- iPhone-friendly card layout with max-width:540px
