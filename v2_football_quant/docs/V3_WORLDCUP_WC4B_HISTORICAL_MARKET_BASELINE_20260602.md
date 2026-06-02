# V3 World Cup WC4B Historical Market Baseline

Date: 2026-06-02

## Scope

WC4B makes the WC4A historical market baseline repeatable through builder/checker/dashboard integration.

## Data Sources

1. WorldCup2026.xlsx reference.
2. TheStatsAPI runtime cache under `data/runtime/v3_worldcup/thestatsapi_cache/20260602/`.
3. WC4A runtime baseline replay for repeatable local output.

## Finals Baseline

1. Years included: 2014, 2018, 2022.
2. Total World Cup finals matches: 192.
3. 2026 qualifiers are marked outside the finals baseline and are not included.

## Key Historical Rates

1. Heavy favorite win rate: 71.9%.
2. Strong favorite win rate: 60.5%.
3. Favorite failed rate: 42.2%.
4. Underdog upset count: 43.
5. Draw result count: 38.
6. HT draw count: 95.
7. Over 2.5 count: 99.
8. BTTS count: 96.

## TheStatsAPI Coverage

1. Match coverage: 128/192.
2. Odds coverage: 2018 34/64, 2022 33/64.
3. Lineup coverage: 2018 26/64, 2022 22/64.
4. xG/statistics/events are unavailable as supplemental endpoints and remain observation notes only.

## Safety Boundary

1. This is a Perception Gap historical observation baseline.
2. It is not a betting recommendation.
3. It does not affect V4.
4. It does not modify official final squad artifacts.
5. It does not call API or fetch the web.
6. `26_QQ_push_disabled` remains out of scope.
