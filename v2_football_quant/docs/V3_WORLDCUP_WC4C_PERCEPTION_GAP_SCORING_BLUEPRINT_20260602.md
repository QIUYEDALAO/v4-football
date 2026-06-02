# V3 World Cup WC4C Perception Gap Scoring Blueprint

## Status

- Phase: `V3_WC4C_PERCEPTION_GAP_SCORING_BLUEPRINT`
- Status: code-ready blueprint
- Scope: observation layer only
- Based on: locked WC4B historical market baseline

## Baseline

WC4C uses the WC4B historical market baseline as the first input layer:

- Years: 2014 / 2018 / 2022 World Cup finals
- Matches: 192
- Heavy favorite count: 57
- Heavy favorite win rate: 71.9%
- Strong favorite count: 38
- Strong favorite win rate: 60.5%
- Favorite failed count: 81
- Favorite failed rate: 42.2%
- Underdog upset count: 43
- Draw result count: 38
- HT draw count: 95
- Over 2.5 count: 99
- BTTS count: 96
- Qualifiers: not included

## Input Layers

1. Historical market baseline
   - favorite band
   - historical favorite win / failed rates
   - historical draw / HT draw / upset / over 2.5 / BTTS rates

2. Current market and API prediction
   - current 1x2 prices
   - current favorite team and favorite band
   - market expectation score
   - public heat proxy
   - API prediction home / draw / away

3. Lineup, formation, and value delta
   - starting XI value
   - expected value baseline
   - value delta
   - formation
   - core absence and spine risk flags

## Output Tags

- `UNDERVALUED_WATCH`
- `OVERHYPED_RISK`
- `MARKET_FAIR`
- `LINEUP_WEAKENED`
- `LINEUP_STRONGER_THAN_EXPECTED`
- `DATA_INSUFFICIENT`
- `WATCH_ONLY`

## Safety

- `observation_only = true`
- `betting_recommendation = false`
- `affects_v4_grade = false`
- `auto_bet_allowed = false`
- `official_final_squad_required = false`

WC4C only defines structure. It does not output match conclusions, does not change V4 A/B/C/SKIP, does not call API, does not fetch web data, and does not write official final squad artifacts.

## Out Of Scope

- `26_QQ_push_disabled` remains a pre-existing non-V3 warning.
- RF shadow guard canary issues remain pre-existing V4 canary warnings.
- Neither is repaired in WC4C.
