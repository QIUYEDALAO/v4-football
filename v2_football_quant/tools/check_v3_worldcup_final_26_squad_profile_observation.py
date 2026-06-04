#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data/manual_sources/v3_worldcup/squads/fifa_final_26/processed"
PLAYERS_JSON = BASE / "v3_wc2026_final_26_players.json"
TEAMS_JSON = BASE / "v3_wc2026_final_26_teams.json"
TEAM_OBSERVATION_CARDS = BASE / "v3_wc2026_final_26_team_observation_cards.json"
WAR_ROOM_UI_PAYLOAD = BASE / "v3_wc2026_final_26_war_room_ui_payload.json"
PROFILE_OBSERVATION = BASE / "v3_wc2026_final_26_squad_profile_observation.json"
PROFILE_TEAM_CARDS = BASE / "v3_wc2026_final_26_squad_profile_team_cards.json"
DOC = ROOT / "docs/V3_WC_FINAL_26_SQUAD_PACK_PHASE_5_SQUAD_PROFILE_DERIVED_LAYER_20260604.md"
STATUS_OUT = ROOT / "data/runtime/status/check_v3_worldcup_final_26_squad_profile_observation_20260604.json"

POSITIONS = ["GK", "DF", "MF", "FW"]
EXPECTED_POSITION_COUNTS = {"GK": 145, "DF": 421, "MF": 371, "FW": 311}
SAFETY_EXPECTED = {
    "observation_only": True,
    "no_starting_xi": True,
    "no_injury_judgment": True,
    "no_prediction": True,
    "betting_recommendation": False,
    "affects_v4": False,
}
PROFILE_FIELDS = [
    "age_profile",
    "height_profile",
    "club_profile",
    "position_group_profiles",
    "observation_rankings",
]
DISALLOWED_TEXT = [
    "starting lineup",
    "starting_lineup",
    "starting_players",
    "injury_status",
    "suspension_status",
    "strength ranking",
    "strength_ranking",
    "prediction ranking",
    "prediction_ranking",
    "betting signal",
    "betting_signal",
    "recommended_pick",
    "recommendation_ranking",
    "fund_flow",
    "steam",
    "drift",
]
SECRET_PATTERNS = [
    r"(?i)(api[_-]?key|token|secret)\s*[:=]\s*['\"][A-Za-z0-9_\-]{16,}",
    r"(?i)x-apisports-key\s*[:=]\s*[A-Za-z0-9_\-]{16,}",
    r"(?i)x-rapidapi-key\s*[:=]\s*[A-Za-z0-9_\-]{16,}",
]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def add(failures: list[str], condition: bool, name: str, detail: Any = "") -> None:
    if not condition:
        failures.append(f"{name}:{detail}" if detail != "" else name)


def check_safety(failures: list[str], node: dict[str, Any], prefix: str) -> None:
    for key, expected in SAFETY_EXPECTED.items():
        add(failures, node.get(key) is expected, f"{prefix}_{key}_unexpected", node.get(key))


def git_ls_files(path: Path) -> list[str]:
    rel = str(path.relative_to(ROOT))
    result = subprocess.run(["git", "ls-files", rel], cwd=ROOT, text=True, capture_output=True, check=False)
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def secret_hits(paths: list[Path]) -> list[str]:
    hits: list[str] = []
    for path in paths:
        if not path.exists() or not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if any(re.search(pattern, text) for pattern in SECRET_PATTERNS):
            hits.append(str(path.relative_to(ROOT)))
    return hits


def nested(node: dict[str, Any], path: str) -> Any:
    current: Any = node
    for part in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def check_profile_fields(failures: list[str], node: dict[str, Any], prefix: str, *, require_rankings: bool) -> None:
    fields = PROFILE_FIELDS if require_rankings else [field for field in PROFILE_FIELDS if field != "observation_rankings"]
    for field in fields:
        add(failures, isinstance(node.get(field), dict), f"{prefix}_{field}_missing")
    age = node.get("age_profile") if isinstance(node.get("age_profile"), dict) else {}
    height = node.get("height_profile") if isinstance(node.get("height_profile"), dict) else {}
    club = node.get("club_profile") if isinstance(node.get("club_profile"), dict) else {}
    for field in ["avg_age", "median_age", "age_bucket_counts", "youngest_player", "oldest_player"]:
        add(failures, field in age, f"{prefix}_age_{field}_missing")
    for field in ["avg_height_cm", "median_height_cm", "height_bucket_counts", "tallest_player", "shortest_player"]:
        add(failures, field in height, f"{prefix}_height_{field}_missing")
    for field in ["club_count", "top_clubs", "domestic_club_count", "foreign_club_count"]:
        add(failures, field in club, f"{prefix}_club_{field}_missing")
    groups = node.get("position_group_profiles") if isinstance(node.get("position_group_profiles"), dict) else {}
    for position in POSITIONS:
        group = groups.get(position) if isinstance(groups.get(position), dict) else {}
        add(failures, "avg_age" in group, f"{prefix}_{position}_avg_age_missing")
        add(failures, "avg_height_cm" in group, f"{prefix}_{position}_avg_height_missing")


