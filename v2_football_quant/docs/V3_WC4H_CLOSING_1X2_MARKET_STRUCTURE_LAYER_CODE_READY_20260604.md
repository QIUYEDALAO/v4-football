# V3 WC4H Closing 1X2 Market Structure Layer Code Ready

## Scope

WC4H turns the closing 1X2 source pack into a V3 World Cup observation layer.

This layer uses closing 1X2 data only. It does not infer opening movement, price drift, Asian Handicap movement, Over/Under movement, or fund flow.

It is observation-only, does not enter scoring, does not output recommendations, and does not affect V4.

## Inputs

- `data/manual_sources/v3_worldcup/odds/football_data/v3_wc_closing_1x2_source_pack/v3_wc_closing_1x2_market_structure.csv`
- `data/manual_sources/v3_worldcup/odds/football_data/v3_wc_closing_1x2_source_pack/v3_wc_closing_1x2_market_structure_summary.json`
- `data/manual_sources/v3_worldcup/odds/football_data/v3_wc_closing_1x2_source_pack/V3_WC_CLOSING_1X2_MARKET_STRUCTURE_REPORT.md`

## Outputs

- `data/v3_worldcup/closing_1x2_market_structure/v3_worldcup_closing_1x2_market_structure_20260604.json`
- `data/runtime/status/v3_worldcup_closing_1x2_market_structure_20260604.json`

## Available Tags

- `CLOSING_FAVORITE_HEAVY`
- `CLOSING_FAVORITE_STRONG`
- `CLOSING_FAVORITE_MODERATE`
- `FAVORITE_FAILURE_BASELINE`
- `BOOKMAKER_SPREAD_WIDE`
- `MARKET_SPLIT_WATCH`
- `DRAW_TRAP_WATCH`
- `UNDERDOG_UPSET_PROFILE`
- `MARKET_DATA_LIMITED_NO_OPENING`

## Disabled Tags

- `FAVORITE_STEAM`
- `FAVORITE_DRIFT`
- `LATE_SHARP_MOVE`
- `AH_LINE_MOVEMENT`
- `OU_LINE_MOVEMENT`
- `FUND_FLOW_SIGNAL`

These disabled tags are not emitted because the source pack has no opening odds, no timestamps, no AH/OU movement, and no matched volume.

## Acceptance

- 192 matches.
- 1X2 closing fields complete.
- Favorite failed rate: 42.2%.
- Heavy favorite failed: 28.1%.
- Strong favorite failed: 41.2%.
- Moderate favorite failed: 55.2%.
- War room displays the layer as closing 1X2 market structure observation only.
