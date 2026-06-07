# V4 Offline Research Phase Freeze Summary

Date: 2026-06-07

## Scope

This document freezes the current V4 offline research phase based on
Football-Data replay, bucket analysis, context-aware replay, and the positive
bucket explanation audit.

This is an offline research record only. It does not call api-football, run V4
scan, change official grades, write pending candidates, send QQ, change cron or
launchd, or change any production route.

## Current Freeze

The current research phase cannot enter production.

Reasons:

- Market-level replay remains negative:
  - `FT_OVER25 ROI=-0.0471`
  - `1X2 ROI=-0.0800`
  - `ASIAN_HANDICAP ROI=-0.0245`
- `HIGH_CONFIDENCE=0`.
- `research_candidate_count=0`.
- Context-aware replay found only 2 positive ROI buckets, and both are
  research-only.
- Positive buckets are small-sample cases and carry early-season or
  single-cluster risk.

## Market Decisions

- `FT_OVER25`: keep research-only; needs attack, defense, and tempo context.
- `1X2`: downgrade to auxiliary-only because the market-level replay is the
  weakest.
- `ASIAN_HANDICAP`: keep research-only; needs strength, price, and schedule
  context.
- `DOUBLE_CHANCE_PROXY`: auxiliary hit-rate view only because there is no real
  Double Chance price.

## Positive Bucket Audit

Two positive ROI buckets were audited:

- `ASIAN_HANDICAP`: sample count is 6. It is small-sample and has early-season
  risk.
- `FT_OVER25`: sample count is 52. It is small-sample and has single-cluster
  risk.

Policy: `RESEARCH_ONLY_NOT_EDGE`.

## Stop Line

- `cannot_online=true`
- `research_candidate_count=0`
- `restore_scan_allowed=false`
- `restore_qq_allowed=false`
- `official_change_allowed=false`
- `pending_write_allowed=false`
- `cron_or_launchd_change_allowed=false`

Do not restore official flow, QQ flow, pending flow, daily scan, cron, or
launchd from this research phase.

## Allowed Next Actions

Only these research directions remain open:

- Add context variables.
- Expand replay data sources.
- Redesign the research hypothesis.

Any future work must stay offline until a new pack explicitly changes that
boundary.
