# V4 Selection Strategy Redesign Freeze

## Scope

This pack freezes a new V4 selection principle. It does not implement a new
official grading rule and does not increase recommendation volume.

No live API call, real scan, official grade change, A/B threshold change,
pending write, validation recompute, live bet mutation, QQ push, or cron/launchd
change is authorized by this document.

## Diagnosis

The previous risk audit found useful V4 signal artifacts but not enough evidence
to claim sustainable betting edge:

- Validation artifacts measure half-time outcome and bucket hit, not ROI.
- Odds/price coverage is incomplete.
- Official A/B outcome rates are strong, but price-aware replay is missing.
- RF shadow promotion strict checker blocks SKIP to B expansion:
  `shadow_b_above_official_b`, `default_replay_distribution_changed`,
  `skip_to_b_nonzero`, `sensitivity_77_SKIP_to_B_count_unsafe`,
  `sensitivity_73.5_SKIP_to_B_count_unsafe`.

That BLOCKER is correct and must remain a risk guard. It must not be bypassed
by weakening the checker or relabeling SKIP/C/shadow rows as official
recommendations.

## Frozen Selection Principle

The new V4 research direction is low-frequency, high-confidence observation
based on four pillars:

1. Strength gap must be explicit.
2. Market/line movement must confirm or at least not conflict.
3. Odds and price quality must be evaluable.
4. Data coverage must be sufficient.

Supporting rules:

- H2H is auxiliary context only. It cannot dominate selection and cannot
  manufacture A/B by itself.
- Historical matchup probability cannot manufacture A/B without strength gap,
  market confirmation, price quality, and data-quality guards.
- RF shadow and dry-run outputs remain observation/replay until price-aware
  replay proves a durable low-drawdown pattern.
- No-opportunity days are valid outcomes.

## Required Missing Features

The current V4 artifact set is missing several pieces required before any
strategy promotion:

- price-aware ROI ledger
- closing or last-pre-kickoff odds proxy
- market movement timeline
- league strength tier with source quality
- fatigue, travel, injury, and source-quality fields
- drawdown ledger
- rejected-candidate ledger for no-price and market-conflict cases

Without these features, V4 must avoid claims of sustainable edge.

## Forced Downgrade Or No-Alert Buckets

The following buckets are frozen as no real-time reminder / no official
promotion buckets unless a future BOSS-approved pack changes policy:

- `SKIP`
- `C`
- `shadow-only`
- `MARKET_NO_DATA`
- `MARKET_EXTREME`
- `H2H_LOW_SAMPLE`
- weak recent form
- stale recent form
- unknown recent form

These buckets may appear in dashboard observation, daily report, or replay
analysis only. They must not be written as official recommendation.

## Next Research Path

The next safe phase is a price-aware replay ledger:

1. Build a replay-only ledger with fixture, official grade, shadow grade,
   market state, odds proxy, last-pre-kickoff price, result, and drawdown.
2. Compare official A/B against C/SKIP/shadow-only without promoting the latter.
3. Require enough sample size before any policy proposal.
4. Keep output observation-only and no-betting until separately authorized.

## Operational Policy

- No official A/B: daily report only.
- Official A/B but guard incomplete: dashboard/daily report only.
- C/SKIP/shadow-only/dry-run/replay: never trigger real-time reminder.
- Official high-confidence A/B with complete guards: eligible for compact
  reminder, subject to existing QQ policy and separate authorization.

This freeze intentionally reduces gambling-like behavior and night-watch
pressure. It does not attempt to increase daily picks.
