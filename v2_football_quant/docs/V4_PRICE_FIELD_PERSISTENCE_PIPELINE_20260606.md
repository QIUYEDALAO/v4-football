# V4 Price Field Persistence Pipeline

## Scope

This pack persists price fields that already exist in later V4 scout artifacts
into the official candidate_view and validation ledger builders.

It is not a strategy launch, not a recommendation-volume increase, and not a
real-time reminder restore. No live API is called, no scan is executed, no
official grades or thresholds are changed, no pending candidates are written,
QQ is not pushed, and cron/launchd are not changed.

## Source Inventory Input

The previous inventory established:

- official A/B historical ledger has no real odds; it only has
  `paper_default_0.80`.
- later scout artifacts contain partial real market fields.
- current official candidate_view artifacts do not persist price event fields.

This pack starts the persistence path for future artifacts. It does not rewrite
runtime history.

## Source Fields

The scout source fields are:

- `fixture_id`
- `kickoff` / `kickoff_time`
- `opening_market_bookmaker_used`
- `opening_market_market_name`
- `opening_market_bet_name`
- `opening_market_source`
- `opening_market_snapshot_time`
- `opening_ht_ou_line`
- `opening_ht_ou_over_odds`
- `opening_ht_ou_under_odds`
- `prematch_ht_line`
- `prematch_over_odds`
- `prematch_under_odds`

## Candidate View Fields

Future official candidate_view rows preserve:

- `price_source`
- `bookmaker`
- `market`
- `line`
- `odds`
- `snapshot_time`
- `selected_at`
- `kickoff_time`
- `price_status`

`price_status` values:

- `REAL_PRICE`: bookmaker, market, line, odds, and snapshot time exist.
- `PRICE_MISSING`: no usable real price was saved for the event.
- `PAPER_PROXY_FORBIDDEN`: a paper/default proxy was detected and must not be
  treated as real odds.

## Validation Ledger Fields

The validation ledger builder now carries the same fields from candidate_view
rows into ledger rows when available:

- `price_source`
- `bookmaker`
- `market`
- `line`
- `odds`
- `snapshot_time`
- `selected_at`
- `kickoff_time`
- `price_status`

This allows future rows to join `result_hit` with saved price fields. Existing
historical paper rows remain non-authoritative for price-aware edge.

## Paper Default Policy

`paper_default` is never a real odds source.

If a row contains `paper_default_0.80`, the persistence layer must not copy it
into `odds` as a real price. The row is marked `PAPER_PROXY_FORBIDDEN` or kept
outside the true price ledger.

## Offline Verification

The checker uses existing `20260531` scout and brief artifacts. It builds a
candidate_view in memory only and verifies:

- A/B/C/SKIP counts are unchanged from the current candidate_view.
- existing real scout price fields are carried into A/B candidate rows.
- missing price is marked `PRICE_MISSING`.
- paper default is marked `PAPER_PROXY_FORBIDDEN`.
- validation ledger builder can accept the same real price fields.

## Safety

Official grades and thresholds are unchanged.

B real-time reminders remain paused. Shadow/C/SKIP remain observation-only.
This work only creates the data trail needed for future true price-aware replay.

Machine-check policy: paper_default is never a real odds source; official grades and thresholds are unchanged.