def main() -> int:
    failures: list[str] = []
    for path in [PLAYERS_JSON, TEAMS_JSON, TEAM_OBSERVATION_CARDS, WAR_ROOM_UI_PAYLOAD]:
        add(failures, path.exists(), "source_missing", path.relative_to(ROOT))
    for path in [PROFILE_OBSERVATION, PROFILE_TEAM_CARDS]:
        add(failures, path.exists(), "derived_output_missing", path.relative_to(ROOT))
    if failures:
        print(json.dumps({"conclusion": "BLOCKER", "failures": failures}, ensure_ascii=False, indent=2))
        return 2

    players = load_json(PLAYERS_JSON)
    observation = load_json(PROFILE_OBSERVATION)
    team_cards = load_json(PROFILE_TEAM_CARDS)
    add(failures, observation.get("module") == "final_26_squad_profile_observation", "module_unexpected", observation.get("module"))
    add(failures, observation.get("team_count") == 48, "team_count_not_48", observation.get("team_count"))
    add(failures, observation.get("total_players") == 1248, "total_players_not_1248", observation.get("total_players"))
    add(failures, len(team_cards) == 48, "team_cards_length_not_48", len(team_cards))
    add(failures, observation.get("position_distribution") == EXPECTED_POSITION_COUNTS, "position_distribution_unexpected", observation.get("position_distribution"))
    check_profile_fields(failures, observation, "global", require_rankings=True)
    check_safety(failures, observation, "global")

    rankings = observation.get("observation_rankings") if isinstance(observation.get("observation_rankings"), dict) else {}
    add(failures, rankings.get("ranking_type") == "roster_observation_ranking", "ranking_type_unexpected", rankings.get("ranking_type"))
    for field in ["oldest_avg_age_teams", "youngest_avg_age_teams", "tallest_avg_height_teams", "shortest_avg_height_teams"]:
        add(failures, isinstance(rankings.get(field), list) and bool(rankings.get(field)), "ranking_missing", field)

    player_counts_by_team: dict[str, int] = {}
    for player in players:
        slug = str(player.get("team_slug") or "")
        player_counts_by_team[slug] = player_counts_by_team.get(slug, 0) + 1
    for card in team_cards:
        team = card.get("team")
        slug = str(card.get("team_slug") or "")
        add(failures, card.get("player_count") == 26, "team_player_count_not_26", team)
        add(failures, player_counts_by_team.get(slug) == 26, "source_team_player_count_not_26", team)
        add(failures, card.get("position_distribution") and sum(int(card["position_distribution"].get(p) or 0) for p in POSITIONS) == 26, "team_position_sum_not_26", team)
        check_profile_fields(failures, card, f"team_{team}", require_rankings=False)
        check_safety(failures, card, f"team_{team}")

    text = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore").lower()
        for path in [PROFILE_OBSERVATION, PROFILE_TEAM_CARDS, DOC]
        if path.exists()
    )
    for token in DISALLOWED_TEXT:
        add(failures, token not in text, "disallowed_text", token)
    relevant_runtime = [item for item in git_ls_files(ROOT / "data/runtime") if "final_26" in item or "squad" in item]
    add(failures, not relevant_runtime, "runtime_squad_output_tracked", relevant_runtime[:5])
    secrets = secret_hits([
        PROFILE_OBSERVATION,
        PROFILE_TEAM_CARDS,
        DOC,
        ROOT / "tools/build_v3_worldcup_final_26_squad_profile_observation.py",
        Path(__file__).resolve(),
    ])
    add(failures, not secrets, "secret_literal_hits", secrets)
    out = {
        "generated_at": datetime.now().isoformat(),
        "conclusion": "PASS" if not failures else "BLOCKER",
        "failures": failures,
        "team_count": observation.get("team_count"),
        "total_players": observation.get("total_players"),
        "position_distribution": observation.get("position_distribution"),
        "avg_age": nested(observation, "age_profile.avg_age"),
        "avg_height_cm": nested(observation, "height_profile.avg_height_cm"),
        "club_count": nested(observation, "club_profile.club_count"),
        "runtime_relevant_tracked": relevant_runtime,
        "secret_hits": secrets,
    }
    STATUS_OUT.parent.mkdir(parents=True, exist_ok=True)
    STATUS_OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
