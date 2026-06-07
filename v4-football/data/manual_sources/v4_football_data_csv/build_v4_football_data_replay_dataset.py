#!/usr/bin/env python3
"""Build the V4 Football-Data unified replay dataset.

The builder only reads committed football-data.co.uk CSV files. It does not
call APIs, does not alter V4 production state, and does not create signals.
"""
from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
RAW_DIR = ROOT / "raw"
OUT_DIR = ROOT / "processed"
DATASET = OUT_DIR / "v4_football_data_replay_dataset.csv"
SUMMARY = OUT_DIR / "v4_football_data_replay_summary.json"
BUILD_TIMESTAMP = "2026-06-07T00:00:00+08:00"

COMPLETE_SEASONS = {"2021", "2122", "2223", "2324", "2425"}
CURRENT_PARTIAL_SEASONS = {"2526"}
SOURCE = "football-data.co.uk"

LEAGUE_NAMES = {
    "B1": "Belgian Pro League",
    "D1": "German Bundesliga",
    "E0": "English Premier League",
    "F1": "French Ligue 1",
    "I1": "Italian Serie A",
    "N1": "Dutch Eredivisie",
    "P1": "Portuguese Primeira Liga",
    "SP1": "Spanish La Liga",
    "T1": "Turkish Super Lig",
}

