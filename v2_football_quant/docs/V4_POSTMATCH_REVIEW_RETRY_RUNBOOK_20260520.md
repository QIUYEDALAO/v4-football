# V4 Postmatch Review Retry Runbook — 20260520

**Generated:** 2026-05-20 23:22 CST  
**Status:** READY — execute after 2026-05-21 09:30 CST

---

## Prerequisites

All 20260520 matches must have finished, including:
- Santos vs San Lorenzo (南美杯) — kickoff 06:00+1 BJ
- HT result data must be available from API

## Retry Order

Execute each step in sequence. Do NOT skip steps.

### Step 1-3: Pre-processing
```bash
cd /Users/liudehua/.openclaw/workspace/v2_football_quant

python3 engine/v4_ht_result_validator.py --date 20260520
python3 engine/v4_result_attribution.py --date 20260520
python3 engine/v4_review_result_refresh.py --date 20260520
```

### Step 4-5: Render
```bash
python3 engine/v4_review_renderer.py --date 20260520 --mode full
python3 engine/v4_review_renderer.py --date 20260520 --mode qq
```

### Step 6-7: Guard
```bash
python3 engine/v4_review_guard.py --date 20260520 --mode full
python3 engine/v4_review_guard.py --date 20260520 --mode qq
```

### Step 8: ReportAgent
ClawOps calls ReportAgent to check QQ text formatting.

### Step 9: Route/Sent Marker
ClawOps writes `v4_review_route_20260520.json` → final verification → systemEvent.

## Blocking Conditions

If any of the following are true, stop and do NOT proceed:
1. `v4_review_structured_20260520.json` does not exist
2. attribution returns all UNKNOWN (API still unavailable)
3. guard returns BLOCKER
4. ReportAgent returns FAIL
5. Any V4_QQ_ENABLED is true (must remain false)

## Hard Rules

| Rule | Value |
|:-----|:------|
| C=observation-only | enforced by guard |
| SKIP=not recommendation | enforced by guard |
| A/B=formal candidate | |
| route=shadow_only | |
| actual_send=false | |
| V4_QQ_ENABLED=false | |
| BOSS approval required=true | |
