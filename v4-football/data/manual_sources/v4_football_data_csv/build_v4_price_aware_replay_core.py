#!/usr/bin/env python3
"""Build V4 offline price-aware replay core from Football-Data CSV dataset.

This builder is research-only. It reads the processed Football-Data replay
dataset and writes offline market settlement ledgers and aggregate metrics.
"""
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DATASET = ROOT / "processed/v4_football_data_replay_dataset.csv"
LEDGER = ROOT / "processed/v4_price_aware_replay_core_ledger.csv"
SUMMARY = ROOT / "processed/v4_price_aware_replay_core_summary.json"
BUILD_TIMESTAMP = "2026-06-07T00:00:00+08:00"

LEDGER_FIELDS = [
    "source",
    "market",
    "selection",
    "league_code",
    "league_name",
    "season",
    "date",
    "home_team",
    "away_team",
    "full_time_result",
    "full_time_home_goals",
    "full_time_away_goals",
    "line",
    "close_odds",
    "price_status",
    "settlement_status",
    "hit",
    "pnl_proxy_flat_1u",
    "data_quality_flags",
]


def to_int(value: str) -> int | None:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def to_decimal(value: str) -> Decimal | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return Decimal(raw)
    except (InvalidOperation, ValueError):
        return None


def dec_str(value: Decimal | None) -> str:
    if value is None:
        return ""
    return format(value.normalize(), "f")


def outcome_to_pnl(hit: bool, odds: Decimal | None) -> Decimal | None:
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


def split_quarter_handicap(handicap: Decimal) -> list[Decimal] | None:
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


def settle_ah(goals_for: int, goals_against: int, handicap: Decimal) -> tuple[str, Decimal | None]:
    parts = split_quarter_handicap(handicap)
    if not parts:
        return "AH_SETTLEMENT_UNCERTAIN", None
    pnl = sum(settle_ah_single(goals_for, goals_against, part) for part in parts) / Decimal(len(parts))
    return "SETTLED", pnl


def ledger_base(row: dict[str, str], market: str, selection: str) -> dict[str, str]:
    return {
        "source": row["source"],
        "market": market,
        "selection": selection,
        "league_code": row["league_code"],
        "league_name": row["league_name"],
        "season": row["season"],
        "date": row["date"],
        "home_team": row["home_team"],
        "away_team": row["away_team"],
        "full_time_result": row["full_time_result"],
        "full_time_home_goals": row["full_time_home_goals"],
        "full_time_away_goals": row["full_time_away_goals"],
        "line": "",
        "close_odds": "",
        "price_status": "PRICE_MISSING",
        "settlement_status": "DATA_MISSING",
        "hit": "",
        "pnl_proxy_flat_1u": "",
        "data_quality_flags": row.get("data_quality_flags", ""),
    }


def add_ft_over25(row: dict[str, str]) -> dict[str, str]:
    entry = ledger_base(row, "FT_OVER25", "OVER_2_5")
    home = to_int(row["full_time_home_goals"])
    away = to_int(row["full_time_away_goals"])
    odds = to_decimal(row["odds_over25_close"])
    entry["line"] = "2.5"
    if home is None or away is None:
        return entry
    hit = home + away > 2.5
    entry["settlement_status"] = "SETTLED"
    entry["hit"] = str(hit).lower()
    if odds is None:
        entry["price_status"] = "PRICE_MISSING"
        return entry
    entry["price_status"] = "REAL_CLOSE_ODDS"
    entry["close_odds"] = dec_str(odds)
    entry["pnl_proxy_flat_1u"] = dec_str(outcome_to_pnl(hit, odds))
    return entry


