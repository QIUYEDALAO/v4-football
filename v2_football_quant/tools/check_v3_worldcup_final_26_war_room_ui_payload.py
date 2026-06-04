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
ROSTER_INDEX = BASE / "v3_wc2026_final_26_war_room_roster_index.json"
TEAM_CARDS = BASE / "v3_wc2026_final_26_team_observation_cards.json"
OBS_SUMMARY = BASE / "v3_wc2026_final_26_squad_observation_summary.json"
UI_PAYLOAD = BASE / "v3_wc2026_final_26_war_room_ui_payload.json"
WAR_ROOM_JSON = ROOT / "data/v3_worldcup/war_room/v3_worldcup_wc10_war_room_20260602.json"
DOC = ROOT / "docs/V3_WC_FINAL_26_SQUAD_PACK_PHASE_4_WAR_ROOM_UI_JSON_INTEGRATION_20260604.md"
STATUS_OUT = ROOT / "data/runtime/status/check_v3_worldcup_final_26_war_room_ui_payload_20260604.json"

EXPECTED_POSITION_COUNTS = {"GK": 145, "DF": 421, "MF": 371, "FW": 311}
SECRET_PATTERNS = [
    r"(?i)(api[_-]?key|token|secret)\s*[:=]\s*['\"][A-Za-z0-9_\-]{16,}",
    r"(?i)x-apisports-key\s*[:=]\s*[A-Za-z0-9_\-]{16,}",
    r"(?i)x-rapidapi-key\s*[:=]\s*[A-Za-z0-9_\-]{16,}",
]
DISALLOWED_STRUCTURED_TEXT = [
    "\"starting_lineup\"",
    "\"starting_players\"",
    "\"injury_status\"",
    "\"suspension_status\"",
    "\"recommended_pick\"",
    "\"betting_signal\"",
    "\"fund_flow\"",
    "\"steam\"",
    "\"drift\"",
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


def check_safety(failures: list[str], safety: dict[str, Any], prefix: str) -> None:
    for field, expected in {
        "observation_only": True,
        "no_starting_xi": True,
        "no_injury_judgment": True,
        "betting_recommendation": False,
        "affects_v4": False,
    }.items():
        add(failures, safety.get(field) is expected, f"{prefix}_{field}_unexpected", safety.get(field))


def main() -> int:
    failures: list[str] = []
    for path in [ROSTER_INDEX, TEAM_CARDS, OBS_SUMMARY]:
        add(failures, path.exists(), "source_observation_json_missing", path.relative_to(ROOT))
    add(failures, UI_PAYLOAD.exists(), "ui_payload_missing", UI_PAYLOAD.relative_to(ROOT))
    if failures:
        print(json.dumps({"conclusion": "BLOCKER", "failures": failures}, ensure_ascii=False, indent=2))
        return 2

    payload = load_json(UI_PAYLOAD)
    add(failures, payload.get("module") == "final_26_squad_observation", "module_unexpected", payload.get("module"))
    add(failures, payload.get("team_count") == 48, "team_count_not_48", payload.get("team_count"))
    add(failures, payload.get("total_players") == 1248, "total_players_not_1248", payload.get("total_players"))
    add(failures, payload.get("coach_count") == 48, "coach_count_not_48", payload.get("coach_count"))
    teams = payload.get("teams") if isinstance(payload.get("teams"), list) else []
    add(failures, len(teams) == 48, "teams_length_not_48", len(teams))
    add(failures, payload.get("global_position_distribution") == EXPECTED_POSITION_COUNTS, "global_position_distribution_unexpected", payload.get("global_position_distribution"))
    check_safety(failures, payload.get("safety") if isinstance(payload.get("safety"), dict) else {}, "payload_safety")
    for team in teams:
        team_name = team.get("team")
        add(failures, bool(team.get("team_slug")), "team_slug_missing", team_name)
        add(failures, team.get("player_count") == 26, "team_player_count_not_26", team_name)
        counts = team.get("position_counts") if isinstance(team.get("position_counts"), dict) else {}
        add(failures, sum(int(counts.get(k) or 0) for k in ["GK", "DF", "MF", "FW"]) == 26, "team_position_count_sum_not_26", team_name)
        add(failures, len(team.get("roster_ref", {}).get("player_ids") or []) == 26, "team_roster_ref_not_26", team_name)
        check_safety(failures, team.get("safety") if isinstance(team.get("safety"), dict) else {}, f"team_safety_{team_name}")

    structured_text = UI_PAYLOAD.read_text(encoding="utf-8", errors="ignore").lower()
    if WAR_ROOM_JSON.exists():
        war = load_json(WAR_ROOM_JSON)
        node = war.get("final_26_squad_observation")
        add(failures, isinstance(node, dict), "war_room_final_26_node_missing")
        if isinstance(node, dict):
            add(failures, node.get("module") == "final_26_squad_observation", "war_room_module_unexpected", node.get("module"))
            add(failures, node.get("team_count") == 48, "war_room_team_count_not_48", node.get("team_count"))
            check_safety(failures, node.get("safety") if isinstance(node.get("safety"), dict) else {}, "war_room_safety")
        structured_text += "\n" + json.dumps(node or {}, ensure_ascii=False).lower()
    for token in DISALLOWED_STRUCTURED_TEXT:
        add(failures, token not in structured_text, "disallowed_structured_text", token)

    relevant_runtime = [x for x in git_ls_files(ROOT / "data/runtime") if "final_26" in x or "squad" in x]
    add(failures, not relevant_runtime, "runtime_squad_output_tracked", relevant_runtime[:5])
    secrets = secret_hits([UI_PAYLOAD, DOC, ROOT / "tools/build_v3_worldcup_final_26_war_room_ui_payload.py", Path(__file__).resolve()])
    add(failures, not secrets, "secret_literal_hits", secrets)
    out = {
        "generated_at": datetime.now().isoformat(),
        "conclusion": "PASS" if not failures else "BLOCKER",
        "failures": failures,
        "module": payload.get("module"),
        "team_count": payload.get("team_count"),
        "total_players": payload.get("total_players"),
        "coach_count": payload.get("coach_count"),
        "global_position_distribution": payload.get("global_position_distribution"),
        "teams_length": len(teams),
        "runtime_relevant_tracked": relevant_runtime,
        "secret_hits": secrets,
    }
    STATUS_OUT.parent.mkdir(parents=True, exist_ok=True)
    STATUS_OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
