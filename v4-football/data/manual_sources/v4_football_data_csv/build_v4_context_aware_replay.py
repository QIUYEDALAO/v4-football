#!/usr/bin/env python3
"""Build offline context-aware replay for FT Over 2.5 and Asian Handicap."""
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DATASET = ROOT / "processed/v4_replay_feature_enriched_dataset.csv"
OUT_CSV = ROOT / "processed/v4_context_aware_replay.csv"
OUT_SUMMARY = ROOT / "processed/v4_context_aware_replay_summary.json"
BUILD_TIMESTAMP = "2026-06-07T00:00:00+08:00"

FIELDS = [
    "market",
    "context_filter",
    "context_value",
    "sample_count",
    "settled_count",
    "hit_count",
    "hit_rate",
    "avg_close_odds",
    "roi_proxy_flat_1u",
    "max_fail_streak",
    "max_drawdown_proxy",
    "price_missing_count",
    "settlement_uncertain_count",
    "confidence_flag",
    "risk_flags",
]


def dec(value: str | None) -> Decimal | None:
    raw = str(value or "").strip()
    if raw == "":
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


def read_rows() -> list[dict[str, str]]:
    with DATASET.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def bucket_signed(value: str, buckets: list[tuple[int, str]]) -> str:
    num = int_value(value)
    if num is None:
        return "MISSING"
    for limit, label in buckets:
        if num <= limit:
            return label
    return buckets[-1][1]


def prob_bucket(value: str) -> str:
    prob = dec(value)
    if prob is None:
        return "PROB_MISSING"
    if prob < Decimal("0.40"):
        return "LT_0_40"
    if prob < Decimal("0.50"):
        return "0_40_0_49"
    if prob < Decimal("0.60"):
        return "0_50_0_59"
    return "GE_0_60"


def move_direction(value: str) -> str:
    move = dec(value)
    if move is None:
        return "MOVE_MISSING"
    if move < 0:
        return "SHORTER_CLOSE"
    if move > 0:
        return "LONGER_CLOSE"
    return "STABLE"


def ah_line_bucket(value: str) -> str:
    line = dec(value)
    if line is None:
        return "LINE_MISSING"
    abs_line = abs(line)
    if abs_line == 0:
        return "AH_0"
    if abs_line <= Decimal("0.25"):
        return "AH_0_25"
    if abs_line <= Decimal("0.50"):
        return "AH_0_50"
    if abs_line <= Decimal("0.75"):
        return "AH_0_75"
    if abs_line <= Decimal("1.00"):
        return "AH_1_00"
    if abs_line <= Decimal("1.50"):
        return "AH_1_25_1_50"
    return "AH_GT_1_50"


def early_bucket(row: dict[str, str]) -> str:
    return "EARLY_SEASON_INSUFFICIENT" if "EARLY_SEASON_INSUFFICIENT" in row["team_strength_context_flags"] else "EARLY_SEASON_EXCLUDED_VIEW"


def ft_contexts(row: dict[str, str]) -> list[tuple[str, str]]:
    return [
        ("strength_gap_bucket", bucket_signed(row["points_gap"], [(-10, "AWAY_PLUS_10"), (-4, "AWAY_PLUS_4_9"), (3, "BALANCED_-3_3"), (9, "HOME_PLUS_4_9"), (10**9, "HOME_PLUS_10")])),
        ("recent_5_points_gap_bucket", bucket_signed(row["recent_5_points_gap"], [(-6, "AWAY_RECENT_PLUS_6"), (-2, "AWAY_RECENT_PLUS_2_5"), (1, "BALANCED_-1_1"), (5, "HOME_RECENT_PLUS_2_5"), (10**9, "HOME_RECENT_PLUS_6")])),
        ("over25_close_implied_prob_bucket", prob_bucket(row["over25_close_implied_prob"])),
        ("odds_over25_move_direction", move_direction(row["odds_over25_move"])),
        ("early_season_status", early_bucket(row)),
        ("league_code", row["league_code"]),
        ("season", row["season"]),
    ]


def ah_contexts(row: dict[str, str], side: str) -> list[tuple[str, str]]:
    move_field = "ah_home_move" if side == "HOME" else "ah_away_move"
    return [
        ("rank_gap_bucket", bucket_signed(row["rank_gap"], [(-10, "HOME_RANK_PLUS_10"), (-4, "HOME_RANK_PLUS_4_9"), (3, "BALANCED_-3_3"), (9, "AWAY_RANK_PLUS_4_9"), (10**9, "AWAY_RANK_PLUS_10")])),
        ("points_gap_bucket", bucket_signed(row["points_gap"], [(-10, "AWAY_PLUS_10"), (-4, "AWAY_PLUS_4_9"), (3, "BALANCED_-3_3"), (9, "HOME_PLUS_4_9"), (10**9, "HOME_PLUS_10")])),
        ("recent_5_points_gap_bucket", bucket_signed(row["recent_5_points_gap"], [(-6, "AWAY_RECENT_PLUS_6"), (-2, "AWAY_RECENT_PLUS_2_5"), (1, "BALANCED_-1_1"), (5, "HOME_RECENT_PLUS_2_5"), (10**9, "HOME_RECENT_PLUS_6")])),
        ("ah_home_close_implied_prob_bucket", prob_bucket(row["ah_home_close_implied_prob"])),
        ("ah_move_direction", move_direction(row[move_field])),
        ("asian_handicap_line_bucket", ah_line_bucket(row["asian_handicap_line"])),
        ("home_away_side", side),
        ("early_season_status", early_bucket(row)),
        ("league_code", row["league_code"]),
        ("season", row["season"]),
    ]


