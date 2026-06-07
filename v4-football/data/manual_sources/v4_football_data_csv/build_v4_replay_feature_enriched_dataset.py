#!/usr/bin/env python3
"""Build offline V4 replay dataset with strength and price movement features."""
from __future__ import annotations

import csv
import json
from collections import defaultdict, deque
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DATASET = ROOT / "processed/v4_football_data_replay_dataset.csv"
OUT_CSV = ROOT / "processed/v4_replay_feature_enriched_dataset.csv"
OUT_SUMMARY = ROOT / "processed/v4_replay_feature_enriched_summary.json"
BUILD_TIMESTAMP = "2026-06-07T00:00:00+08:00"

TEAM_STRENGTH_FIELDS = [
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

PRICE_MOVEMENT_FIELDS = [
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


def dec(value: str | None) -> Decimal | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return Decimal(raw)
    except (InvalidOperation, ValueError):
        return None


def int_value(value: str | None) -> int | None:
    raw = str(value or "").strip()
    if raw == "":
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def dec_out(value: Decimal | None) -> str:
    if value is None:
        return ""
    return format(value.quantize(Decimal("0.0001")), "f")


def read_dataset() -> list[dict[str, str]]:
    with DATASET.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    for idx, row in enumerate(rows):
        row["_source_order"] = str(idx)
    return rows


def result_points(result: str) -> tuple[int, int]:
    if result == "H":
        return 3, 0
    if result == "A":
        return 0, 3
    if result == "D":
        return 1, 1
    return 0, 0


def empty_team_state() -> dict[str, Any]:
    return {
        "played": 0,
        "points": 0,
        "gf": 0,
        "ga": 0,
        "home_points": 0,
        "away_points": 0,
        "recent_points": deque(maxlen=5),
    }


def rank_table(states: dict[str, dict[str, Any]]) -> dict[str, int]:
    ordered = sorted(
        states.items(),
        key=lambda item: (
            -int(item[1]["points"]),
            -(int(item[1]["gf"]) - int(item[1]["ga"])),
            -int(item[1]["gf"]),
            item[0],
        ),
    )
    return {team: idx + 1 for idx, (team, _state) in enumerate(ordered)}


def strength_features(row: dict[str, str], states: dict[str, dict[str, Any]]) -> dict[str, str]:
    home = row["home_team"]
    away = row["away_team"]
    home_state = states[home]
    away_state = states[away]
    ranks = rank_table(states)
    flags: list[str] = []
    if home_state["played"] < 5 or away_state["played"] < 5:
        flags.append("EARLY_SEASON_INSUFFICIENT")
    if home_state["played"] == 0 or away_state["played"] == 0:
        flags.append("NO_PRIOR_MATCH_SAMPLE")
    home_recent = sum(home_state["recent_points"])
    away_recent = sum(away_state["recent_points"])
    home_goal_diff = int(home_state["gf"]) - int(home_state["ga"])
    away_goal_diff = int(away_state["gf"]) - int(away_state["ga"])
    rank_gap = ranks.get(away, 0) - ranks.get(home, 0)
    points_gap = int(home_state["points"]) - int(away_state["points"])
    home_advantage = "HOME_CONTEXT_POSITIVE" if int(home_state["home_points"]) >= int(away_state["away_points"]) else "HOME_CONTEXT_WEAKER"
    return {
        "home_points_before_match": str(home_state["points"]),
        "away_points_before_match": str(away_state["points"]),
        "home_rank_before_match": str(ranks.get(home, "")),
        "away_rank_before_match": str(ranks.get(away, "")),
        "rank_gap": str(rank_gap),
        "points_gap": str(points_gap),
        "home_goal_diff_before_match": str(home_goal_diff),
        "away_goal_diff_before_match": str(away_goal_diff),
        "home_recent_5_points": str(home_recent),
        "away_recent_5_points": str(away_recent),
        "recent_5_points_gap": str(home_recent - away_recent),
        "home_home_points_before_match": str(home_state["home_points"]),
        "away_away_points_before_match": str(away_state["away_points"]),
        "home_advantage_context_flag": home_advantage,
        "team_strength_context_flags": "|".join(flags or ["TEAM_STRENGTH_CONTEXT_AVAILABLE"]),
    }


def update_states(row: dict[str, str], states: dict[str, dict[str, Any]]) -> None:
    home = row["home_team"]
    away = row["away_team"]
    home_goals = int_value(row.get("full_time_home_goals"))
    away_goals = int_value(row.get("full_time_away_goals"))
    result = row.get("full_time_result", "")
    if home_goals is None or away_goals is None or result not in {"H", "D", "A"}:
        return
    home_points, away_points = result_points(result)
    home_state = states[home]
    away_state = states[away]
    home_state["played"] += 1
    away_state["played"] += 1
    home_state["points"] += home_points
    away_state["points"] += away_points
    home_state["gf"] += home_goals
    home_state["ga"] += away_goals
    away_state["gf"] += away_goals
    away_state["ga"] += home_goals
    home_state["home_points"] += home_points
    away_state["away_points"] += away_points
    home_state["recent_points"].append(home_points)
    away_state["recent_points"].append(away_points)


def price_move(row: dict[str, str], open_field: str, close_field: str) -> tuple[str, Decimal | None]:
    open_odds = dec(row.get(open_field))
    close_odds = dec(row.get(close_field))
    if open_odds is None or close_odds is None:
        return "", None
    move = close_odds - open_odds
    return dec_out(move), move


def implied_prob(close_value: str | None) -> str:
    odds = dec(close_value)
    if odds is None or odds == 0:
        return ""
    return dec_out(Decimal("1") / odds)


def direction_flag(moves: dict[str, Decimal | None]) -> str:
    available = {key: value for key, value in moves.items() if value is not None}
    if not available:
        return "PRICE_MOVEMENT_MISSING"
    shortened = [key for key, value in available.items() if value < 0]
    drifted = [key for key, value in available.items() if value > 0]
    if not shortened and not drifted:
        return "PRICE_STABLE"
    parts: list[str] = []
    if shortened:
        parts.append("SHORTER_CLOSE:" + ",".join(sorted(shortened)))
    if drifted:
        parts.append("LONGER_CLOSE:" + ",".join(sorted(drifted)))
    return "|".join(parts)


def price_features(row: dict[str, str]) -> dict[str, str]:
    movement_fields = {
        "home": ("odds_1x2_home_open", "odds_1x2_home_close"),
        "draw": ("odds_1x2_draw_open", "odds_1x2_draw_close"),
        "away": ("odds_1x2_away_open", "odds_1x2_away_close"),
        "over25": ("odds_over25_open", "odds_over25_close"),
        "under25": ("odds_under25_open", "odds_under25_close"),
        "ah_home": ("asian_handicap_home_open", "asian_handicap_home_close"),
        "ah_away": ("asian_handicap_away_open", "asian_handicap_away_close"),
    }
    moves: dict[str, Decimal | None] = {}
    out: dict[str, str] = {}
    output_names = {
        "home": "odds_1x2_home_move",
        "draw": "odds_1x2_draw_move",
        "away": "odds_1x2_away_move",
        "over25": "odds_over25_move",
        "under25": "odds_under25_move",
        "ah_home": "ah_home_move",
        "ah_away": "ah_away_move",
    }
    for key, (open_field, close_field) in movement_fields.items():
        text, move = price_move(row, open_field, close_field)
        out[output_names[key]] = text
        moves[key] = move
    flags: list[str] = []
    if any(value is None for value in moves.values()):
        flags.append("PRICE_MOVEMENT_MISSING")
    out["market_home_avg_vs_b365_close"] = ""
    out["market_home_max_vs_b365_close"] = ""
    flags.append("MARKET_AVG_MAX_SOURCE_MISSING")
    out["over25_close_implied_prob"] = implied_prob(row.get("odds_over25_close"))
    out["ah_home_close_implied_prob"] = implied_prob(row.get("asian_handicap_home_close"))
    out["price_move_direction_flag"] = direction_flag(moves)
    out["line_movement_flag"] = "LINE_MOVEMENT_SOURCE_FLAG" if "AH_LINE_MOVED_BETWEEN_OPEN_CLOSE" in row.get("data_quality_flags", "") else "LINE_MOVEMENT_VALUE_MISSING"
    out["price_movement_context_flags"] = "|".join(flags or ["PRICE_MOVEMENT_CONTEXT_AVAILABLE"])
    return out


def build() -> tuple[list[dict[str, str]], dict[str, Any]]:
    rows = read_dataset()
    enriched: list[dict[str, str]] = []
    groups: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[(row["league_code"], row["season"])].append(row)
    for group_rows in groups.values():
        group_rows.sort(key=lambda row: (row["date"], int(row["_source_order"])))
        teams = {row["home_team"] for row in group_rows} | {row["away_team"] for row in group_rows}
        states = {team: empty_team_state() for team in teams}
        for row in group_rows:
            output = {key: value for key, value in row.items() if key != "_source_order"}
            output["_sort_order"] = row["_source_order"]
            output.update(strength_features(row, states))
            output.update(price_features(row))
            enriched.append(output)
            update_states(row, states)
    enriched.sort(key=lambda row: int(row["_sort_order"]))
    for row in enriched:
        row.pop("_sort_order", None)
    summary = summarize(enriched)
    return enriched, summary


def summarize(rows: list[dict[str, str]]) -> dict[str, Any]:
    seasons = sorted({row["season"] for row in rows})
    leagues = sorted({row["league_code"] for row in rows})
    early = sum("EARLY_SEASON_INSUFFICIENT" in row["team_strength_context_flags"] for row in rows)
    no_prior = sum("NO_PRIOR_MATCH_SAMPLE" in row["team_strength_context_flags"] for row in rows)
    price_missing = sum("PRICE_MOVEMENT_MISSING" in row["price_movement_context_flags"] for row in rows)
    avg_missing = sum("MARKET_AVG_MAX_SOURCE_MISSING" in row["price_movement_context_flags"] for row in rows)
    line_flag = sum(row["line_movement_flag"] == "LINE_MOVEMENT_SOURCE_FLAG" for row in rows)
    return {
        "schema_version": "v4_replay_feature_enriched_summary.v1",
        "generated_at": BUILD_TIMESTAMP,
        "source_dataset": str(DATASET.relative_to(ROOT)),
        "output_dataset": str(OUT_CSV.relative_to(ROOT)),
        "row_count": len(rows),
        "seasons": seasons,
        "leagues": leagues,
        "team_strength_context": {
            "fields": TEAM_STRENGTH_FIELDS,
            "early_season_insufficient_count": early,
            "no_prior_match_sample_count": no_prior,
            "leakage_policy": "PRE_MATCH_ACCUMULATION_ONLY",
        },
        "price_movement_context": {
            "fields": PRICE_MOVEMENT_FIELDS,
            "price_movement_missing_count": price_missing,
            "market_avg_max_source_missing_count": avg_missing,
            "line_movement_source_flag_count": line_flag,
            "movement_policy": "OPEN_CLOSE_DIFF_ONLY",
        },
        "policy_lock": {
            "api_football_called": False,
            "v4_scan_executed": False,
            "official_grade_changed": False,
            "pending_written": False,
            "qq_sent": False,
            "cron_or_launchd_modified": False,
            "strategy_online": False,
            "recommendation_generated": False,
            "edge_claim_generated": False,
        },
    }


def main() -> int:
    rows, summary = build()
    fieldnames = list(rows[0].keys()) if rows else []
    with OUT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    OUT_SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "conclusion": "PASS",
        "row_count": len(rows),
        "output": str(OUT_CSV.relative_to(ROOT)),
        "summary": str(OUT_SUMMARY.relative_to(ROOT)),
        "early_season_insufficient_count": summary["team_strength_context"]["early_season_insufficient_count"],
        "price_movement_missing_count": summary["price_movement_context"]["price_movement_missing_count"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