def add_1x2(row: dict[str, str], selection: str, odds_field: str, result_value: str) -> dict[str, str]:
    entry = ledger_base(row, "1X2", selection)
    odds = to_decimal(row[odds_field])
    result = row["full_time_result"]
    if result not in {"H", "D", "A"}:
        return entry
    hit = result == result_value
    entry["settlement_status"] = "SETTLED"
    entry["hit"] = str(hit).lower()
    if odds is None:
        entry["price_status"] = "PRICE_MISSING"
        return entry
    entry["price_status"] = "REAL_CLOSE_ODDS"
    entry["close_odds"] = dec_str(odds)
    entry["pnl_proxy_flat_1u"] = dec_str(outcome_to_pnl(hit, odds))
    return entry


def add_double_chance(row: dict[str, str], selection: str, result_values: set[str]) -> dict[str, str]:
    entry = ledger_base(row, "DOUBLE_CHANCE_PROXY", selection)
    result = row["full_time_result"]
    if result not in {"H", "D", "A"}:
        return entry
    entry["settlement_status"] = "HIT_RATE_ONLY_NO_REAL_DC_PRICE"
    entry["price_status"] = "NO_REAL_DOUBLE_CHANCE_ODDS"
    entry["hit"] = str(result in result_values).lower()
    return entry


def add_ah(row: dict[str, str], selection: str, odds_field: str, side: str) -> dict[str, str]:
    entry = ledger_base(row, "ASIAN_HANDICAP", selection)
    home = to_int(row["full_time_home_goals"])
    away = to_int(row["full_time_away_goals"])
    line = to_decimal(row["asian_handicap_line"])
    odds = to_decimal(row[odds_field])
    if line is not None:
        entry["line"] = dec_str(line)
    if home is None or away is None or line is None:
        entry["settlement_status"] = "AH_SETTLEMENT_UNCERTAIN"
        return entry
    goals_for, goals_against, handicap = (home, away, line) if side == "HOME" else (away, home, -line)
    status, unit_result = settle_ah(goals_for, goals_against, handicap)
    entry["settlement_status"] = status
    if unit_result is None:
        return entry
    entry["hit"] = "true" if unit_result > 0 else "false"
    if odds is None:
        entry["price_status"] = "PRICE_MISSING"
        return entry
    entry["price_status"] = "REAL_CLOSE_ODDS"
    entry["close_odds"] = dec_str(odds)
    if unit_result > 0:
        pnl = unit_result * (odds - Decimal("1"))
    else:
        pnl = unit_result
    entry["pnl_proxy_flat_1u"] = dec_str(pnl)
    return entry