def outcome_pnl(hit: bool, odds: Decimal | None) -> Decimal | None:
    if odds is None:
        return None
    return odds - Decimal("1") if hit else Decimal("-1")


def settle_ah_single(goals_for: int, goals_against: int, handicap: Decimal) -> Decimal:
    margin = Decimal(goals_for - goals_against) + handicap
    if margin > 0:
        return Decimal("1")
    if margin == 0:
        return Decimal("0")
    return Decimal("-1")


def split_quarter(handicap: Decimal) -> list[Decimal] | None:
    scaled = handicap * Decimal("4")
    if scaled != scaled.to_integral_value():
        return None
    remainder = int(abs(scaled)) % 4
    if remainder in {0, 2}:
        return [handicap]
    abs_handicap = abs(handicap)
    lower_abs = (int(abs_handicap * Decimal("2")) // 1) * Decimal("0.5")
    upper_abs = lower_abs + Decimal("0.5")
    if handicap >= 0:
        return [lower_abs, upper_abs]
    return [-lower_abs, -upper_abs]


def ah_unit_result(row: dict[str, str], side: str) -> tuple[str, Decimal | None]:
    home_goals = int_value(row["full_time_home_goals"])
    away_goals = int_value(row["full_time_away_goals"])
    line = dec(row["asian_handicap_line"])
    if home_goals is None or away_goals is None or line is None:
        return "AH_SETTLEMENT_UNCERTAIN", None
    goals_for, goals_against, handicap = (home_goals, away_goals, line) if side == "HOME" else (away_goals, home_goals, -line)
    parts = split_quarter(handicap)
    if not parts:
        return "AH_SETTLEMENT_UNCERTAIN", None
    unit = sum(settle_ah_single(goals_for, goals_against, part) for part in parts) / Decimal(len(parts))
    return "SETTLED", unit


def replay_entries(rows: list[dict[str, str]]) -> dict[tuple[str, str, str], list[dict[str, Any]]]:
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        home_goals = int_value(row["full_time_home_goals"])
        away_goals = int_value(row["full_time_away_goals"])
        over_odds = dec(row["odds_over25_close"])
        if home_goals is not None and away_goals is not None:
            hit = home_goals + away_goals > 2.5
            pnl = outcome_pnl(hit, over_odds)
            entry = {
                "settlement_status": "SETTLED",
                "hit": hit,
                "odds": over_odds,
                "pnl": pnl,
                "price_missing": over_odds is None,
                "uncertain": False,
                "early": "EARLY_SEASON_INSUFFICIENT" in row["team_strength_context_flags"],
            }
            for context_filter, context_value in ft_contexts(row):
                grouped[("FT_OVER25", context_filter, context_value)].append(entry)
        for side in ["HOME", "AWAY"]:
            status, unit = ah_unit_result(row, side)
            odds = dec(row["asian_handicap_home_close" if side == "HOME" else "asian_handicap_away_close"])
            pnl: Decimal | None = None
            hit = False
            if unit is not None:
                hit = unit > 0
                if odds is not None:
                    pnl = unit * (odds - Decimal("1")) if unit > 0 else unit
            entry = {
                "settlement_status": status,
                "hit": hit,
                "odds": odds,
                "pnl": pnl,
                "price_missing": odds is None,
                "uncertain": status != "SETTLED",
                "early": "EARLY_SEASON_INSUFFICIENT" in row["team_strength_context_flags"],
            }
            for context_filter, context_value in ah_contexts(row, side):
                grouped[("ASIAN_HANDICAP", context_filter, context_value)].append(entry)
    return grouped


def confidence(sample_count: int) -> str:
    if sample_count < 300:
        return "SMALL_SAMPLE"
    if sample_count < 1000:
        return "MEDIUM_RESEARCH_ONLY"
    return "HIGH_CONFIDENCE"


def max_fail_streak(entries: list[dict[str, Any]]) -> int:
    streak = 0
    best = 0
    for row in entries:
        pnl = row.get("pnl")
        if pnl is None:
            continue
        if pnl < 0:
            streak += 1
            best = max(best, streak)
        else:
            streak = 0
    return best


def max_drawdown(entries: list[dict[str, Any]]) -> Decimal:
    cumulative = Decimal("0")
    peak = Decimal("0")
    worst = Decimal("0")
    for row in entries:
        pnl = row.get("pnl")
        if pnl is None:
            continue
        cumulative += pnl
        peak = max(peak, cumulative)
        worst = min(worst, cumulative - peak)
    return worst


def metric_row(key: tuple[str, str, str], entries: list[dict[str, Any]]) -> dict[str, Any]:
    market, context_filter, context_value = key
    sample_count = len(entries)
    settled = [row for row in entries if row["settlement_status"] == "SETTLED"]
    priced = [row for row in settled if row.get("pnl") is not None and row.get("odds") is not None]
    hit_count = sum(1 for row in settled if row["hit"])
    odds = [row["odds"] for row in priced]
    pnls = [row["pnl"] for row in priced]
    roi = sum(pnls) / Decimal(len(pnls)) if pnls else None
    avg_odds = sum(odds) / Decimal(len(odds)) if odds else None
    drawdown = max_drawdown(priced)
    conf = confidence(sample_count)
    flags: list[str] = []
    if conf == "SMALL_SAMPLE":
        flags.append("SMALL_SAMPLE_NO_CANDIDATE")
    if conf == "MEDIUM_RESEARCH_ONLY":
        flags.append("MEDIUM_RESEARCH_ONLY")
    if any(row["early"] for row in entries) and context_filter == "early_season_status" and context_value == "EARLY_SEASON_INSUFFICIENT":
        flags.append("EARLY_SEASON_NOT_MAIN_CANDIDATE")
    if roi is not None and roi > 0 and abs(drawdown) > Decimal(max(30, sample_count // 8)):
        flags.append("HIGH_DRAWDOWN_RISK")
    if roi is not None and roi > 0:
        flags.append("POSITIVE_ROI_RESEARCH_ONLY")
    return {
        "market": market,
        "context_filter": context_filter,
        "context_value": context_value,
        "sample_count": sample_count,
        "settled_count": len(settled),
        "hit_count": hit_count,
        "hit_rate": round(hit_count / len(settled), 6) if settled else "",
        "avg_close_odds": round(float(avg_odds), 6) if avg_odds is not None else "",
        "roi_proxy_flat_1u": round(float(roi), 6) if roi is not None else "",
        "max_fail_streak": max_fail_streak(priced),
        "max_drawdown_proxy": round(float(drawdown), 6) if priced else "",
        "price_missing_count": sum(1 for row in entries if row["price_missing"]),
        "settlement_uncertain_count": sum(1 for row in entries if row["uncertain"]),
        "confidence_flag": conf,
        "risk_flags": "|".join(flags or ["RESEARCH_ONLY_NO_CANDIDATE"]),
    }


def build() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = read_rows()
    grouped = replay_entries(rows)
    metrics = [metric_row(key, entries) for key, entries in sorted(grouped.items())]
    confidence_counts = Counter(row["confidence_flag"] for row in metrics)
    positive = [row for row in metrics if row["roi_proxy_flat_1u"] != "" and row["roi_proxy_flat_1u"] > 0]
    candidate_like = [
        row for row in positive
        if row["sample_count"] >= 1000
        and "HIGH_DRAWDOWN_RISK" not in row["risk_flags"]
        and "EARLY_SEASON_NOT_MAIN_CANDIDATE" not in row["risk_flags"]
    ]
    summary = {
        "schema_version": "v4_context_aware_replay_summary.v1",
        "generated_at": BUILD_TIMESTAMP,
        "source_dataset": str(DATASET.relative_to(ROOT)),
        "output_csv": str(OUT_CSV.relative_to(ROOT)),
        "row_count": len(rows),
        "seasons": sorted({row["season"] for row in rows}),
        "markets": ["ASIAN_HANDICAP", "FT_OVER25"],
        "context_filters": sorted({row["context_filter"] for row in metrics}),
        "context_bucket_count": len(metrics),
        "confidence_counts": dict(sorted(confidence_counts.items())),
        "positive_roi_bucket_count": len(positive),
        "research_candidate_count": len(candidate_like),
        "research_candidates": sorted(candidate_like, key=lambda row: row["roi_proxy_flat_1u"], reverse=True)[:20],
        "risk_summary": {
            "small_sample_bucket_count": sum(1 for row in metrics if row["confidence_flag"] == "SMALL_SAMPLE"),
            "early_season_bucket_not_candidate": sum("EARLY_SEASON_NOT_MAIN_CANDIDATE" in row["risk_flags"] for row in metrics),
            "high_drawdown_risk_count": sum("HIGH_DRAWDOWN_RISK" in row["risk_flags"] for row in metrics),
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
    return metrics, summary


def main() -> int:
    rows, summary = build()
    with OUT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    OUT_SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "conclusion": "PASS",
        "context_bucket_count": len(rows),
        "confidence_counts": summary["confidence_counts"],
        "research_candidate_count": summary["research_candidate_count"],
        "output": str(OUT_CSV.relative_to(ROOT)),
        "summary": str(OUT_SUMMARY.relative_to(ROOT)),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
