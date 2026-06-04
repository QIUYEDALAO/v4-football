# V3 WC 2026 Dashboard UI 104 Read Path Check Pack

## Scope

This pack verifies and locks the V3 World Cup dashboard UI read path.

- Executor: Codex
- Primary UI: `data/runtime/dashboard/v3_worldcup_wc10_war_room.html`
- Dashboard read model: `data/manual_sources/v3_worldcup/war_room/v3_wc2026_dashboard_104_read_model.json`
- Canonical schedule scope: `FULL_TOURNAMENT_104_INDEX`
- Group-stage view scope: `GROUP_STAGE_ONLY_72`
- Knockout policy: `STRUCTURAL_ONLY_NO_TEAM_GENERATED`

## Read Path

The dashboard UI now fetches:

`/data/manual_sources/v3_worldcup/war_room/v3_wc2026_dashboard_104_read_model.json`

The UI must not fetch the old WC10 JSON as its dashboard source:

`/data/v3_worldcup/war_room/v3_worldcup_wc10_war_room_20260602.json`

The 72-card group-stage file remains a view referenced by the read model. It is not a complete tournament source and is not fetched directly by the dashboard UI.

## Display Policy

- 104 cards are the canonical full-tournament index.
- 72 cards remain visible only as `GROUP_STAGE_ONLY_72`.
- 32 knockout cards are structural slots only.
- Knockout slots must not generate teams, fixtures, venues, predictions, or lineup claims.
- The dashboard must not double-read 72 and 104 as competing complete sources.

## Safety

- observation_only=true
- no_starting_xi_generated=true
- no_prediction=true
- no_injury_judgment=true
- betting_recommendation=false
- affects_v4=false

No live API call, cron, launchd, V4 scan, QQ push, runtime output submission, or secret material is part of this pack.

## Checker

`tools/check_v3_worldcup_dashboard_ui_104_read_path.py` verifies:

- dashboard HTML fetches the 104 read model
- old WC10 JSON is not fetched as the UI source
- direct 72 card source fetch is absent
- 104/72/32 counts and labels are present
- knockout structural placeholder policy is visible
- double-read guard is visible
- safety fields remain observation-only and V4-unaffected
