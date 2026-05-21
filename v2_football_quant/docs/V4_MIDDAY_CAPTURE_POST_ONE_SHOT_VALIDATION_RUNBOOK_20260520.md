# V4 Midday Capture Post-One-Shot Validation Runbook — 2026-05-20

## One-Shot Job

- **Job ID:** V4_MIDDAY_ONE_SHOT_20260520
- **Scheduled:** 2026-05-20 14:05 CST
- **Type:** one_shot (not_cron=true)
- **Self-destruct:** autodelete_after_run=true
- **CRON modified:** false — no long-term cron configured for midday window
- **Scheduler:** openclaw_cron_one_shot

## Command (executed by one-shot job at 14:05 CST)

```
cd /Users/liudehua/.openclaw/workspace/v2_football_quant && python3 tools/run_v4_window_scan_capture_readonly.py --window midday --scan-date 20260520 --no-push --no-d13 --no-v33 --no-hourly
```

## Key Rules

1. **14:05 executed by one-shot job** — no manual trigger required, no long-term cron needed.
2. **No long-term cron** — this is a one-shot job; it self-destructs after execution.
3. **V4 QQ NOT enabled** — V4_QQ_ENABLED=false; BOSS approval required for any QQ activation.
4. **No early B=6 push** — B=6 from early window is recorded as future_ab_trigger only; no QQ push.
5. **After 14:05, verify window-specific evidence** — check `data/runtime/status/v4_scan_midday_window_capture_after_due_20260520.json` for `production_evidence=true` and `synthetic_evidence=false`.
6. **A/B>0 → future_ab_trigger only** — any A or B grades from midday window are recorded; no automatic QQ.
7. **QQ enabled requires separate BOSS approval** — the V4_QQ_ENABLE decision pack documents all preconditions.
8. **No D13, no V33, no HOURLY** — all prohibited.

## Post-Capture Validation Commands

After 14:05 CST, verify:

```bash
# Check window-specific capture evidence
python3 tools/check_v4_next_scan_window_capture.py --window midday --scan-date 20260520 --no-push --no-d13 --no-v33 --no-hourly

# Check one-shot job completion
python3 tools/check_v4_midday_one_shot_job.py

# Run safety verification suite
python3 tools/check_v4_wrapper_regression.py
python3 tools/check_v4_qq_decision_pack_consistency.py
python3 tools/check_dashboard_route_stale_regression.py
python3 tools/check_ops_daily_operation.py --date 20260520
```

## Guardrails

- `actual_send=false`
- `qq_sent=false`
- `route=shadow_only`
- `V4_QQ_ENABLED=false`
- `boss_approval_required=true`
- `no_push=true`, `no_d13=true`, `no_v33=true`, `no_hourly=true`

## Related Documents

- [V4 QQ Enable Decision Pack](./V4_QQ_ENABLE_DECISION_PACK_20260520.md)
- [Claude Code Safe Hardening Pack](./CLAUDE_CODE_SAFE_HARDENING_PACK_20260520.md)
- [Early Window Capture Runbook](./V4_EARLY_WINDOW_CAPTURE_RUNBOOK_20260520.md)
