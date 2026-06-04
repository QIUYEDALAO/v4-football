# V3 WC Lineup Readiness Schema Pack Phase 1

## Scope

Phase 1 adds a lineup readiness schema and team-level readiness status for
official matchday lineup ingestion.

This phase does not generate an eleven-player lineup, does not choose players,
does not assert official formations, does not evaluate injuries or suspensions,
does not forecast matches, and does not affect V4.

## Outputs

- `data/manual_sources/v3_worldcup/squads/fifa_final_26/processed/v3_wc2026_lineup_readiness_schema.json`
- `data/manual_sources/v3_worldcup/squads/fifa_final_26/processed/v3_wc2026_lineup_readiness_team_status.json`

## Status Contract

Every team row carries:

- `final_26_player_count=26`
- `starting_xi_status=NOT_AVAILABLE`
- `starting_xi_source=NONE`
- `starting_xi_players=[]`
- `predicted_xi_generated=false`
- `matchday_lineup_status=WAIT_OFFICIAL_LINEUP`
- `formation_status=HISTORICAL_OBSERVATION_ONLY`
- `official_lineup_future_source=official_matchday_lineup_feed_not_ingested`

Historical formations are kept as observation context only.

## Safety

Every team row and the top-level payload carry:

- `observation_only=true`
- `no_starting_xi_generated=true`
- `no_prediction=true`
- `no_injury_judgment=true`
- `betting_recommendation=false`
- `affects_v4=false`

## Verification

Run:

```bash
python3 tools/check_v3_worldcup_lineup_readiness_schema.py
python3 tools/check_v3_worldcup_final_26_pack_manifest.py
python3 tools/check_v3_worldcup_wc10_war_room.py
python3 tools/check_v3_worldcup_no_betting_words.py
```
