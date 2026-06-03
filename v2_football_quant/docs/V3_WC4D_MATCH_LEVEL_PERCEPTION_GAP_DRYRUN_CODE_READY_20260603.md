# V3 WC4D Match-Level Perception Gap Dry Run Code Ready

## Scope

This change makes the WC4D match-level perception gap dry run repeatable and visible in the V3 World Cup war room.

It is observation-only. It does not change V4, grading rules, validation, QQ, live-bet records, cron, or scoring thresholds.

## Builder

- `tools/build_v3_worldcup_match_level_perception_gap_dryrun.py`
- Reads local WC4B historical market baseline, WC5D candidate review artifact, venue stress layer, and cached 2026 World Cup matches.
- Outputs:
  - `data/runtime/v3_worldcup/perception_gap_dryrun/v3_wc4d_match_level_perception_gap_dryrun_20260603.csv`
  - `data/runtime/v3_worldcup/perception_gap_dryrun/V3_WC4D_MATCH_LEVEL_PERCEPTION_GAP_DRYRUN_20260603.md`
  - `data/runtime/v3_worldcup/perception_gap_dryrun/v3_wc4d_match_level_perception_gap_dryrun_status_20260603.json`

## Checker

- `tools/check_v3_worldcup_match_level_perception_gap_dryrun.py`
- Confirms five samples are present.
- Confirms coverage of high heat or humidity, altitude, ordinary low pressure, popular strong team, and mixed pressure samples.
- Confirms selected samples with `odds_available=false` and `xg_available=false` carry `data_insufficient_reason`.
- Confirms:
  - `observation_only=true`
  - `betting_recommendation=false`
  - `affects_v4_grade=false`
  - `scoring_changed=false`
  - `SQUAD_CANDIDATE_REVIEW_OK` does not appear
  - `SQUAD_CANDIDATE_KNOWN` appears without implying confirmed final squad
  - team-level statuses keep `OFFICIAL_CONFIRMED` distinct from API candidate statuses
  - `VENUE_UPSET_WATCH` carries `upset_watch_definition=historical_data_insufficient_for_probability`
  - market data status path is frozen as `CURRENT_MARKET_DATA_MISSING -> MARKET_DATA_PARTIAL -> MARKET_DATA_AVAILABLE`

## War Room

`tools/build_v3_worldcup_wc10_war_room.py` reads the WC4D runtime CSV/status and exposes:

- `match_level_perception_gap_dryrun_status`
- `match_level_perception_gap_dryrun_sample_count`
- `match_level_perception_gap_dryrun_samples`
- `match_level_perception_gap_dryrun_safety_guard`

`data/runtime/dashboard/v3_worldcup_wc10_war_room.html` renders the same data as a match-level observation block only.

## Safety

WC4D is a dry-run observation layer. It only surfaces market gap tags, venue stress tags, squad data quality, perception gap tags, and data insufficiency reasons for selected samples.

WC4E freezes the WC4D labels before any future scoring work:

- `SQUAD_CANDIDATE_KNOWN` means the local candidate-review artifact has known candidate status for both teams. It does not mean confirmed final squad.
- `OFFICIAL_CONFIRMED` remains visible in `home_candidate_status` or `away_candidate_status` and is distinct from `API_CLEAN_CANDIDATE`.
- `VENUE_UPSET_WATCH` is retained as a venue-stress observation tag only. Its definition is `historical_data_insufficient_for_probability`; it is not an upset prediction and it is not a scoring input.
- Current WC4D samples remain `CURRENT_MARKET_DATA_MISSING`. The only allowed future status path is `CURRENT_MARKET_DATA_MISSING -> MARKET_DATA_PARTIAL -> MARKET_DATA_AVAILABLE`.
