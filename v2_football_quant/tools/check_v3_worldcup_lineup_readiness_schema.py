#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data/manual_sources/v3_worldcup/squads/fifa_final_26/processed"
BUILDER = ROOT / "tools/build_v3_worldcup_lineup_readiness_schema.py"
SCHEMA = BASE / "v3_wc2026_lineup_readiness_schema.json"
TEAM_STATUS = BASE / "v3_wc2026_lineup_readiness_team_status.json"
PLAYERS_JSON = BASE / "v3_wc2026_final_26_players.json"
TEAMS_JSON = BASE / "v3_wc2026_final_26_teams.json"
SUMMARY_JSON = BASE / "v3_wc2026_final_26_summary.json"
PROFILE_OBSERVATION = BASE / "v3_wc2026_final_26_squad_profile_observation.json"
TACTICAL_PROFILE = ROOT / "data/v3_worldcup/tactical_profile/v3_worldcup_tactical_profile_layer_20260604.json"
DOC = ROOT / "docs/V3_WC_LINEUP_READINESS_SCHEMA_PACK_PHASE_1_20260604.md"
STATUS_OUT = ROOT / "data/runtime/status/check_v3_worldcup_lineup_readiness_schema_20260604.json"

SAFETY_EXPECTED = {
    "observation_only": True,
    "no_starting_xi_generated": True,
    "no_prediction": True,
    "no_injury_judgment": True,
    "betting_recommendation": False,
    "affects_v4": False,
}
SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|token|secret)\s*[:=]\s*['\"][A-Za-z0-9_\-]{16,}"),
    re.compile(r"(?i)x-apisports-key\s*[:=]\s*[A-Za-z0-9_\-]{16,}"),
    re.compile(r"(?i)x-rapidapi-key\s*[:=]\s*[A-Za-z0-9_\-]{16,}"),
]
DISALLOWED_GENERATED_KEYS = {
    "confirmed_lineup",
    "confirmed_formation",
    "selected_eleven",
    "injury_status",
    "suspension_status",
    "recommendation_output",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def add(failures: list[str], condition: bool, name: str, detail: Any = "") -> None:
    if not condition:
        failures.append(f"{name}:{detail}" if detail != "" else name)


def check_safety(failures: list[str], node: dict[str, Any], prefix: str) -> None:
    for key, expected in SAFETY_EXPECTED.items():
        add(failures, node.get(key) is expected, f"{prefix}_{key}_unexpected", node.get(key))


def secret_hits(paths: list[Path]) -> list[str]:
    hits: list[str] = []
    for path in paths:
        if not path.exists() or not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if any(pattern.search(text) for pattern in SECRET_PATTERNS):
            hits.append(str(path.relative_to(ROOT)))
    return hits


def staged_files() -> list[str]:
    result = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=ROOT.parent, text=True, capture_output=True, check=False)
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def main() -> int:
    failures: list[str] = []
    run = subprocess.run([sys.executable, str(BUILDER)], cwd=ROOT, text=True, capture_output=True, check=False)
    add(failures, run.returncode == 0, "builder_runs", run.stderr or run.stdout[-500:])
    for path in [PLAYERS_JSON, TEAMS_JSON, SUMMARY_JSON, PROFILE_OBSERVATION, TACTICAL_PROFILE, SCHEMA, TEAM_STATUS, DOC]:
        add(failures, path.exists(), "required_file_missing", path.relative_to(ROOT))
    if failures:
        print(json.dumps({"conclusion": "BLOCKER", "failures": failures}, ensure_ascii=False, indent=2))
        return 2

    players = load_json(PLAYERS_JSON)
    teams = load_json(TEAMS_JSON)
    schema = load_json(SCHEMA)
    status = load_json(TEAM_STATUS)
    team_rows = status.get("teams") if isinstance(status.get("teams"), list) else []
    add(failures, len(teams) == 48, "source_team_count_not_48", len(teams))
    add(failures, len(players) == 1248, "source_total_players_not_1248", len(players))
    add(failures, status.get("team_count") == 48 and len(team_rows) == 48, "team_status_count_not_48", {"top": status.get("team_count"), "rows": len(team_rows)})
    add(failures, status.get("total_players") == 1248, "status_total_players_not_1248", status.get("total_players"))
    add(failures, status.get("starting_xi_status") == "NOT_AVAILABLE", "top_starting_xi_status_unexpected", status.get("starting_xi_status"))
    add(failures, status.get("matchday_lineup_status") == "WAIT_OFFICIAL_LINEUP", "top_matchday_lineup_status_unexpected", status.get("matchday_lineup_status"))
    add(failures, status.get("formation_status") == "HISTORICAL_OBSERVATION_ONLY", "top_formation_status_unexpected", status.get("formation_status"))
    check_safety(failures, status.get("safety") if isinstance(status.get("safety"), dict) else {}, "top_safety")
    check_safety(failures, schema.get("safety") if isinstance(schema.get("safety"), dict) else {}, "schema_safety")
    for row in team_rows:
        team = row.get("team")
        add(failures, row.get("final_26_player_count") == 26, "team_final_26_player_count_not_26", team)
        add(failures, row.get("starting_xi_status") == "NOT_AVAILABLE", "team_starting_xi_status_unexpected", team)
        add(failures, row.get("starting_xi_source") == "NONE", "team_starting_xi_source_unexpected", team)
        add(failures, row.get("starting_xi_players") == [], "team_starting_xi_players_not_empty", team)
        add(failures, row.get("predicted_xi_generated") is False, "team_predicted_xi_generated_unexpected", team)
        add(failures, row.get("matchday_lineup_status") == "WAIT_OFFICIAL_LINEUP", "team_matchday_lineup_status_unexpected", team)
        add(failures, row.get("formation_status") == "HISTORICAL_OBSERVATION_ONLY", "team_formation_status_unexpected", team)
        check_safety(failures, row, f"team_safety_{team}")
    text = json.dumps({"schema": schema, "status": status}, ensure_ascii=False).lower()
    for key in DISALLOWED_GENERATED_KEYS:
        add(failures, f'"{key}"' not in text, "disallowed_generated_key", key)
    staged = staged_files()
    runtime_staged = [path for path in staged if "/data/runtime/" in path or path.endswith(".log")]
    v4_staged = [path for path in staged if "/V4_" in path or "/v4_" in path or "/check_v4" in path or "/build_v4" in path or "/run_v4" in path]
    secrets = secret_hits([SCHEMA, TEAM_STATUS, DOC, BUILDER, Path(__file__).resolve()])
    add(failures, not runtime_staged, "runtime_staged", runtime_staged)
    add(failures, not v4_staged, "v4_staged", v4_staged)
    add(failures, not secrets, "secret_literal_hits", secrets)
    out = {
        "generated_at": datetime.now().isoformat(),
        "conclusion": "PASS" if not failures else "BLOCKER",
        "failures": failures,
        "team_count": status.get("team_count"),
        "total_players": status.get("total_players"),
        "starting_xi_status": status.get("starting_xi_status"),
        "matchday_lineup_status": status.get("matchday_lineup_status"),
        "formation_status": status.get("formation_status"),
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
