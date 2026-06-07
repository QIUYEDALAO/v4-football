#!/usr/bin/env python3
"""Check V4 replay feature enriched dataset."""
from __future__ import annotations

import csv
import json
import re
import subprocess
import sys
from collections import defaultdict, deque
from pathlib import Path
from typing import Any


DATA_DIR = Path(__file__).resolve().parent
ROOT = DATA_DIR.parents[3]
BUILDER = DATA_DIR / "build_v4_replay_feature_enriched_dataset.py"
DATASET_CHECKER = DATA_DIR / "check_v4_football_data_replay_dataset.py"
NEGATIVE_CHECKER = DATA_DIR / "check_v4_price_aware_negative_findings.py"
CORE_CHECKER = DATA_DIR / "check_v4_price_aware_replay_core.py"
OUT_CSV = DATA_DIR / "processed/v4_replay_feature_enriched_dataset.csv"
OUT_SUMMARY = DATA_DIR / "processed/v4_replay_feature_enriched_summary.json"
DOC = DATA_DIR / "V4_TEAM_STRENGTH_AND_PRICE_MOVEMENT_FEATURES.md"
FORBIDDEN_TEXT = re.compile(
    r"推荐|投注建议|下注|实单|必中|稳胆|must bet|betting advice|steam|sharp|fund[-_ ]?flow",
    re.IGNORECASE,
)
REQUIRED_STRENGTH_FIELDS = [
    "home_points_before_match",
    "away_points_before_match",
    "home_rank_before_match",
    "away_rank_before_match",
    "rank_gap",
    "points_gap",
    "home_goal_diff_before_match",
    "away_goal_diff_before_match",
    "home_recent_5_points",
    "away_recent_5_points",
    "recent_5_points_gap",
    "home_home_points_before_match",
    "away_away_points_before_match",
    "home_advantage_context_flag",
    "team_strength_context_flags",
]
REQUIRED_PRICE_FIELDS = [
    "odds_1x2_home_move",
    "odds_1x2_draw_move",
    "odds_1x2_away_move",
    "odds_over25_move",
    "odds_under25_move",
    "ah_home_move",
    "ah_away_move",
    "market_home_avg_vs_b365_close",
    "market_home_max_vs_b365_close",
    "over25_close_implied_prob",
    "ah_home_close_implied_prob",
    "price_move_direction_flag",
    "line_movement_flag",
    "price_movement_context_flags",
]


def run_py(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(path)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=300,
    )


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def git(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=ROOT, text=True)
    except subprocess.CalledProcessError:
        return ""


def staged_forbidden(staged: list[str]) -> list[str]:
    bad: list[str] = []
    for path in staged:
        lower = path.lower()
        if re.search(r"(^|/)(runtime|cache|logs?|secrets?)(/|$)", lower):
            bad.append(path)
        if re.search(r"(^|/)(\\.env|.*\\.env|.*\\.key|.*token.*)(/|$)", lower):
            bad.append(path)
    return sorted(set(bad))


def points(result: str) -> tuple[int, int]:
    if result == "H":
        return 3, 0
    if result == "A":
        return 0, 3
    if result == "D":
        return 1, 1
    return 0, 0


def empty_state() -> dict[str, Any]:
    return {"played": 0, "points": 0, "gf": 0, "ga": 0, "home_points": 0, "away_points": 0, "recent": deque(maxlen=5)}


def rank_table(states: dict[str, dict[str, Any]]) -> dict[str, int]:
    ordered = sorted(
        states.items(),
        key=lambda item: (-item[1]["points"], -(item[1]["gf"] - item[1]["ga"]), -item[1]["gf"], item[0]),
    )
    return {team: idx + 1 for idx, (team, _state) in enumerate(ordered)}


