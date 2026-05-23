# V3/V4 Intel Ops Console Daily Auto Refresh Runbook - 2026-05-21

## Scope

This runbook replaces the old `INTEL-OPS-CONSOLE-DAILY-AUTO-REFRESH-PIPELINE-CLOSEOUT` current-source contract with `V3V4-INTEL-OPS-CONSOLE-DAILY-AUTO-REFRESH-PIPELINE`.

## Active Sources

- V3 Perception Gap World Cup readiness system.
- V4 candidate model.
- V4 review `REPORT_ONLY` output.
- V4 dashboard renderer.
- Cloud readonly mirror metadata only.

## Explicitly Removed From Current Refresh

- V2 validation is not read.
- V2 historical pool is not read.
- V2 markers are not read.
- V2 dashboard modules are not generated.
- V2 cron/task state is not used as current source.
- V33 is not restored and must not be treated as V3.

## Safety Contract

- `capture_ran=false`.
- `qq_push=false`.
- `cloud_publish=false`.
- `cron_enabled=false`.
- `reverse_sync=false`.
- No new cron is created in this phase.
- V3/V4 strategy, candidate numbers, validation, and attribution outputs are unchanged.

## Execution Status

This phase defines the design and local dashboard refresh only. Cron remains disabled pending a separate BOSS authorization phase.
