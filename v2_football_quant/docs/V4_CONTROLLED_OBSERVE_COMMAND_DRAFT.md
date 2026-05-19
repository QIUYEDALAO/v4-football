# V4 Controlled Observe Command Draft

Phase: V4-I / V4-I.2
Date: 2026-05-19
Status: REVIEW_ONLY_DRAFT — NOT EXECUTABLE

## Command Classification

| Field | Value |
|-------|-------|
| command_type | REVIEW_ONLY_DRAFT |
| command_must_not_execute | true |
| runner_defined | true |
| runner_exists | true (V4-I.1) |
| runner_execution_authorization_required | true |
| observe_execution_allowed | false |
| execution_allowed | false |
| execution_marker | NOT_EXECUTABLE |
| v4_i2_allowed_to_execute | false |
| v4_j_allowed_to_execute | false |

## Proposed Command (REVIEW ONLY — STILL NOT EXECUTABLE)

```
# V4 controlled observe single-window command
# STILL NOT EXECUTABLE (V4-I.1 runner defined but execution blocked)

OPENCLAW_NO_PUSH=1 python3 engine/v4_observe_runner.py \
  --observe-only \
  --dry-run \
  --single-window-only \
  --no-push \
  --no-state-write \
  --no-verified-write \
  --no-cron \
  --no-api \
  --no-key-read \
  --no-supervisor \
  --watchdog-only-failure \
  --no-ai-kill-retry \
  --preserve-logs \
  --manifest-required \
  --review-only \
  --date 20260519 \
  --window midday
```

## Notes

- `engine/v4_observe_runner.py` is already defined as a no-exec runner.
- `--date` and `--window` are required runner inputs.
- V4-I.2 defines four-window preview review (`early/midday/evening/night`) as evidence generation only.
- V4-I.2 is generate-only; execution stays blocked.
- Command draft remains review-only and must not be executed.
- Legacy marker retained for compatibility: `NOT_EXECUTABLE_UNTIL_RUNNER_DEFINED`.
- Route and sent markers are NOT created in this phase.
- No lock is acquired.
- No state is written.
- No QQ is sent.
- Any real observe execution requires separate explicit BOSS instruction.