def read_dataset() -> list[dict[str, str]]:
    with DATASET.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def build_ledger(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    for row in rows:
        entries.append(add_ft_over25(row))
        entries.append(add_1x2(row, "HOME", "odds_1x2_home_close", "H"))
        entries.append(add_1x2(row, "DRAW", "odds_1x2_draw_close", "D"))
        entries.append(add_1x2(row, "AWAY", "odds_1x2_away_close", "A"))
        entries.append(add_double_chance(row, "1X", {"H", "D"}))
        entries.append(add_double_chance(row, "X2", {"A", "D"}))
        entries.append(add_double_chance(row, "12", {"H", "A"}))
        entries.append(add_ah(row, "HOME", "asian_handicap_home_close", "HOME"))
        entries.append(add_ah(row, "AWAY", "asian_handicap_away_close", "AWAY"))
    return entries


def max_fail_streak(entries: list[dict[str, str]]) -> int:
    streak = 0
    max_streak = 0
    for entry in entries:
        if entry.get("settlement_status") != "SETTLED":
            continue
        pnl = to_decimal(entry.get("pnl_proxy_flat_1u", ""))
        if pnl is not None and pnl < 0:
            streak += 1
            max_streak = max(max_streak, streak)
        else:
            streak = 0
    return max_streak


def max_drawdown(entries: list[dict[str, str]]) -> Decimal:
    cumulative = Decimal("0")
    peak = Decimal("0")
    drawdown = Decimal("0")
    for entry in entries:
        pnl = to_decimal(entry.get("pnl_proxy_flat_1u", ""))
        if pnl is None:
            continue
        cumulative += pnl
        peak = max(peak, cumulative)
        drawdown = min(drawdown, cumulative - peak)
    return drawdown


def metric_for(market: str, entries: list[dict[str, str]]) -> dict[str, Any]:
    sample_count = len(entries)
    settled = [entry for entry in entries if entry.get("settlement_status") == "SETTLED"]
    roi_entries = [entry for entry in settled if entry.get("price_status") == "REAL_CLOSE_ODDS" and entry.get("pnl_proxy_flat_1u") != ""]
    hit_entries = [entry for entry in entries if entry.get("hit") in {"true", "false"}]
    odds_values = [to_decimal(entry.get("close_odds", "")) for entry in roi_entries]
    odds_values = [value for value in odds_values if value is not None]
    pnl_values = [to_decimal(entry.get("pnl_proxy_flat_1u", "")) for entry in roi_entries]
    pnl_values = [value for value in pnl_values if value is not None]
    status_counts = Counter(entry.get("settlement_status") or "UNKNOWN" for entry in entries)
    price_missing_count = sum(1 for entry in entries if entry.get("price_status") in {"PRICE_MISSING", "NO_REAL_DOUBLE_CHANCE_ODDS"})
    hit_count = sum(1 for entry in hit_entries if entry["hit"] == "true")
    avg_odds = sum(odds_values) / Decimal(len(odds_values)) if odds_values else None
    roi = sum(pnl_values) / Decimal(len(pnl_values)) if pnl_values else None
    return {
        "market": market,
        "sample_count": sample_count,
        "settled_count": len(settled),
        "hit_count": hit_count,
        "hit_rate": round(hit_count / len(hit_entries), 6) if hit_entries else None,
        "avg_close_odds": float(avg_odds) if avg_odds is not None else None,
        "roi_proxy_flat_1u": float(roi) if roi is not None else None,
        "max_fail_streak": max_fail_streak(roi_entries),
        "max_drawdown_proxy": float(max_drawdown(roi_entries)),
        "price_missing_count": price_missing_count,
        "settlement_uncertain_count": status_counts.get("AH_SETTLEMENT_UNCERTAIN", 0),
        "data_quality_flags": dict(sorted(Counter(entry.get("data_quality_flags") or "" for entry in entries).items())),
        "status_counts": dict(sorted(status_counts.items())),
        "roi_policy": "REAL_CLOSE_ODDS_ONLY" if market != "DOUBLE_CHANCE_PROXY" else "ROI_NOT_COMPUTED_NO_REAL_DC_PRICE",
    }


def main() -> int:
    rows = read_dataset()
    ledger = build_ledger(rows)
    markets = sorted({entry["market"] for entry in ledger})
    metrics = [metric_for(market, [entry for entry in ledger if entry["market"] == market]) for market in markets]
    seasons = sorted({row["season"] for row in rows})
    summary = {
        "schema_version": "v4_price_aware_replay_core_summary.v1",
        "generated_at": BUILD_TIMESTAMP,
        "source_dataset": str(DATASET.relative_to(ROOT)),
        "dataset_rows": len(rows),
        "ledger_rows": len(ledger),
        "seasons": seasons,
        "markets": markets,
        "metrics": metrics,
        "settlement_rules": {
            "FT_OVER25": "total_goals > 2.5, ROI uses odds_over25_close only",
            "1X2": "H/D/A settled against full_time_result, ROI uses 1X2 close odds only",
            "DOUBLE_CHANCE_PROXY": "1X/X2/12 hit-rate only; no real DC odds, no ROI",
            "ASIAN_HANDICAP": "home line from asian_handicap_line; away line is inverse; quarter lines split into two half stakes",
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
        },
    }
    with LEDGER.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=LEDGER_FIELDS)
        writer.writeheader()
        writer.writerows(ledger)
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "conclusion": "PASS",
        "dataset_rows": len(rows),
        "ledger_rows": len(ledger),
        "markets": markets,
        "summary": str(SUMMARY.relative_to(ROOT)),
        "ledger": str(LEDGER.relative_to(ROOT)),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
