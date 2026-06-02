# V3 World Cup T-10 Readiness

Date: 2026-06-02

## Scope

V3-WC10 is a World Cup readiness observation layer for Perception Gap war-room use.
It is not a betting recommendation system and does not modify V4 logic.

## Baseline Snapshot

- teams: 46/46
- players: 1375
- status: `WAR_ROOM_READY_WITH_WARN_ONLY`
- status_level: `CODE_READY`
- blocker: `NONE`

## WARN_ONLY Reasons (supplement gaps)

- caps/goals/minutes
- injury reports
- friendlies
- market baseline (supplement-level)
- club form
- coach profiles
- WC history

## Safety Boundary

- Perception Gap watchlist is observation-only.
- No betting recommendation output.
- No impact on V4 official grade.
- No QQ push.
- No pending write.
- No validation recompute.
- No change to `73.5`.
- No change to `DEFAULT_RULES` or A/B thresholds.
- `26_QQ_push_disabled` is out-of-scope (`NON_V3_EXISTING_WARN_ONLY`).
- RF shadow guard canary issues are out-of-scope (`PRE_EXISTING_V4_CANARY_WARN_ONLY`).

## WC4B Historical Market Baseline

- status: locked observation baseline
- years: 2014 / 2018 / 2022
- matches: 192
- favorite failed rate: 42.2%
- heavy favorite win rate: 71.9%
- strong favorite win rate: 60.5%
- qualifiers included: no
- V4 impact: none

## WC4C Perception Gap Blueprint

- status: scoring blueprint only
- based on: WC4B historical market baseline
- input layer 1: historical market baseline
- input layer 2: current market/API prediction
- input layer 3: lineup/formation/value delta
- output tags: `UNDERVALUED_WATCH`, `OVERHYPED_RISK`, `MARKET_FAIR`, `LINEUP_WEAKENED`, `LINEUP_STRONGER_THAN_EXPECTED`, `DATA_INSUFFICIENT`, `WATCH_ONLY`
- `observation_only = true`
- `betting_recommendation = false`
- `affects_v4_grade = false`
- `auto_bet_allowed = false`
- API called: no
- official final squad write: no

## Next Suggested Phase

1. OpenClaw read-only acceptance and final lock
2. V3-WC4D match-level perception gap dry-run with cached fixtures and manually supplied lineup/value sample
3. V3-WC5E candidate review dashboard integration
4. V3-WC6 authorized offline final squad ingestion dry-run layer
5. V3-WC7 real final squad source authorization gate
