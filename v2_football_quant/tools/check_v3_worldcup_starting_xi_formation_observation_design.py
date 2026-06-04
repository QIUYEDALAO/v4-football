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
PLAYERS_CSV = BASE / "v3_wc2026_final_26_players.csv"
PLAYERS_JSON = BASE / "v3_wc2026_final_26_players.json"
TEAMS_JSON = BASE / "v3_wc2026_final_26_teams.json"
PROFILE_OBSERVATION = BASE / "v3_wc2026_final_26_squad_profile_observation.json"
PROFILE_TEAM_CARDS = BASE / "v3_wc2026_final_26_squad_profile_team_cards.json"
SCHEMA = BASE / "v3_wc2026_starting_xi_formation_observation_schema.json"
TACTICAL_PROFILE = ROOT / "data/v3_worldcup/tactical_profile/v3_worldcup_tactical_profile_layer_20260604.json"
DOC = ROOT / "docs/V3_WC_STARTING_XI_FORMATION_OBSERVATION_PACK_PHASE_1_SOURCE_AND_SCHEMA_DESIGN_FREEZE_20260604.md"
STATUS_OUT = ROOT / "data/runtime/status/check_v3_worldcup_starting_xi_formation_observation_design_20260604.json"

EXPECTED_POSITION_COUNTS = {"GK": 145, "DF": 421, "MF": 371, "FW": 311}
SAFETY_EXPECTED = {
    "observation_only": True,
    "no_starting_xi_generated": True,
    "no_injury_judgment": True,
    "no_prediction": True,
    "betting_recommendation": False,
    "affects_v4": False,
}
SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|token|secret)\s*[:=]\s*['\"][A-Za-z0-9_\-]{16,}"),
    re.compile(r"(?i)x-apisports-key\s*[:=]\s*[A-Za-z0-9_\-]{16,}"),
    re.compile(r"(?i)x-rapidapi-key\s*[:=]\s*[A-Za-z0-9_\-]{16,}"),
]
PROHIBITED_GENERATED_KEYS = {
    "starting_eleven",
    "starting_eleven_players",
    "lineup_prediction",
    "injury_status_assessment",
    "suspension_status_assessment",
    "match_prediction",
    "recommendation_output",
    "wagering_signal",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def add(failures: list[str], condition: bool, name: str, detail: Any = "") -> None:
    if not condition:
        failures.append(f"{name}:{detail}" if detail != "" else name)


def git(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=ROOT.parent, text=True, capture_output=True, check=False)


def secret_hits(paths: list[Path]) -> list[str]:
    hits: list[str] = []
    for path in paths:
        if not path.exists() or not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if any(pattern.search(text) for pattern in SECRET_PATTERNS):
            hits.append(str(path.relative_to(ROOT)))
    return hits


def scan_generated_outputs_for_prohibited_keys() -> list[str]:
    hits: list[str] = []
    for path in [SCHEMA]:
        obj = load_json(path)
        text = json.dumps(obj.get("team_observation_schema", {}), ensure_ascii=False).lower()
        text += json.dumps(obj.get("player_role_pool_schema", {}), ensure_ascii=False).lower()
        text += json.dumps(obj.get("formation_observation_schema", {}), ensure_ascii=False).lower()
        for key in PROHIBITED_GENERATED_KEYS:
            if f'"{key}"' in text:
                hits.append(f"{path.relative_to(ROOT)}:{key}")
    return hits


def main() -> int:
    failures: list[str] = []
    for path in [PLAYERS_CSV, PLAYERS_JSON, TEAMS_JSON, PROFILE_OBSERVATION, PROFILE_TEAM_CARDS, TACTICAL_PROFILE]:
        add(failures, path.exists(), "source_missing", path.relative_to(ROOT))
    add(failures, SCHEMA.exists(), "schema_missing", SCHEMA.relative_to(ROOT))
    add(failures, DOC.exists(), "doc_missing", DOC.relative_to(ROOT))
    if failures:
        print(json.dumps({"conclusion": "BLOCKER", "failures": failures}, ensure_ascii=False, indent=2))
        return 2

    players = load_json(PLAYERS_JSON)
    teams = load_json(TEAMS_JSON)
    profile = load_json(PROFILE_OBSERVATION)
    schema = load_json(SCHEMA)
    add(failures, len(teams) == 48, "team_count_not_48", len(teams))
    add(failures, len(players) == 1248, "total_players_not_1248", len(players))
    add(failures, profile.get("position_distribution") == EXPECTED_POSITION_COUNTS, "position_distribution_unexpected", profile.get("position_distribution"))
    add(failures, schema.get("pack_name") == "V3_WC_STARTING_XI_FORMATION_OBSERVATION_PACK", "pack_name_unexpected", schema.get("pack_name"))
    source_strategy = schema.get("source_strategy") if isinstance(schema.get("source_strategy"), dict) else {}
    for key in ["final_26_canonical_source", "historical_formation_source", "matchday_lineup_future_source", "tactical_profile_source", "source_trust_level", "source_status"]:
        add(failures, key in source_strategy, "source_strategy_field_missing", key)
    for section in ["team_observation_schema", "player_role_pool_schema", "formation_observation_schema"]:
        add(failures, isinstance(schema.get(section), dict), "schema_section_missing", section)
    safety = schema.get("safety") if isinstance(schema.get("safety"), dict) else {}
    for key, expected in SAFETY_EXPECTED.items():
        add(failures, safety.get(key) is expected, "safety_field_unexpected", {key: safety.get(key)})
    team_schema = schema.get("team_observation_schema") if isinstance(schema.get("team_observation_schema"), dict) else {}
    add(failures, team_schema.get("starting_xi_status") == "NOT_GENERATED_SCHEMA_ONLY", "starting_xi_status_unexpected", team_schema.get("starting_xi_status"))
    add(failures, team_schema.get("matchday_lineup_status") == "NOT_AVAILABLE_PHASE_1", "matchday_lineup_status_unexpected", team_schema.get("matchday_lineup_status"))
    add(failures, team_schema.get("likely_role_pool_status") == "ROLE_POOL_OBSERVATION_NOT_LINEUP", "role_pool_status_unexpected", team_schema.get("likely_role_pool_status"))
    player_schema = schema.get("player_role_pool_schema") if isinstance(schema.get("player_role_pool_schema"), dict) else {}
    add(failures, player_schema.get("not_starting_xi") is True, "player_role_pool_not_starting_xi_missing", player_schema.get("not_starting_xi"))
    formation_schema = schema.get("formation_observation_schema") if isinstance(schema.get("formation_observation_schema"), dict) else {}
    add(failures, formation_schema.get("no_prediction") is True, "formation_no_prediction_missing", formation_schema.get("no_prediction"))
    prohibited = scan_generated_outputs_for_prohibited_keys()
    add(failures, not prohibited, "prohibited_generated_key_present", prohibited)

    staged = [line for line in git(["diff", "--cached", "--name-only"]).stdout.splitlines() if line.strip()]
    runtime_staged = [path for path in staged if "/data/runtime/" in path or path.endswith(".log")]
    v4_staged = [path for path in staged if "/V4_" in path or "/v4_" in path or "/check_v4" in path or "/build_v4" in path or "/run_v4" in path]
    final26_staged = [path for path in staged if "final_26" in path and not path.endswith("v3_wc2026_starting_xi_formation_observation_schema.json")]
    add(failures, not runtime_staged, "runtime_staged", runtime_staged)
    add(failures, not v4_staged, "v4_staged", v4_staged)
    add(failures, not final26_staged, "final26_unrelated_staged", final26_staged)
    secrets = secret_hits([SCHEMA, DOC, Path(__file__).resolve()])
    add(failures, not secrets, "secret_literal_hits", secrets)
    out = {
        "generated_at": datetime.now().isoformat(),
        "conclusion": "PASS" if not failures else "BLOCKER",
        "failures": failures,
        "team_count": len(teams),
        "total_players": len(players),
        "position_distribution": profile.get("position_distribution"),
        "schema": str(SCHEMA.relative_to(ROOT)),
        "source_strategy_keys": sorted(source_strategy.keys()),
        "runtime_staged": runtime_staged,
        "secret_hits": secrets,
        "v4_staged": v4_staged,
    }
    STATUS_OUT.parent.mkdir(parents=True, exist_ok=True)
    STATUS_OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
