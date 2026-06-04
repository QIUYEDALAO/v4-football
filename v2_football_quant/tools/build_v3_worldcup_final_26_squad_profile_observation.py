#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import statistics
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data/manual_sources/v3_worldcup/squads/fifa_final_26/processed"
PLAYERS_CSV = BASE / "v3_wc2026_final_26_players.csv"
PLAYERS_JSON = BASE / "v3_wc2026_final_26_players.json"
TEAMS_JSON = BASE / "v3_wc2026_final_26_teams.json"
TEAM_OBSERVATION_CARDS = BASE / "v3_wc2026_final_26_team_observation_cards.json"
WAR_ROOM_UI_PAYLOAD = BASE / "v3_wc2026_final_26_war_room_ui_payload.json"

PROFILE_OBSERVATION = BASE / "v3_wc2026_final_26_squad_profile_observation.json"
PROFILE_TEAM_CARDS = BASE / "v3_wc2026_final_26_squad_profile_team_cards.json"

AGE_REFERENCE_DATE = date(2026, 6, 11)
POSITIONS = ["GK", "DF", "MF", "FW"]
SAFETY = {
    "observation_only": True,
    "no_starting_xi": True,
    "no_injury_judgment": True,
    "no_prediction": True,
    "betting_recommendation": False,
    "affects_v4": False,
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_birth_date(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value))
    except Exception:
        return None


def age_years(value: Any) -> float | None:
    born = parse_birth_date(value)
    if not born:
        return None
    return round((AGE_REFERENCE_DATE - born).days / 365.2425, 2)


def median(values: list[float | int]) -> float | None:
    if not values:
        return None
    return round(float(statistics.median(values)), 2)


def mean(values: list[float | int]) -> float | None:
    if not values:
        return None
    return round(float(statistics.mean(values)), 2)


def player_brief(player: dict[str, Any]) -> dict[str, Any]:
    return {
        "player_id": player.get("player_id"),
        "team": player.get("team"),
        "team_slug": player.get("team_slug"),
        "squad_number": player.get("squad_number"),
        "position": player.get("position"),
        "full_name": player.get("full_name"),
        "shirt_name": player.get("shirt_name"),
        "birth_date": player.get("birth_date"),
        "club": player.get("club"),
        "height_cm": player.get("height_cm"),
    }


def player_with_age(player: dict[str, Any]) -> dict[str, Any]:
    out = player_brief(player)
    out["age"] = age_years(player.get("birth_date"))
    return out


def age_bucket(age: float | None) -> str:
    if age is None:
        return "unknown"
    if age < 23:
        return "u23"
    if age < 27:
        return "23_26"
    if age < 31:
        return "27_30"
    if age < 35:
        return "31_34"
    return "35_plus"


def height_bucket(height: Any) -> str:
    if not isinstance(height, int):
        return "unknown"
    if height < 175:
        return "under_175"
    if height < 180:
        return "175_179"
    if height < 185:
        return "180_184"
    if height < 190:
        return "185_189"
    return "190_plus"


def sorted_bucket_counts(counter: Counter[str], order: list[str]) -> dict[str, int]:
    return {key: counter.get(key, 0) for key in order}


def club_country_code(club: str) -> str | None:
    matches = re.findall(r"\(([A-Z]{3})\)", club or "")
    return matches[-1] if matches else None


def top_clubs(counter: Counter[str], limit: int = 8) -> list[dict[str, Any]]:
    return [{"club": club, "player_count": count} for club, count in counter.most_common(limit)]


def rank_cards(cards: list[dict[str, Any]], metric: str, reverse: bool, limit: int = 8) -> list[dict[str, Any]]:
    values = [card for card in cards if isinstance(card.get(metric), (int, float))]
    values.sort(key=lambda item: (float(item[metric]), str(item.get("team") or "")), reverse=reverse)
    return [
        {
            "team": card.get("team"),
            "team_slug": card.get("team_slug"),
            metric: card.get(metric),
            "player_count": card.get("player_count"),
        }
        for card in values[:limit]
    ]


