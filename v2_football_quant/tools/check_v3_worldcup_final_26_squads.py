#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data/manual_sources/v3_worldcup/squads/fifa_final_26"
PROCESSED = BASE / "processed"
REPORTS = BASE / "reports"
PLAYERS_CSV = PROCESSED / "v3_wc2026_final_26_players.csv"
PLAYERS_JSON = PROCESSED / "v3_wc2026_final_26_players.json"
TEAMS_JSON = PROCESSED / "v3_wc2026_final_26_teams.json"
SUMMARY_JSON = PROCESSED / "v3_wc2026_final_26_summary.json"
REPORT_MD = REPORTS / "V3_WC_FINAL_26_SQUAD_INGEST_REPORT.md"
STATUS_OUT = ROOT / "data/runtime/status/check_v3_worldcup_final_26_squads_20260604.json"

PLAYER_REQUIRED_FIELDS = [
    "tournament",
    "source",
    "team",
    "team_slug",
    "player_id",
    "squad_number",
    "position",
    "first_name",
    "last_name",
    "full_name",
    "shirt_name",
    "birth_date",
    "club",
    "height_cm",
    "head_coach",
    "is_final_26",
    "is_official_fifa",
    "observation_only",
    "betting_recommendation",
    "affects_v4",
]

TEAM_REQUIRED_FIELDS = [
    "tournament",
    "source",
    "team",
    "team_slug",
    "head_coach",
    "player_count",
    "gk_count",
    "df_count",
    "mf_count",
    "fw_count",
    "is_final_26",
    "is_official_fifa",
    "observation_only",
    "betting_recommendation",
    "affects_v4",
]

SUMMARY_REQUIRED_FIELDS = [
    "team_count",
    "total_players",
    "expected_team_count",
    "expected_total_players",
    "teams_with_26_players",
    "teams_not_26_players",
    "duplicate_player_id_count",
    "missing_required_field_counts",
    "position_distribution",
    "height_parse_warn_count",
    "birth_date_parse_warn_count",
    "source_docx",
    "observation_only",
    "betting_recommendation",
    "affects_v4",
]

SECRET_PATTERNS = [
    r"(?i)(api[_-]?key|token|secret)\s*[:=]\s*['\"][A-Za-z0-9_\-]{16,}",
    r"(?i)x-apisports-key\s*[:=]\s*[A-Za-z0-9_\-]{16,}",
    r"(?i)x-rapidapi-key\s*[:=]\s*[A-Za-z0-9_\-]{16,}",
]

DISALLOWED_TEXT = [
    "starting xi",
    "injury judgment",
    "suspension judgment",
    "steam",
    "drift",
    "fund_flow",
    "fund flow",
    "betting signal",
]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        return [dict(r) for r in csv.DictReader(f)]


def git_ls_files(path: Path) -> list[str]:
    rel = str(path.relative_to(ROOT))
    result = subprocess.run(["git", "ls-files", rel], cwd=ROOT, text=True, capture_output=True, check=False)
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def valid_iso_date(value: str) -> bool:
    return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(value or "")))


def secret_hits(paths: list[Path]) -> list[str]:
    hits: list[str] = []
    for path in paths:
        if not path.exists() or not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in SECRET_PATTERNS:
            if re.search(pattern, text):
                hits.append(str(path.relative_to(ROOT)))
                break
    return hits


