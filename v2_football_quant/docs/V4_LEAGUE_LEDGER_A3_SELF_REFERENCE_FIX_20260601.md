# V4 League Ledger A3 Self-Reference Fix

Date: 2026-06-01

## Problem

A3 trend builder could compare current snapshot against itself in reruns.
This produced:
- `previous_snapshot_id == current_snapshot_id`
- `baseline_only=false`
- zero deltas that looked like a valid trend result

## Fix Rules

1. previous snapshot must be distinct from current:
- `previous_snapshot_id != current_snapshot_id`
- `previous_snapshot_path != current_snapshot_path`
- `previous.generated_at < current.generated_at` (when available)

2. if no distinct previous snapshot exists:
- `baseline_only=true`
- `baseline_only_reason=NO_PREVIOUS_DISTINCT_SNAPSHOT`
- previous snapshot fields empty
- trend change lists empty
- no fabricated trend delta

3. self-reference guard:
- emit `self_reference_guard_status=PASS` only when safe
- checker blocks non-baseline payloads that fail distinct-previous rules

4. same-day rerun:
- `snapshot_id` is unique per run
- `snapshot_date` is tracked separately

## Weekly Report Safety

- baseline-only shows: `当前仅有 baseline 快照，不能判断趋势。`
- if guard is not PASS, weekly trend section is BLOCKED/WARN behavior and must not be shown as normal no-change trend.

## Policy Boundary (unchanged)

- trend layer is observation-only, not connected to official grade.
- `73.5` unchanged.
- `DEFAULT_RULES` unchanged.
- A/B thresholds unchanged.
- no QQ push.
- no pending write.
- no validation recompute.
- no live bet change.
- no cron change.
- `LOW_TRUST_ALERT` not auto-exclude.
- `PENDING_ONLY` not in denominator.
- `DO_NOT_CONCLUDE` not negative grading.
- `26_QQ_push_disabled` is NON_A3_EXISTING_WARN_ONLY and out of scope for this fix.
