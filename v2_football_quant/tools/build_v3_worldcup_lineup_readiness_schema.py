#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data/manual_sources/v3_worldcup/squads/fifa_final_26/processed"
PLAYERS_JSON = BASE / "v3_wc2026_final_26_players.json"
TEAMS_JSON = BASE / "v3_wc2026_final_26_teams.json"
SUMMARY_JSON = BASE / "v3_wc2026_final_26_summary.json"
PROFILE_OBSERVATION = BASE / "v3_wc2026_final_26_squad_profile_observation.json"
TACTICAL_PROFILE = ROOT / "data/v3_worldcup/tactical_profile/v3_worldcup_tactical_profile_layer_20260604.json"
SCHEMA_OUT = BASE / "v3_wc2026_lineup_readiness_schema.json"
TEAM_STATUS_OUT = BASE / "v3_wc2026_lineup_readiness_team_status.json"

SAFETY = {
    "observation_only": True,
    "no_starting_xi_generated": True,
    "no_prediction": True,
    "no_injury_judgment": True,
    "betting_recommendation": False,
    "affects_v4": False,
}
POSITIONS = ["GK", "DF", "MF", "FW"]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def tactical_by_team() -> dict[str, dict[str, Any]]:
    payload = load_json(TACTICAL_PROFILE) if TACTICAL_PROFILE.exists() else {}
    profiles = payload.get("profiles") if isinstance(payload.get("profiles"), list) else []
    return {str(item.get("team") or ""): item for item in profiles if isinstance(item, dict)}


def build_schema() -> dict[str, Any]:
    return {
        "schema_name": "v3_wc2026_lineup_readiness_schema",
        "tournament": "FIFA World Cup 2026",
        "schema_status": "SCHEMA_READY_WAIT_OFFICIAL_LINEUP",
        "source_strategy": {
            "final_26_canonical_source": str(PLAYERS_JSON.relative_to(ROOT)),
            "tactical_profile_source": str(TACTICAL_PROFILE.relative_to(ROOT)),
            "historical_formation_source": str(TACTICAL_PROFILE.relative_to(ROOT)),
            "official_lineup_future_source": "official_matchday_lineup_feed_not_ingested",
            "source_trust_level": "OFFICIAL_FINAL_26_PLUS_HISTORICAL_OBSERVATION",
            "source_status": "FINAL_26_READY_MATCHDAY_LINEUP_NOT_AVAILABLE",
        },
        "team_status_schema": {
            "team": "string",
            "team_slug": "string",
            "final_26_player_count": 26,
            "starting_xi_status": "NOT_AVAILABLE",
            "starting_xi_source": "NONE",
            "starting_xi_players": [],
            "predicted_xi_generated": False,
            "matchday_lineup_status": "WAIT_OFFICIAL_LINEUP",
            "formation_status": "HISTORICAL_OBSERVATION_ONLY",
            "historical_formations_observed": "array[string]",
            "tactical_profile_ref": "string",
            "official_lineup_future_source": "official_matchday_lineup_feed_not_ingested",
            "data_insufficient_reason": "official_matchday_lineup_not_available",
            **SAFETY,
        },
        "safety": SAFETY,
    }


def build_team_status() -> dict[str, Any]:
    players = load_json(PLAYERS_JSON)
    teams = load_json(TEAMS_JSON)
    summary = load_json(SUMMARY_JSON)
    profile = load_json(PROFILE_OBSERVATION)
    tactical = tactical_by_team()
    players_by_slug: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for player in players:
        players_by_slug[str(player.get("team_slug") or "")].append(player)

    team_rows = []
    for team in sorted(teams, key=lambda item: str(item.get("team") or "")):
        team_name = str(team.get("team") or "")
        slug = str(team.get("team_slug") or "")
        squad = players_by_slug[slug]
        positions = Counter(str(player.get("position") or "") for player in squad)
        tactical_item = tactical.get(team_name, {})
        formations = []
        common = tactical_item.get("common_formation")
        if common:
            formations.append(str(common))
        alternatives = tactical_item.get("alternative_formations") if isinstance(tactical_item.get("alternative_formations"), list) else []
        formations.extend(str(item) for item in alternatives if item)
        seen = []
        for formation in formations:
            if formation not in seen:
                seen.append(formation)
        team_rows.append({
            "team": team_name,
            "team_slug": slug,
            "final_26_player_count": len(squad),
            "fifa_position_distribution": {position: positions.get(position, 0) for position in POSITIONS},
            "starting_xi_status": "NOT_AVAILABLE",
            "starting_xi_source": "NONE",
            "starting_xi_players": [],
            "predicted_xi_generated": False,
            "matchday_lineup_status": "WAIT_OFFICIAL_LINEUP",
            "formation_status": "HISTORICAL_OBSERVATION_ONLY",
            "historical_formations_observed": seen,
            "tactical_profile_ref": str(TACTICAL_PROFILE.relative_to(ROOT)) if tactical_item else "",
            "official_lineup_future_source": "official_matchday_lineup_feed_not_ingested",
            "data_insufficient_reason": [
                "official_matchday_lineup_not_available",
                "no_confirmed_lineup_feed_ingested",
                "formation_is_historical_observation_only",
            ],
            **SAFETY,
        })
    return {
        "module": "v3_wc2026_lineup_readiness_team_status",
        "tournament": "FIFA World Cup 2026",
        "generated_from": {
            "players_json": str(PLAYERS_JSON.relative_to(ROOT)),
            "teams_json": str(TEAMS_JSON.relative_to(ROOT)),
            "summary_json": str(SUMMARY_JSON.relative_to(ROOT)),
            "squad_profile_observation": str(PROFILE_OBSERVATION.relative_to(ROOT)),
            "tactical_profile": str(TACTICAL_PROFILE.relative_to(ROOT)),
        },
        "team_count": len(team_rows),
        "total_players": len(players),
        "teams_with_26_players": int(summary.get("teams_with_26_players") or 0),
        "position_distribution": summary.get("position_distribution") or profile.get("position_distribution") or {},
        "starting_xi_status": "NOT_AVAILABLE",
        "matchday_lineup_status": "WAIT_OFFICIAL_LINEUP",
        "formation_status": "HISTORICAL_OBSERVATION_ONLY",
        "teams": team_rows,
        "safety": SAFETY,
    }


def main() -> int:
    for path in [PLAYERS_JSON, TEAMS_JSON, SUMMARY_JSON, PROFILE_OBSERVATION]:
        if not path.exists():
            raise FileNotFoundError(path)
    schema = build_schema()
    team_status = build_team_status()
    SCHEMA_OUT.write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8")
    TEAM_STATUS_OUT.write_text(json.dumps(team_status, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "conclusion": "PASS",
        "schema": str(SCHEMA_OUT),
        "team_status": str(TEAM_STATUS_OUT),
        "team_count": team_status["team_count"],
        "total_players": team_status["total_players"],
        "starting_xi_status": team_status["starting_xi_status"],
        "matchday_lineup_status": team_status["matchday_lineup_status"],
        "formation_status": team_status["formation_status"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