def build_position_group_profiles(players: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_position: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for player in players:
        by_position[str(player.get("position") or "")].append(player)
    profiles: dict[str, dict[str, Any]] = {}
    for position in POSITIONS:
        group = by_position[position]
        ages = [age_years(player.get("birth_date")) for player in group]
        ages = [age for age in ages if age is not None]
        heights = [int(player["height_cm"]) for player in group if isinstance(player.get("height_cm"), int)]
        profiles[position] = {
            "player_count": len(group),
            "avg_age": mean(ages),
            "avg_height_cm": mean(heights),
        }
    return profiles


def build_layer() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    players = load_json(PLAYERS_JSON)
    teams = load_json(TEAMS_JSON)
    team_cards = load_json(TEAM_OBSERVATION_CARDS)
    ui_payload = load_json(WAR_ROOM_UI_PAYLOAD)
    cards_by_slug = {str(card.get("team_slug") or ""): card for card in team_cards}
    players_by_team: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for player in players:
        players_by_team[str(player.get("team_slug") or "")].append(player)

    profile_cards: list[dict[str, Any]] = []
    all_ages: list[float] = []
    all_heights: list[int] = []
    global_age_buckets: Counter[str] = Counter()
    global_height_buckets: Counter[str] = Counter()
    global_clubs: Counter[str] = Counter()
    position_distribution: Counter[str] = Counter()

    for team in sorted(teams, key=lambda item: str(item.get("team") or "")):
        slug = str(team.get("team_slug") or "")
        squad = sorted(players_by_team[slug], key=lambda p: int(p.get("squad_number") or 0))
        ages = [age_years(player.get("birth_date")) for player in squad]
        valid_ages = [age for age in ages if age is not None]
        heights = [int(player["height_cm"]) for player in squad if isinstance(player.get("height_cm"), int)]
        age_buckets = Counter(age_bucket(age) for age in ages)
        height_buckets = Counter(height_bucket(player.get("height_cm")) for player in squad)
        clubs = Counter(str(player.get("club") or "") for player in squad if player.get("club"))
        club_country_codes = Counter(
            code for code in (club_country_code(str(player.get("club") or "")) for player in squad) if code
        )
        positions = Counter(str(player.get("position") or "") for player in squad)
        all_ages.extend(valid_ages)
        all_heights.extend(heights)
        global_age_buckets.update(age_buckets)
        global_height_buckets.update(height_buckets)
        global_clubs.update(clubs)
        position_distribution.update(positions)

        by_birth = [(parse_birth_date(player.get("birth_date")), player) for player in squad]
        by_birth = [(born, player) for born, player in by_birth if born is not None]
        by_height = [player for player in squad if isinstance(player.get("height_cm"), int)]
        card = cards_by_slug.get(slug, {})
        profile_cards.append({
            "team": team.get("team"),
            "team_slug": slug,
            "head_coach": team.get("head_coach"),
            "player_count": len(squad),
            "position_distribution": {position: positions.get(position, 0) for position in POSITIONS},
            "age_profile": {
                "avg_age": mean(valid_ages),
                "median_age": median(valid_ages),
                "age_bucket_counts": sorted_bucket_counts(age_buckets, ["u23", "23_26", "27_30", "31_34", "35_plus", "unknown"]),
                "youngest_player": player_with_age(max(by_birth, key=lambda item: item[0])[1]) if by_birth else {},
                "oldest_player": player_with_age(min(by_birth, key=lambda item: item[0])[1]) if by_birth else {},
            },
            "height_profile": {
                "avg_height_cm": mean(heights),
                "median_height_cm": median(heights),
                "height_bucket_counts": sorted_bucket_counts(height_buckets, ["under_175", "175_179", "180_184", "185_189", "190_plus", "unknown"]),
                "tallest_player": player_brief(max(by_height, key=lambda player: int(player["height_cm"]))) if by_height else {},
                "shortest_player": player_brief(min(by_height, key=lambda player: int(player["height_cm"]))) if by_height else {},
            },
            "club_profile": {
                "club_count": len(clubs),
                "top_clubs": top_clubs(clubs),
                "domestic_club_count": None,
                "foreign_club_count": None,
                "club_country_code_counts": dict(sorted(club_country_codes.items())),
                "domestic_foreign_derivation": "not_derivable_without_canonical_team_country_code",
            },
            "position_group_profiles": build_position_group_profiles(squad),
            "source_refs": {
                "canonical_players": str(PLAYERS_JSON.relative_to(ROOT)),
                "canonical_teams": str(TEAMS_JSON.relative_to(ROOT)),
                "team_observation_card": card.get("team_slug"),
                "war_room_ui_payload_module": ui_payload.get("module"),
            },
            **SAFETY,
        })

    observation = {
        "tournament": "FIFA World Cup 2026",
        "source": "FIFA official final 26 canonical derived squad profile observation",
        "generated_from": {
            "players_csv": str(PLAYERS_CSV.relative_to(ROOT)),
            "players_json": str(PLAYERS_JSON.relative_to(ROOT)),
            "teams_json": str(TEAMS_JSON.relative_to(ROOT)),
            "team_observation_cards": str(TEAM_OBSERVATION_CARDS.relative_to(ROOT)),
            "war_room_ui_payload": str(WAR_ROOM_UI_PAYLOAD.relative_to(ROOT)),
        },
        "module": "final_26_squad_profile_observation",
        "team_count": len(profile_cards),
        "total_players": len(players),
        "position_distribution": {position: position_distribution.get(position, 0) for position in POSITIONS},
        "age_profile": {
            "avg_age": mean(all_ages),
            "median_age": median(all_ages),
            "age_bucket_counts": sorted_bucket_counts(global_age_buckets, ["u23", "23_26", "27_30", "31_34", "35_plus", "unknown"]),
            "youngest_player": min(
                (player_with_age(player) for player in players if age_years(player.get("birth_date")) is not None),
                key=lambda item: item["age"],
            ),
            "oldest_player": max(
                (player_with_age(player) for player in players if age_years(player.get("birth_date")) is not None),
                key=lambda item: item["age"],
            ),
        },
        "height_profile": {
            "avg_height_cm": mean(all_heights),
            "median_height_cm": median(all_heights),
            "height_bucket_counts": sorted_bucket_counts(global_height_buckets, ["under_175", "175_179", "180_184", "185_189", "190_plus", "unknown"]),
            "tallest_player": player_brief(max((p for p in players if isinstance(p.get("height_cm"), int)), key=lambda p: int(p["height_cm"]))),
            "shortest_player": player_brief(min((p for p in players if isinstance(p.get("height_cm"), int)), key=lambda p: int(p["height_cm"]))),
        },
        "club_profile": {
            "club_count": len(global_clubs),
            "top_clubs": top_clubs(global_clubs, limit=12),
            "domestic_club_count": None,
            "foreign_club_count": None,
            "domestic_foreign_derivation": "not_derivable_without_canonical_team_country_code",
        },
        "position_group_profiles": build_position_group_profiles(players),
        "observation_rankings": {
            "ranking_type": "roster_observation_ranking",
            "oldest_avg_age_teams": rank_cards(profile_cards, "age_profile.avg_age", True),
            "youngest_avg_age_teams": rank_cards(profile_cards, "age_profile.avg_age", False),
            "tallest_avg_height_teams": rank_cards(profile_cards, "height_profile.avg_height_cm", True),
            "shortest_avg_height_teams": rank_cards(profile_cards, "height_profile.avg_height_cm", False),
        },
        **SAFETY,
    }
    # Flattened ranking metrics are easier to sort without teaching rank_cards nested paths.
    for card in profile_cards:
        card["avg_age"] = card["age_profile"]["avg_age"]
        card["avg_height_cm"] = card["height_profile"]["avg_height_cm"]
    observation["observation_rankings"] = {
        "ranking_type": "roster_observation_ranking",
        "oldest_avg_age_teams": rank_cards(profile_cards, "avg_age", True),
        "youngest_avg_age_teams": rank_cards(profile_cards, "avg_age", False),
        "tallest_avg_height_teams": rank_cards(profile_cards, "avg_height_cm", True),
        "shortest_avg_height_teams": rank_cards(profile_cards, "avg_height_cm", False),
    }
    for card in profile_cards:
        card.pop("avg_age", None)
        card.pop("avg_height_cm", None)
    return observation, profile_cards


def main() -> int:
    for path in [PLAYERS_CSV, PLAYERS_JSON, TEAMS_JSON, TEAM_OBSERVATION_CARDS, WAR_ROOM_UI_PAYLOAD]:
        if not path.exists():
            raise FileNotFoundError(path)
    observation, team_cards = build_layer()
    PROFILE_OBSERVATION.write_text(json.dumps(observation, ensure_ascii=False, indent=2), encoding="utf-8")
    PROFILE_TEAM_CARDS.write_text(json.dumps(team_cards, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "conclusion": "PASS",
        "profile_observation": str(PROFILE_OBSERVATION),
        "profile_team_cards": str(PROFILE_TEAM_CARDS),
        "team_count": observation["team_count"],
        "total_players": observation["total_players"],
        "position_distribution": observation["position_distribution"],
        "avg_age": observation["age_profile"]["avg_age"],
        "avg_height_cm": observation["height_profile"]["avg_height_cm"],
        "club_count": observation["club_profile"]["club_count"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
