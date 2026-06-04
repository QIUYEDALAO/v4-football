#!/usr/bin/env python3
from __future__ import annotations

import json
import statistics
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data/manual_sources/v3_worldcup/squads/fifa_final_26"
PROCESSED = BASE / "processed"
PLAYERS_JSON = PROCESSED / "v3_wc2026_final_26_players.json"
TEAMS_JSON = PROCESSED / "v3_wc2026_final_26_teams.json"
SUMMARY_JSON = PROCESSED / "v3_wc2026_final_26_summary.json"

ROSTER_INDEX_JSON = PROCESSED / "v3_wc2026_final_26_war_room_roster_index.json"
TEAM_CARDS_JSON = PROCESSED / "v3_wc2026_final_26_team_observation_cards.json"
OBS_SUMMARY_JSON = PROCESSED / "v3_wc2026_final_26_squad_observation_summary.json"

AGE_REFERENCE_DATE = date(2026, 6, 11)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_birth_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value)
    except Exception:
        return None


def age_years(born: date | None) -> float | None:
    if not born:
        return None
    days = (AGE_REFERENCE_DATE - born).days
    return round(days / 365.2425, 2)


def player_brief(player: dict[str, Any]) -> dict[str, Any]:
    return {
        "player_id": player.get("player_id"),
        "squad_number": player.get("squad_number"),
        "position": player.get("position"),
        "full_name": player.get("full_name"),
        "shirt_name": player.get("shirt_name"),
        "birth_date": player.get("birth_date"),
        "club": player.get("club"),
        "height_cm": player.get("height_cm"),
    }


def top_counter_items(counter: Counter[str], limit: int = 5) -> list[dict[str, Any]]:
    return [
        {"club": key, "player_count": value}
        for key, value in counter.most_common(limit)
    ]


def build_layer() -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    players = load_json(PLAYERS_JSON)
    teams = load_json(TEAMS_JSON)
    source_summary = load_json(SUMMARY_JSON)
    players_by_team: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for player in players:
        players_by_team[str(player.get("team_slug") or "")].append(player)

    roster_index: list[dict[str, Any]] = []
    team_cards: list[dict[str, Any]] = []
    global_positions = Counter()
    global_clubs = Counter()
    all_ages: list[float] = []
    all_heights: list[int] = []

    for team in sorted(teams, key=lambda x: str(x.get("team") or "")):
        team_slug = str(team.get("team_slug") or "")
        squad = sorted(players_by_team[team_slug], key=lambda p: int(p.get("squad_number") or 0))
        position_counts = Counter(str(p.get("position") or "") for p in squad)
        by_position: dict[str, list[dict[str, Any]]] = {}
        for position in ["GK", "DF", "MF", "FW"]:
            by_position[position] = [player_brief(p) for p in squad if p.get("position") == position]
        ages = [age_years(parse_birth_date(str(p.get("birth_date") or ""))) for p in squad]
        ages = [x for x in ages if x is not None]
        heights = [int(p["height_cm"]) for p in squad if isinstance(p.get("height_cm"), int)]
        clubs = Counter(str(p.get("club") or "") for p in squad if p.get("club"))
        global_positions.update(position_counts)
        global_clubs.update(clubs)
        all_ages.extend(ages)
        all_heights.extend(heights)

        def player_by(metric: str, reverse: bool) -> dict[str, Any]:
            values = [p for p in squad if isinstance(p.get(metric), int)]
            if not values:
                return {}
            return player_brief(sorted(values, key=lambda p: int(p[metric]), reverse=reverse)[0])

        birth_values = [(parse_birth_date(str(p.get("birth_date") or "")), p) for p in squad]
        birth_values = [(d, p) for d, p in birth_values if d is not None]
        oldest = player_brief(sorted(birth_values, key=lambda x: x[0])[0][1]) if birth_values else {}
        youngest = player_brief(sorted(birth_values, key=lambda x: x[0], reverse=True)[0][1]) if birth_values else {}

        roster_index.append({
            "tournament": "FIFA World Cup 2026",
            "source": "FIFA official final 26 canonical processed layer",
            "team": team.get("team"),
            "team_slug": team_slug,
            "head_coach": team.get("head_coach"),
            "player_count": len(squad),
            "position_counts": {k: position_counts.get(k, 0) for k in ["GK", "DF", "MF", "FW"]},
            "players_by_position": by_position,
            "roster_player_ids": [p.get("player_id") for p in squad],
            "is_final_26": True,
            "is_official_fifa": True,
            "observation_only": True,
            "betting_recommendation": False,
            "affects_v4": False,
        })
        team_cards.append({
            "team": team.get("team"),
            "team_slug": team_slug,
            "head_coach": team.get("head_coach"),
            "player_count": len(squad),
            "gk_count": position_counts.get("GK", 0),
            "df_count": position_counts.get("DF", 0),
            "mf_count": position_counts.get("MF", 0),
            "fw_count": position_counts.get("FW", 0),
            "avg_age": round(statistics.mean(ages), 2) if ages else None,
            "median_age": round(statistics.median(ages), 2) if ages else None,
            "avg_height_cm": round(statistics.mean(heights), 2) if heights else None,
            "min_height_cm": min(heights) if heights else None,
            "max_height_cm": max(heights) if heights else None,
            "club_count": len(clubs),
            "top_clubs": top_counter_items(clubs),
            "oldest_player": oldest,
            "youngest_player": youngest,
            "tallest_player": player_by("height_cm", True),
            "shortest_player": player_by("height_cm", False),
            "observation_only": True,
            "no_starting_xi": True,
            "no_injury_judgment": True,
            "betting_recommendation": False,
            "affects_v4": False,
        })

    observation_summary = {
        "team_count": len(roster_index),
        "total_players": len(players),
        "coach_count": sum(1 for t in teams if t.get("head_coach")),
        "global_position_distribution": {k: global_positions.get(k, 0) for k in ["GK", "DF", "MF", "FW"]},
        "avg_age_global": round(statistics.mean(all_ages), 2) if all_ages else None,
        "avg_height_global": round(statistics.mean(all_heights), 2) if all_heights else None,
        "club_count_global": len(global_clubs),
        "teams_with_26_players": sum(1 for item in roster_index if item["player_count"] == 26),
        "source_summary_total_players": source_summary.get("total_players"),
        "observation_only": True,
        "is_final_26": True,
        "is_official_fifa": True,
        "no_starting_xi": True,
        "no_injury_judgment": True,
        "betting_recommendation": False,
        "affects_v4": False,
    }
    return roster_index, team_cards, observation_summary


def main() -> int:
    for path in [PLAYERS_JSON, TEAMS_JSON, SUMMARY_JSON]:
        if not path.exists():
            raise FileNotFoundError(path)
    roster_index, team_cards, observation_summary = build_layer()
    PROCESSED.mkdir(parents=True, exist_ok=True)
    ROSTER_INDEX_JSON.write_text(json.dumps(roster_index, ensure_ascii=False, indent=2), encoding="utf-8")
    TEAM_CARDS_JSON.write_text(json.dumps(team_cards, ensure_ascii=False, indent=2), encoding="utf-8")
    OBS_SUMMARY_JSON.write_text(json.dumps(observation_summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "conclusion": "PASS",
        "roster_index": str(ROSTER_INDEX_JSON),
        "team_cards": str(TEAM_CARDS_JSON),
        "observation_summary": str(OBS_SUMMARY_JSON),
        "team_count": observation_summary["team_count"],
        "total_players": observation_summary["total_players"],
        "coach_count": observation_summary["coach_count"],
        "teams_with_26_players": observation_summary["teams_with_26_players"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
