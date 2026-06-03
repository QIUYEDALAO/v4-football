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

## War Room

`tools/build_v3_worldcup_wc10_war_room.py` reads the WC4D runtime CSV/status and exposes:

- `match_level_perception_gap_dryrun_status`
- `match_level_perception_gap_dryrun_sample_count`
- `match_level_perception_gap_dryrun_samples`
- `match_level_perception_gap_dryrun_safety_guard`

`data/runtime/dashboard/v3_worldcup_wc10_war_room.html` renders the same data as a match-level observation block only.

## Safety

WC4D is a dry-run observation layer. It only surfaces market gap tags, venue stress tags, squad data quality, perception gap tags, and data insufficiency reasons for selected samples.
