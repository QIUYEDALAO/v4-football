#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime
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
DOC = ROOT / "docs/V3_WC_FINAL_26_SQUAD_PACK_PHASE_3_WAR_ROOM_OBSERVATION_LAYER_20260604.md"
STATUS_OUT = ROOT / "data/runtime/status/check_v3_worldcup_final_26_war_room_observation_layer_20260604.json"

SECRET_PATTERNS = [
    r"(?i)(api[_-]?key|token|secret)\s*[:=]\s*['\"][A-Za-z0-9_\-]{16,}",
    r"(?i)x-apisports-key\s*[:=]\s*[A-Za-z0-9_\-]{16,}",
    r"(?i)x-rapidapi-key\s*[:=]\s*[A-Za-z0-9_\-]{16,}",
]

DISALLOWED_STRUCTURED_TEXT = [
    "\"starting_lineup\"",
    "\"starting_players\"",
    "injury_status",
    "suspension_status",
    "recommended_pick",
    "betting_signal",
    "fund_flow",
    "steam",
    "drift",
]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


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


def add(failures: list[str], condition: bool, name: str, detail: Any = "") -> None:
    if not condition:
        failures.append(f"{name}:{detail}" if detail != "" else name)


def main() -> int:
    failures: list[str] = []
    source_files = [PLAYERS_JSON, TEAMS_JSON, SUMMARY_JSON]
    output_files = [ROSTER_INDEX_JSON, TEAM_CARDS_JSON, OBS_SUMMARY_JSON]
    for path in source_files:
        add(failures, path.exists(), "source_file_missing", path.relative_to(ROOT))
    for path in output_files:
        add(failures, path.exists(), "output_file_missing", path.relative_to(ROOT))
    if failures:
        print(json.dumps({"conclusion": "BLOCKER", "failures": failures}, ensure_ascii=False, indent=2))
        return 2

    players = load_json(PLAYERS_JSON)
    teams = load_json(TEAMS_JSON)
    source_summary = load_json(SUMMARY_JSON)
    roster_index = load_json(ROSTER_INDEX_JSON)
    team_cards = load_json(TEAM_CARDS_JSON)
    observation_summary = load_json(OBS_SUMMARY_JSON)

    add(failures, source_summary.get("team_count") == 48, "source_team_count_not_48", source_summary.get("team_count"))
    add(failures, len(players) == 1248, "source_total_players_not_1248", len(players))
    add(failures, sum(1 for t in teams if t.get("head_coach")) == 48, "source_coach_count_not_48")
    add(failures, len(roster_index) == 48, "roster_index_team_count_not_48", len(roster_index))
    add(failures, len(team_cards) == 48, "team_cards_count_not_48", len(team_cards))
    add(failures, observation_summary.get("team_count") == 48, "summary_team_count_not_48", observation_summary.get("team_count"))
    add(failures, observation_summary.get("total_players") == 1248, "summary_total_players_not_1248", observation_summary.get("total_players"))
    add(failures, observation_summary.get("coach_count") == 48, "summary_coach_count_not_48", observation_summary.get("coach_count"))
    add(failures, observation_summary.get("teams_with_26_players") == 48, "summary_teams_with_26_not_48", observation_summary.get("teams_with_26_players"))

    for item in roster_index:
        team = item.get("team")
        add(failures, bool(item.get("team_slug")), "roster_team_slug_missing", team)
        add(failures, item.get("player_count") == 26, "roster_player_count_not_26", team)
        counts = item.get("position_counts") if isinstance(item.get("position_counts"), dict) else {}
        add(failures, sum(int(counts.get(k) or 0) for k in ["GK", "DF", "MF", "FW"]) == 26, "roster_position_count_sum_not_26", team)
        add(failures, len(item.get("roster_player_ids") or []) == 26, "roster_player_ids_not_26", team)
        for field, expected in {
            "is_final_26": True,
            "is_official_fifa": True,
            "observation_only": True,
            "betting_recommendation": False,
            "affects_v4": False,
        }.items():
            add(failures, item.get(field) is expected, f"roster_{field}_unexpected", team)

    for card in team_cards:
        team = card.get("team")
        add(failures, bool(card.get("team_slug")), "card_team_slug_missing", team)
        add(failures, card.get("player_count") == 26, "card_player_count_not_26", team)
        add(failures, sum(int(card.get(k) or 0) for k in ["gk_count", "df_count", "mf_count", "fw_count"]) == 26, "card_position_count_sum_not_26", team)
        for field, expected in {
            "observation_only": True,
            "no_starting_xi": True,
            "no_injury_judgment": True,
            "betting_recommendation": False,
            "affects_v4": False,
        }.items():
            add(failures, card.get(field) is expected, f"card_{field}_unexpected", team)
        for metric in ["avg_age", "median_age", "avg_height_cm", "min_height_cm", "max_height_cm", "club_count"]:
            add(failures, card.get(metric) is not None, f"card_metric_missing_{metric}", team)

    for field, expected in {
        "observation_only": True,
        "is_final_26": True,
        "is_official_fifa": True,
        "no_starting_xi": True,
        "no_injury_judgment": True,
        "betting_recommendation": False,
        "affects_v4": False,
    }.items():
        add(failures, observation_summary.get(field) is expected, f"summary_{field}_unexpected", observation_summary.get(field))

    structured_text = "\n".join(path.read_text(encoding="utf-8", errors="ignore").lower() for path in output_files)
    for token in DISALLOWED_STRUCTURED_TEXT:
        add(failures, token not in structured_text, "disallowed_structured_text", token)
    relevant_runtime_tracked = [x for x in git_ls_files(ROOT / "data/runtime") if "final_26" in x or "squad" in x]
    add(failures, not relevant_runtime_tracked, "runtime_squad_output_tracked", relevant_runtime_tracked[:5])
    secrets = secret_hits(source_files + output_files + [DOC, ROOT / "tools/build_v3_worldcup_final_26_war_room_observation_layer.py", Path(__file__).resolve()])
    add(failures, not secrets, "secret_literal_hits", secrets)

    out = {
        "generated_at": datetime.now().isoformat(),
        "conclusion": "PASS" if not failures else "BLOCKER",
        "failures": failures,
        "team_count": observation_summary.get("team_count"),
        "total_players": observation_summary.get("total_players"),
        "coach_count": observation_summary.get("coach_count"),
        "global_position_distribution": observation_summary.get("global_position_distribution"),
        "avg_age_global": observation_summary.get("avg_age_global"),
        "avg_height_global": observation_summary.get("avg_height_global"),
        "club_count_global": observation_summary.get("club_count_global"),
        "runtime_relevant_tracked": relevant_runtime_tracked,
        "secret_hits": secrets,
    }
    STATUS_OUT.parent.mkdir(parents=True, exist_ok=True)
    STATUS_OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