def leakage_check(rows: list[dict[str, str]]) -> bool:
    groups: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for idx, row in enumerate(rows):
        row["_idx"] = str(idx)
        groups[(row["league_code"], row["season"])].append(row)
    for group_rows in groups.values():
        group_rows.sort(key=lambda row: (row["date"], int(row["_idx"])))
        teams = {row["home_team"] for row in group_rows} | {row["away_team"] for row in group_rows}
        states = {team: empty_state() for team in teams}
        for row in group_rows:
            home = row["home_team"]
            away = row["away_team"]
            ranks = rank_table(states)
            home_state = states[home]
            away_state = states[away]
            expected = {
                "home_points_before_match": home_state["points"],
                "away_points_before_match": away_state["points"],
                "home_rank_before_match": ranks[home],
                "away_rank_before_match": ranks[away],
                "points_gap": home_state["points"] - away_state["points"],
                "home_goal_diff_before_match": home_state["gf"] - home_state["ga"],
                "away_goal_diff_before_match": away_state["gf"] - away_state["ga"],
                "home_recent_5_points": sum(home_state["recent"]),
                "away_recent_5_points": sum(away_state["recent"]),
                "home_home_points_before_match": home_state["home_points"],
                "away_away_points_before_match": away_state["away_points"],
            }
            for field, value in expected.items():
                if row[field] != str(value):
                    return False
            home_goals = int(row["full_time_home_goals"]) if row["full_time_home_goals"] else None
            away_goals = int(row["full_time_away_goals"]) if row["full_time_away_goals"] else None
            if home_goals is None or away_goals is None or row["full_time_result"] not in {"H", "D", "A"}:
                continue
            hp, ap = points(row["full_time_result"])
            home_state["played"] += 1
            away_state["played"] += 1
            home_state["points"] += hp
            away_state["points"] += ap
            home_state["gf"] += home_goals
            home_state["ga"] += away_goals
            away_state["gf"] += away_goals
            away_state["ga"] += home_goals
            home_state["home_points"] += hp
            away_state["away_points"] += ap
            home_state["recent"].append(hp)
            away_state["recent"].append(ap)
    return True


def decimal_text(value: str) -> bool:
    return value == "" or bool(re.fullmatch(r"-?\d+\.\d{4}", value))


def main() -> int:
    builder = run_py(BUILDER)
    dataset = run_py(DATASET_CHECKER)
    negative = run_py(NEGATIVE_CHECKER)
    core = run_py(CORE_CHECKER)
    rows = read_csv(OUT_CSV)
    summary = load_json(OUT_SUMMARY)
    staged = [line.strip() for line in git(["diff", "--cached", "--name-only"]).splitlines() if line.strip()]
    text = json.dumps(summary, ensure_ascii=False)
    if DOC.exists():
        text += DOC.read_text(encoding="utf-8")
    fieldnames = set(rows[0].keys()) if rows else set()
    checks = {
        "builder_exists": BUILDER.exists(),
        "builder_runs": builder.returncode == 0,
        "dataset_checker_pass": dataset.returncode == 0,
        "negative_checker_pass": negative.returncode == 0,
        "core_checker_pass": core.returncode == 0,
        "enriched_dataset_exists": OUT_CSV.exists(),
        "summary_exists": OUT_SUMMARY.exists(),
        "doc_exists": DOC.exists(),
        "row_count_15448": len(rows) == 15448 and summary.get("row_count") == 15448,
        "no_2025_26": "2025/26" not in {row.get("season") for row in rows},
        "nine_leagues": len({row.get("league_code") for row in rows}) == 9,
        "required_strength_fields": set(REQUIRED_STRENGTH_FIELDS).issubset(fieldnames),
        "required_price_fields": set(REQUIRED_PRICE_FIELDS).issubset(fieldnames),
        "pre_match_no_leakage": leakage_check(rows),
        "early_season_flag_present": summary.get("team_strength_context", {}).get("early_season_insufficient_count", 0) > 0,
        "price_movement_open_close_format": all(
            decimal_text(row[field])
            for row in rows
            for field in [
                "odds_1x2_home_move",
                "odds_1x2_draw_move",
                "odds_1x2_away_move",
                "odds_over25_move",
                "odds_under25_move",
                "ah_home_move",
                "ah_away_move",
            ]
        ),
        "missing_market_avg_marked": summary.get("price_movement_context", {}).get("market_avg_max_source_missing_count") == 15448,
        "no_forbidden_text": FORBIDDEN_TEXT.search(text) is None,
        "policy_lock": summary.get("policy_lock", {}).get("api_football_called") is False
        and summary.get("policy_lock", {}).get("v4_scan_executed") is False
        and summary.get("policy_lock", {}).get("official_grade_changed") is False
        and summary.get("policy_lock", {}).get("pending_written") is False
        and summary.get("policy_lock", {}).get("qq_sent") is False
        and summary.get("policy_lock", {}).get("cron_or_launchd_modified") is False
        and summary.get("policy_lock", {}).get("recommendation_generated") is False
        and summary.get("policy_lock", {}).get("edge_claim_generated") is False,
        "no_runtime_cache_log_secret_staged": not staged_forbidden(staged),
    }
    blockers = [name for name, ok in checks.items() if not ok]
    result = {
        "schema_version": "v4_replay_feature_enriched_checker.v1",
        "conclusion": "PASS" if not blockers else "BLOCKER",
        "checks": checks,
        "blockers": blockers,
        "row_count": len(rows),
        "team_strength_context": summary.get("team_strength_context"),
        "price_movement_context": summary.get("price_movement_context"),
        "forbidden_staged": staged_forbidden(staged),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not blockers else 2


if __name__ == "__main__":
    raise SystemExit(main())
