#!/usr/bin/env python3
"""Check the V4 Football-Data unified replay dataset."""
from __future__ import annotations

import csv
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


DATA_DIR = Path(__file__).resolve().parent
ROOT = DATA_DIR.parents[3]
RAW_DIR = DATA_DIR / "raw"
BUILDER = DATA_DIR / "build_v4_football_data_replay_dataset.py"
DATASET = DATA_DIR / "processed/v4_football_data_replay_dataset.csv"
SUMMARY = DATA_DIR / "processed/v4_football_data_replay_summary.json"
DOC = DATA_DIR / "V4_FOOTBALL_DATA_CSV_REPLAY_DATASET.md"

REQUIRED_FIELDS = [
    "source",
    "league_code",
    "league_name",
    "season",
    "date",
    "home_team",
    "away_team",
    "full_time_home_goals",
    "full_time_away_goals",
    "full_time_result",
    "half_time_home_goals",
    "half_time_away_goals",
    "half_time_result",
    "home_shots",
    "away_shots",
    "home_shots_on_target",
    "away_shots_on_target",
    "home_corners",
    "away_corners",
    "home_yellow_cards",
    "away_yellow_cards",
    "home_red_cards",
    "away_red_cards",
    "odds_1x2_home_open",
    "odds_1x2_draw_open",
    "odds_1x2_away_open",
    "odds_1x2_home_close",
    "odds_1x2_draw_close",
    "odds_1x2_away_close",
    "odds_over25_open",
    "odds_under25_open",
    "odds_over25_close",
    "odds_under25_close",
    "asian_handicap_line",
    "asian_handicap_home_open",
    "asian_handicap_away_open",
    "asian_handicap_home_close",
    "asian_handicap_away_close",
    "data_quality_flags",
]
CORE_LEAGUES = {"E0", "SP1", "D1", "I1", "F1"}
ALL_LEAGUES = {"E0", "SP1", "D1", "I1", "F1", "P1", "N1", "B1", "T1"}
COMPLETE_SEASONS = {"2020/21", "2021/22", "2022/23", "2023/24", "2024/25"}
FORBIDDEN_TEXT = re.compile(
    r"推荐|投注建议|下注|实单|必中|稳胆|betting advice|recommendation signal|must bet",
    re.IGNORECASE,
)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def git(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=ROOT, text=True)
    except subprocess.CalledProcessError:
        return ""


def read_dataset() -> list[dict[str, str]]:
    if not DATASET.exists():
        return []
    with DATASET.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def coverage(rows: list[dict[str, str]], fields: list[str]) -> float:
    if not rows:
        return 0.0
    return sum(1 for row in rows if all(row.get(field, "") != "" for field in fields)) / len(rows)


def staged_forbidden(staged: list[str]) -> list[str]:
    bad: list[str] = []
    for path in staged:
        lower = path.lower()
        if re.search(r"(^|/)(runtime|cache|logs?|secrets?)(/|$)", lower):
            bad.append(path)
        if re.search(r"(^|/)(\\.env|.*\\.env|.*\\.key|.*token.*)(/|$)", lower):
            bad.append(path)
    return sorted(set(bad))


def main() -> int:
    builder_proc = subprocess.run([sys.executable, str(BUILDER)], cwd=ROOT, capture_output=True, text=True, timeout=180)
    summary = load_json(SUMMARY) or {}
    rows = read_dataset()
    header = list(rows[0].keys()) if rows else []
    seasons = {row.get("season") for row in rows}
    leagues = {row.get("league_code") for row in rows}
    rows_by_league = summary.get("rows_by_league") or {}
    staged = [line.strip() for line in git(["diff", "--cached", "--name-only"]).splitlines() if line.strip()]
    text = ""
    for path in [DOC, SUMMARY]:
        if path.exists():
            text += path.read_text(encoding="utf-8")
    coverage_checks = {
        "result": coverage(rows, [
            "full_time_home_goals",
            "full_time_away_goals",
            "full_time_result",
            "half_time_home_goals",
            "half_time_away_goals",
            "half_time_result",
        ]),
        "stats": coverage(rows, [
            "home_shots",
            "away_shots",
            "home_shots_on_target",
            "away_shots_on_target",
            "home_corners",
            "away_corners",
            "home_yellow_cards",
            "away_yellow_cards",
            "home_red_cards",
            "away_red_cards",
        ]),
        "1x2_open": coverage(rows, ["odds_1x2_home_open", "odds_1x2_draw_open", "odds_1x2_away_open"]),
        "1x2_close": coverage(rows, ["odds_1x2_home_close", "odds_1x2_draw_close", "odds_1x2_away_close"]),
        "ou25_open": coverage(rows, ["odds_over25_open", "odds_under25_open"]),
        "ou25_close": coverage(rows, ["odds_over25_close", "odds_under25_close"]),
        "ah_open": coverage(rows, ["asian_handicap_line", "asian_handicap_home_open", "asian_handicap_away_open"]),
        "ah_close": coverage(rows, ["asian_handicap_line", "asian_handicap_home_close", "asian_handicap_away_close"]),
    }
    policy = summary.get("policy_lock") or {}
    checks = {
        "builder_exists": BUILDER.exists(),
        "builder_runs": builder_proc.returncode == 0,
        "dataset_exists": DATASET.exists(),
        "summary_exists": SUMMARY.exists(),
        "doc_exists": DOC.exists(),
        "raw_csv_count_54": len(list(RAW_DIR.glob("*.csv"))) == 54,
        "schema_complete": header == REQUIRED_FIELDS,
        "row_count_reasonable": len(rows) >= 14000,
        "no_current_partial_in_dataset": "2025/26" not in seasons,
        "complete_seasons_exact": seasons == COMPLETE_SEASONS,
        "all_9_leagues_present": leagues == ALL_LEAGUES,
        "core_5_leagues_5_seasons_present": all(
            any(row.get("league_code") == league and row.get("season") == season for row in rows)
            for league in CORE_LEAGUES
            for season in COMPLETE_SEASONS
        ),
        "excluded_current_partial_present": int(summary.get("excluded_current_partial_rows") or 0) > 0,
        "summary_total_matches_dataset": int(summary.get("total_rows") or 0) == len(rows),
        "rows_by_league_complete": set(rows_by_league) == ALL_LEAGUES,
        "coverage_thresholds": all(value >= 0.98 for value in coverage_checks.values()),
        "replay_ready_true": summary.get("replay_ready") is True,
        "no_forbidden_recommendation_text": FORBIDDEN_TEXT.search(text) is None,
        "policy_lock": policy.get("api_football_called") is False
        and policy.get("v4_scan_executed") is False
        and policy.get("official_grade_changed") is False
        and policy.get("pending_written") is False
        and policy.get("qq_sent") is False
        and policy.get("cron_or_launchd_modified") is False
        and policy.get("strategy_online") is False
        and policy.get("recommendation_generated") is False,
        "no_runtime_cache_log_secret_staged": not staged_forbidden(staged),
    }
    blockers = [name for name, ok in checks.items() if not ok]
    result = {
        "schema_version": "v4_football_data_replay_dataset_checker.v1",
        "conclusion": "PASS" if not blockers else "BLOCKER",
        "checks": checks,
        "blockers": blockers,
        "dataset_rows": len(rows),
        "seasons": sorted(season for season in seasons if season),
        "leagues": sorted(league for league in leagues if league),
        "excluded_current_partial_rows": summary.get("excluded_current_partial_rows"),
        "coverage": coverage_checks,
        "forbidden_staged": staged_forbidden(staged),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not blockers else 2


if __name__ == "__main__":
    raise SystemExit(main())
