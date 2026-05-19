# V2 D10 Controlled Proof Command Drafts

Phase: D.10
Date: 2026-05-19
Status: REVIEW_ONLY_DRAFT — NOT EXECUTABLE UNTIL RUNNER DEFINED

## Classification

| Field | Value |
|-------|-------|
| command_type | REVIEW_ONLY_DRAFT |
| command_must_not_execute | true |
| runner_exists | false |
| runner_required_before_execution | true |
| execution_authorization_required | true |

## Required Flags (all commands)

```
--no-push
--no-cron
--no-state-write
--no-verified-write
--no-api
--no-key-read
--no-supervisor
--watchdog-only-failure
--no-ai-kill-retry
--preserve-logs
--manifest-required
--review-only
```

## Draft 1: real_state_present_case

```bash
OPENCLAW_NO_PUSH=1 python3 tools/sandbox_v2_state_present.py --observe-only --dry-run \
  --no-state-write --no-verified-write --date <DATE> --review-only
```
Status: runner_exists=false | NOT_EXECUTABLE

## Draft 2: active_window_mutation_path

```bash
OPENCLAW_NO_PUSH=1 python3 tools/sandbox_v2_window_worker.py --observe-only --dry-run \
  --single-window-only --date <DATE> --window <early|midday> --review-only
```
Status: runner_exists=false | NOT_EXECUTABLE

## Draft 3: production_cron_path

```bash
OPENCLAW_NO_PUSH=1 python3 engine/v2_cron_schedule_dryrun.py --schedule-only --dry-run \
  --date <DATE> --no-enable --review-only
```
Status: runner_exists=false | NOT_EXECUTABLE

## Draft 4: production_qq_path

```bash
OPENCLAW_NO_PUSH=1 python3 engine/v2_qq_route_dryrun.py --dry-run --no-push \
  --date <DATE> --review-only
```
Status: runner_exists=false | NOT_EXECUTABLE

## Draft 5: production_verified_path

```bash
OPENCLAW_NO_PUSH=1 python3 tools/verify_v2_verified_path.py --dry-run --no-write \
  --date <DATE> --review-only
```
Status: runner_exists=false | NOT_EXECUTABLE

## Draft 6: formal_state_write_path

```bash
OPENCLAW_NO_PUSH=1 python3 tools/sandbox_v2_state_write.py --observe-only --dry-run \
  --no-write --date <DATE> --review-only
```
Status: runner_exists=false | NOT_EXECUTABLE

## Notes

- None of these runners currently exist.
- All commands are REVIEW_ONLY_DRAFT.
- No command may be executed without BOSS authorization.
- Each proof target requires individual runner implementation.
