# V4 Early Window Capture Runbook — 2026-05-20

## Command (at 07:20 CST)
```
python3 v2_football_quant/tools/check_v4_next_scan_window_capture.py --window early --scan-date 20260520 --no-push --no-d13 --no-v33 --no-hourly
```

## Fallback
```
python3 v2_football_quant/tools/check_ops_daily_operation.py --scan-date 20260520 --review-date 20260519 --no-push --no-d13 --no-v33 --no-hourly
```

## Rules
- actual_send=false, qq_sent=false
- V4 QQ NOT enabled
- A/B>0 → future_ab_trigger only, NO QQ
