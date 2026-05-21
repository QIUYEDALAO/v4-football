# V4 Night Window Capture Runbook — 20260520

**Generated:** 2026-05-20 15:47 CST  
**Status:** RUNBOOK_READY (not executed)

---

## Night Window

| Field | Value |
|:------|:-------|
| window | night |
| scan_date | 20260520 |
| scheduled_time | 22:20 CST |
| status | PENDING |
| capture_ran | false |

## Command

```bash
python3 tools/run_v4_window_scan_capture_readonly.py --window night --scan-date 20260520 --no-push --no-d13 --no-v33 --no-hourly
```

## Guards

| Guard | Status |
|:------|:-------|
| no_push | true |
| no_d13 | true |
| no_v33 | true |
| no_hourly | true |
| V4_QQ_ENABLED | false |
| actual_send | false |
| qq_sent | false |

## One-Shot Template

If BOSS instructs or auto-advance rules allow after evening completes:

```
openclaw cron add --name V4_NIGHT_ONE_SHOT_20260520 --schedule "cron 20 22 * * *" --tz Asia/Shanghai --deleteAfterRun --payload '{"kind":"agentTurn","message":"cd /Users/liudehua/.openclaw/workspace/v2_football_quant && python3 tools/run_v4_window_scan_capture_readonly.py --window night --scan-date 20260520 --no-push --no-d13 --no-v33 --no-hourly"}'
```

## After Night

1. Verify evidence (log, status, scout, brief)
2. Update candidate model → CURRENT=night
3. Regenerate dashboard
4. Run V4 review (9-step)
5. Present final AB for BOSS QQ decision