def main() -> int:
    failures: list[str] = []
    warnings: list[str] = []
    required_files = [PLAYERS_CSV, PLAYERS_JSON, TEAMS_JSON, SUMMARY_JSON, REPORT_MD]
    for path in required_files:
        if not path.exists():
            failures.append(f"file_missing:{path.relative_to(ROOT)}")
    if failures:
        print(json.dumps({"conclusion": "BLOCKER", "failures": failures}, ensure_ascii=False, indent=2))
        return 2

    players_csv = load_csv(PLAYERS_CSV)
    players = load_json(PLAYERS_JSON)
    teams = load_json(TEAMS_JSON)
    summary = load_json(SUMMARY_JSON)

    if len(players_csv) != len(players):
        failures.append("players_csv_json_count_mismatch")
    for field in PLAYER_REQUIRED_FIELDS:
        if players_csv and field not in players_csv[0]:
            failures.append(f"player_schema_field_missing:{field}")
    for field in TEAM_REQUIRED_FIELDS:
        if teams and field not in teams[0]:
            failures.append(f"team_schema_field_missing:{field}")
    for field in SUMMARY_REQUIRED_FIELDS:
        if field not in summary:
            failures.append(f"summary_schema_field_missing:{field}")

    if summary.get("team_count") != 48:
        failures.append(f"team_count_mismatch:{summary.get('team_count')}")
    if summary.get("total_players") != 1248:
        failures.append(f"total_players_mismatch:{summary.get('total_players')}")
    if summary.get("teams_with_26_players") != 48 or summary.get("teams_not_26_players"):
        failures.append("team_26_count_mismatch")
    if sum(1 for t in teams if t.get("head_coach")) != 48:
        failures.append("coach_count_mismatch")
    ids = [p.get("player_id") for p in players]
    if len(ids) != len(set(ids)):
        failures.append("player_id_not_unique")
    allowed_positions = {"GK", "DF", "MF", "FW"}
    bad_positions = sorted({p.get("position") for p in players if p.get("position") not in allowed_positions})
    if bad_positions:
        failures.append(f"bad_positions:{bad_positions}")

    bad_birth_dates = [p.get("player_id") for p in players if not valid_iso_date(str(p.get("birth_date") or ""))]
    bad_heights = [p.get("player_id") for p in players if not isinstance(p.get("height_cm"), int)]
    if bad_birth_dates:
        warnings.append(f"WARN_ONLY_birth_date_parse:{len(bad_birth_dates)}")
    if bad_heights:
        warnings.append(f"WARN_ONLY_height_parse:{len(bad_heights)}")
    if len(bad_birth_dates) > 5:
        failures.append(f"birth_date_parse_excessive:{len(bad_birth_dates)}")
    if len(bad_heights) > 5:
        failures.append(f"height_parse_excessive:{len(bad_heights)}")

    for field in ["squad_number", "club", "head_coach"]:
        missing = [p.get("player_id") for p in players if p.get(field) in {"", None}]
        if missing:
            failures.append(f"player_field_missing:{field}:{len(missing)}")
    for team in teams:
        if team.get("player_count") != 26:
            failures.append(f"team_not_26:{team.get('team')}")
        if not team.get("head_coach"):
            failures.append(f"team_head_coach_missing:{team.get('team')}")

    for record in list(players) + list(teams) + [summary]:
        for field, expected in {
            "is_final_26": True,
            "is_official_fifa": True,
            "observation_only": True,
            "betting_recommendation": False,
            "affects_v4": False,
        }.items():
            if field in record and record.get(field) is not expected:
                failures.append(f"{field}_unexpected")
                break

    structured_files = [PLAYERS_CSV, PLAYERS_JSON, TEAMS_JSON, SUMMARY_JSON]
    combined_text = "\n".join(path.read_text(encoding="utf-8", errors="ignore").lower() for path in structured_files)
    for token in DISALLOWED_TEXT:
        if token in combined_text:
            failures.append(f"disallowed_text_present:{token}")
    tracked_runtime = git_ls_files(ROOT / "data/runtime")
    tracked_runtime_relevant = [x for x in tracked_runtime if "final_26" in x or "squad" in x]
    if tracked_runtime_relevant:
        failures.append(f"runtime_squad_output_tracked:{tracked_runtime_relevant[:5]}")

    secret_literal_hits = secret_hits(required_files + [ROOT / "tools/build_v3_worldcup_final_26_squads.py", Path(__file__).resolve()])
    if secret_literal_hits:
        failures.append(f"secret_literal_hits:{secret_literal_hits}")

    out = {
        "generated_at": datetime.now().isoformat(),
        "conclusion": "PASS" if not failures else "BLOCKER",
        "failures": failures,
        "warnings": warnings,
        "team_count": summary.get("team_count"),
        "total_players": summary.get("total_players"),
        "coach_count": sum(1 for t in teams if t.get("head_coach")),
        "duplicate_player_id_count": summary.get("duplicate_player_id_count"),
        "position_distribution": summary.get("position_distribution"),
        "height_parse_warn_count": summary.get("height_parse_warn_count"),
        "birth_date_parse_warn_count": summary.get("birth_date_parse_warn_count"),
        "secret_hits": secret_literal_hits,
        "runtime_relevant_tracked": tracked_runtime_relevant,
    }
    STATUS_OUT.parent.mkdir(parents=True, exist_ok=True)
    STATUS_OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
