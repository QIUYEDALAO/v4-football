# V4 Daily Scan No Eligible Fixtures Notification Fix

Date: 2026-06-07

## Scope

This pack fixes notification routing for the durable V4 daily scan when the
runner executes successfully but the pre-scan fixture funnel has zero eligible
fixtures.

It does not run a scan, send QQ, change cron or launchd, change official grades,
write pending candidates, or change validation/live-bet behavior.

## State Model

- `REAL_COMPLETED_WITH_ARTIFACTS`: the durable runner completed with exit code 0,
  eligible fixtures existed, and scan artifacts are present.
- `NO_ELIGIBLE_FIXTURES`: the durable runner completed with exit code 0 and the
  pre-output eligible fixture count is 0. Missing scan artifacts are expected.
- `FAILED_OR_MISSING_ARTIFACTS`: the runner failed, timed out, or eligible
  fixtures existed but scan artifacts are missing.
- `PAUSED`: scan is paused and must not be described as a completed scan.
- `WATCHDOG_ONLY`: OpenClaw 12:00 status check only; it is not scan completion.

## Artifact Guard

For `scan_exit_code=0` and `eligible_fixture_count=0`, the artifact guard returns
`EXPECTED_NO_ELIGIBLE_FIXTURES`. In this state the absence of `scan_perf`,
`scout`, `brief`, and `candidate_view` is normal.

For `scan_exit_code=0` and `eligible_fixture_count>0`, missing artifacts remain
`MISSING_OR_FAILED`.

## Notification Text

`NO_ELIGIBLE_FIXTURES` must say:

`扫描执行完成；无符合条件比赛；无候选产物是正常结果；dashboard 不刷新。`

It must not send the failure/timeout/missing-artifacts wording.

`WATCHDOG_ONLY` and `PAUSED` must not use the real scan completion title.

## Verification

`tools/check_v4_daily_scan_no_eligible_fixtures_notification.py` verifies the
state model using synthetic status files in a temporary directory. It does not
send QQ, run scan, touch cron, or touch launchd.