OUTPUT_FIELDS = [
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

FIELD_MAP = {
    "home_team": "HomeTeam",
    "away_team": "AwayTeam",
    "full_time_home_goals": "FTHG",
    "full_time_away_goals": "FTAG",
    "full_time_result": "FTR",
    "half_time_home_goals": "HTHG",
    "half_time_away_goals": "HTAG",
    "half_time_result": "HTR",
    "home_shots": "HS",
    "away_shots": "AS",
    "home_shots_on_target": "HST",
    "away_shots_on_target": "AST",
    "home_corners": "HC",
    "away_corners": "AC",
    "home_yellow_cards": "HY",
    "away_yellow_cards": "AY",
    "home_red_cards": "HR",
    "away_red_cards": "AR",
    "odds_1x2_home_open": "B365H",
    "odds_1x2_draw_open": "B365D",
    "odds_1x2_away_open": "B365A",
    "odds_1x2_home_close": "B365CH",
    "odds_1x2_draw_close": "B365CD",
    "odds_1x2_away_close": "B365CA",
    "odds_over25_open": "B365>2.5",
    "odds_under25_open": "B365<2.5",
    "odds_over25_close": "B365C>2.5",
    "odds_under25_close": "B365C<2.5",
    "asian_handicap_home_open": "B365AHH",
    "asian_handicap_away_open": "B365AHA",
    "asian_handicap_home_close": "B365CAHH",
    "asian_handicap_away_close": "B365CAHA",
}

FIELD_GROUPS = {
    "result": ["FTHG", "FTAG", "FTR", "HTHG", "HTAG", "HTR"],
    "stats": ["HS", "AS", "HST", "AST", "HC", "AC", "HY", "AY", "HR", "AR"],
    "1x2_open": ["B365H", "B365D", "B365A"],
    "1x2_close": ["B365CH", "B365CD", "B365CA"],
    "ou25_open": ["B365>2.5", "B365<2.5"],
    "ou25_close": ["B365C>2.5", "B365C<2.5"],
    "ah_open": ["AHh", "B365AHH", "B365AHA"],
    "ah_close": ["AHCh", "B365CAHH", "B365CAHA"],
}


def season_label(code: str) -> str:
    if code == "2021":
        return "2020/21"
    return f"20{code[:2]}/{code[2:]}"


def clean_header(row: dict[str, str]) -> dict[str, str]:
    return {key.lstrip("\ufeff"): value for key, value in row.items()}


def parse_date(raw: str) -> str:
    value = (raw or "").strip()
    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            pass
    return value


def value(row: dict[str, str], key: str) -> str:
    return str(row.get(key, "") or "").strip()


def has_all(row: dict[str, str], keys: list[str]) -> bool:
    return all(value(row, key) != "" for key in keys)


def data_quality_flags(row: dict[str, str]) -> list[str]:
    flags: list[str] = []
    for group, keys in FIELD_GROUPS.items():
        if not has_all(row, keys):
            flags.append(f"{group.upper()}_PARTIAL")
    if value(row, "AHCh") and value(row, "AHh") and value(row, "AHCh") != value(row, "AHh"):
        flags.append("AH_LINE_MOVED_BETWEEN_OPEN_CLOSE")
    return flags or ["COMPLETE_FOR_REPLAY_SCHEMA"]


def row_to_output(row: dict[str, str], league_code: str, season_code: str) -> dict[str, str]:
    out = {
        "source": SOURCE,
        "league_code": league_code,
        "league_name": LEAGUE_NAMES.get(league_code, league_code),
        "season": season_label(season_code),
        "date": parse_date(value(row, "Date")),
        "data_quality_flags": "|".join(data_quality_flags(row)),
    }
    for out_key, source_key in FIELD_MAP.items():
        out[out_key] = value(row, source_key)
    out["asian_handicap_line"] = value(row, "AHCh") or value(row, "AHh")
    return {field: out.get(field, "") for field in OUTPUT_FIELDS}


def iter_csv_files() -> list[tuple[Path, str, str]]:
    files: list[tuple[Path, str, str]] = []
    for path in sorted(RAW_DIR.glob("*.csv")):
        stem = path.stem
        if "_" not in stem:
            continue
        league_code, season_code = stem.split("_", 1)
        files.append((path, league_code, season_code))
    return files


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
        return [clean_header(row) for row in csv.DictReader(handle)]


def coverage_ratio(rows: list[dict[str, str]], fields: list[str]) -> float:
    if not rows:
        return 0.0
    covered = sum(1 for row in rows if all(row.get(field, "") != "" for field in fields))
    return round(covered / len(rows), 6)


def missing_counts(rows: list[dict[str, str]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in rows:
        for field in OUTPUT_FIELDS:
            if row.get(field, "") == "":
                counts[field] += 1
    return dict(sorted(counts.items()))


def main() -> int:
    files = iter_csv_files()
    full_rows: list[dict[str, str]] = []
    excluded_rows = 0
    excluded_by_season: Counter[str] = Counter()
    source_file_counts: dict[str, int] = {}

    for path, league_code, season_code in files:
        rows = read_csv(path)
        source_file_counts[path.name] = len(rows)
        if season_code in CURRENT_PARTIAL_SEASONS:
            excluded_rows += len(rows)
            excluded_by_season[season_label(season_code)] += len(rows)
            continue
        if season_code not in COMPLETE_SEASONS:
            continue
        full_rows.extend(row_to_output(row, league_code, season_code) for row in rows)

    rows_by_league = Counter(row["league_code"] for row in full_rows)
    rows_by_season = Counter(row["season"] for row in full_rows)
    coverage = {
        "1x2_open": coverage_ratio(full_rows, ["odds_1x2_home_open", "odds_1x2_draw_open", "odds_1x2_away_open"]),
        "1x2_close": coverage_ratio(full_rows, ["odds_1x2_home_close", "odds_1x2_draw_close", "odds_1x2_away_close"]),
        "ou25_open": coverage_ratio(full_rows, ["odds_over25_open", "odds_under25_open"]),
        "ou25_close": coverage_ratio(full_rows, ["odds_over25_close", "odds_under25_close"]),
        "ah_open": coverage_ratio(full_rows, ["asian_handicap_line", "asian_handicap_home_open", "asian_handicap_away_open"]),
        "ah_close": coverage_ratio(full_rows, ["asian_handicap_line", "asian_handicap_home_close", "asian_handicap_away_close"]),
        "result": coverage_ratio(full_rows, [
            "full_time_home_goals",
            "full_time_away_goals",
            "full_time_result",
            "half_time_home_goals",
            "half_time_away_goals",
            "half_time_result",
        ]),
        "stats": coverage_ratio(full_rows, [
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
    }
    summary: dict[str, Any] = {
        "schema_version": "v4_football_data_replay_summary.v1",
        "generated_at": BUILD_TIMESTAMP,
        "source": SOURCE,
        "raw_csv_count": len(files),
        "complete_seasons_included": [season_label(code) for code in sorted(COMPLETE_SEASONS)],
        "current_partial_seasons_excluded": [season_label(code) for code in sorted(CURRENT_PARTIAL_SEASONS)],
        "total_rows": len(full_rows),
        "rows_by_league": dict(sorted(rows_by_league.items())),
        "rows_by_season": dict(sorted(rows_by_season.items())),
        "excluded_current_partial_rows": excluded_rows,
        "excluded_current_partial_rows_by_season": dict(sorted(excluded_by_season.items())),
        "field_missing_counts": missing_counts(full_rows),
        "coverage": coverage,
        "stats_coverage": coverage["stats"],
        "source_file_counts": source_file_counts,
        "replay_ready": bool(full_rows) and all(value >= 0.98 for value in coverage.values()),
        "policy_lock": {
            "api_football_called": False,
            "v4_scan_executed": False,
            "official_grade_changed": False,
            "pending_written": False,
            "qq_sent": False,
            "cron_or_launchd_modified": False,
            "strategy_online": False,
            "recommendation_generated": False,
        },
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with DATASET.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(full_rows)
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "conclusion": "PASS",
        "dataset": str(DATASET.relative_to(ROOT)),
        "summary": str(SUMMARY.relative_to(ROOT)),
        "rows": len(full_rows),
        "excluded_current_partial_rows": excluded_rows,
        "replay_ready": summary["replay_ready"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
