# V4 Controlled Observe Command Draft

Phase: V4-I
Date: 2026-05-19
Status: REVIEW_ONLY_DRAFT — NOT EXECUTABLE

## Command Classification

| Field | Value |
|-------|-------|
| command_type | REVIEW_ONLY_DRAFT |
| command_must_not_execute | true |
| runner_exists | true (V4-I.1) |
| runner_required_before_execution | true |
| observe_execution_allowed | false |
| execution_allowed | false |

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
  --manifest-required
```

## Notes

- No `engine/v4_observe_runner.py` exists at this stage.
- Command draft defines ALL required flags for future runner implementation.
- Flags marked as `NOT_EXECUTABLE_UNTIL_RUNNER_DEFINED`.
- Route and sent markers are NOT created in this phase.
- No lock is acquired.
- No state is written.
- No QQ is sent.

## Required Runner Capabilities

Future `engine/v4_observe_runner.py` must support ALL flags listed above.
The checker `check_v4_controlled_observe_approval.py` will validate flag coverage.
