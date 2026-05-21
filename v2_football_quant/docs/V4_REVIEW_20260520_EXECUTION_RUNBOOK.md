# V4 Review 20260520 — Execution Runbook

**Generated:** 2026-05-20 16:41 CST  
**Status:** RUNBOOK_READY (not executed — must wait for night 22:20 completion)

---

## 9-Step Review Pipeline

Execute in order after night 22:20 window completes.

### Step 1-3: Pre-processing
```bash
python3 engine/v4_ht_result_validator.py
python3 engine/v4_result_attribution.py
python3 engine/v4_review_result_refresh.py
```

### Step 4-5: Render
```bash
python3 engine/v4_review_renderer.py --mode full
python3 engine/v4_review_renderer.py --mode qq
```

### Step 6-7: Guard
```bash
python3 engine/v4_review_guard.py --mode full
python3 engine/v4_review_guard.py --mode qq
```

### Step 8: ReportAgent
ClawOps calls ReportAgent to check QQ text formatting.

### Step 9: Route/Sent Marker
```bash
# Write v4_review_route_YYYYMMDD.json
# ClawOps final verification
# If all guard PASS, ClawOps systemEvent original push
# Write v4_review_push_YYYYMMDD.json
```

---

## Hard Rules

| Rule | Status |
|:-----|:-------|
| Missing any step → no QQ push | ✅ enforced |
| C=observation-only | ✅ |
| SKIP=not recommendation | ✅ |
| A/B=formal candidate | ✅ (A=1, B=4) |
| V4_QQ_ENABLED=false | ✅ |
| actual_send=false | ✅ |
| qq_sent=false | ✅ |
| BOSS approval required=true | ✅ |

## Current Data

| Field | Value |
|:------|:-------|
| Latest window | evening |
| A | 1 (Palmeiras, 自由杯) |
| B | 4 |
| C | 6 |
| SKIP | 0 |
| Formal recs | 5 |
