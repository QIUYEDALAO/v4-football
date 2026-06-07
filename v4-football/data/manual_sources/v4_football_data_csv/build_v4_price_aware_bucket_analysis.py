#!/usr/bin/env python3
"""Build offline bucket analysis for V4 Football-Data price-aware replay."""
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
LEDGER = ROOT / "processed/v4_price_aware_replay_core_ledger.csv"
CORE_SUMMARY = ROOT / "processed/v4_price_aware_replay_core_summary.json"
OUT_CSV = ROOT / "processed/v4_price_aware_bucket_analysis.csv"
OUT_SUMMARY = ROOT / "processed/v4_price_aware_bucket_summary.json"
BUILD_TIMESTAMP = "2026-06-07T00:00:00+08:00"

BUCKET_FIELDS = [
    "market",
    "league_code",
    "season",
    "close_odds_band",
    "asian_handicap_line_bucket",
    "over25_price_band",
    "home_away_side",
    "sample_size_bucket",
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
    if not raw:
        return None
    try:
        return Decimal(raw)
    except (InvalidOperation, ValueError):
        return None


def close_odds_band(value: str) -> str:
    odds = dec(value)
    if odds is None:
        return "PRICE_MISSING"
    if odds < Decimal("1.50"):
        return "LT_1_50"
    if odds < Decimal("1.75"):
        return "1_50_1_74"
    if odds < Decimal("2.00"):
        return "1_75_1_99"
    if odds < Decimal("2.50"):
        return "2_00_2_49"
    if odds < Decimal("3.50"):
        return "2_50_3_49"
    if odds < Decimal("5.00"):
        return "3_50_4_99"
    return "GE_5_00"


def over25_price_band(row: dict[str, str]) -> str:
    if row.get("market") != "FT_OVER25":
        return "NOT_FT_OVER25"
    return close_odds_band(row.get("close_odds", ""))


def ah_line_bucket(row: dict[str, str]) -> str:
    if row.get("market") != "ASIAN_HANDICAP":
        return "NOT_AH"
    line = dec(row.get("line"))
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


def side_bucket(row: dict[str, str]) -> str:
    selection = row.get("selection", "")
    if selection in {"HOME", "AWAY"}:
        return selection
    if selection == "DRAW":
        return "DRAW"
    if selection in {"1X", "X2", "12"}:
        return selection
    return "MARKET_LEVEL"


def sample_size_bucket(sample_count: int) -> str:
    if sample_count < 100:
        return "LT_100"
    if sample_count < 300:
        return "100_299"
    if sample_count < 1000:
        return "300_999"
    return "GE_1000"


def confidence_flag(sample_count: int) -> str:
    if sample_count < 100:
        return "SMALL_SAMPLE"
    if sample_count < 300:
        return "LOW_CONFIDENCE"
    if sample_count < 1000:
        return "MEDIUM_CONFIDENCE"
    return "HIGH_CONFIDENCE"


def read_ledger() -> list[dict[str, str]]:
    with LEDGER.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def bucket_key(row: dict[str, str]) -> tuple[str, ...]:
    return (
        row["market"],
        row["league_code"],
        row["season"],
        close_odds_band(row.get("close_odds", "")),
        ah_line_bucket(row),
        over25_price_band(row),
        side_bucket(row),
    )


def max_fail_streak(entries: list[dict[str, str]]) -> int:
    streak = 0
    best = 0
    for row in entries:
        pnl = dec(row.get("pnl_proxy_flat_1u"))
        if pnl is None:
            continue
        if pnl < 0:
            streak += 1
            best = max(best, streak)
        else:
            streak = 0
    return best


def max_drawdown(entries: list[dict[str, str]]) -> Decimal:
    cumulative = Decimal("0")
    peak = Decimal("0")
    worst = Decimal("0")
    for row in entries:
        pnl = dec(row.get("pnl_proxy_flat_1u"))
        if pnl is None:
            continue
        cumulative += pnl
        peak = max(peak, cumulative)
        worst = min(worst, cumulative - peak)
    return worst


def metric_row(key: tuple[str, ...], entries: list[dict[str, str]]) -> dict[str, Any]:
    market, league, season, odds_band, ah_bucket, over_band, side = key
    sample_count = len(entries)
    settled = [row for row in entries if row.get("settlement_status") == "SETTLED"]
    hit_rows = [row for row in entries if row.get("hit") in {"true", "false"}]
    roi_rows = [
        row for row in settled
        if row.get("price_status") == "REAL_CLOSE_ODDS" and row.get("pnl_proxy_flat_1u") != ""
    ]
    hit_count = sum(1 for row in hit_rows if row.get("hit") == "true")
    odds = [dec(row.get("close_odds")) for row in roi_rows]
    odds = [value for value in odds if value is not None]
    pnls = [dec(row.get("pnl_proxy_flat_1u")) for row in roi_rows]
    pnls = [value for value in pnls if value is not None]
    roi = sum(pnls) / Decimal(len(pnls)) if pnls else None
    avg_odds = sum(odds) / Decimal(len(odds)) if odds else None
    drawdown = max_drawdown(roi_rows)
    conf = confidence_flag(sample_count)
    risk_flags: list[str] = []
    if conf == "SMALL_SAMPLE":
        risk_flags.append("SMALL_SAMPLE_NO_EDGE_CLAIM")
    if conf == "LOW_CONFIDENCE":
        risk_flags.append("LOW_CONFIDENCE_RESEARCH_ONLY")
    if roi is not None and roi > 0 and abs(drawdown) > Decimal(max(20, sample_count // 10)):
        risk_flags.append("HIGH_DRAWDOWN_RISK")
    if market == "DOUBLE_CHANCE_PROXY":
        risk_flags.append("NO_REAL_DC_ODDS")
    price_missing_count = sum(
        1 for row in entries
        if row.get("price_status") in {"PRICE_MISSING", "NO_REAL_DOUBLE_CHANCE_ODDS"}
    )
    uncertain_count = sum(1 for row in entries if row.get("settlement_status") == "AH_SETTLEMENT_UNCERTAIN")
    return {
        "market": market,
        "league_code": league,
        "season": season,
        "close_odds_band": odds_band,
        "asian_handicap_line_bucket": ah_bucket,
        "over25_price_band": over_band,
        "home_away_side": side,
        "sample_size_bucket": sample_size_bucket(sample_count),
        "sample_count": sample_count,
        "settled_count": len(settled),
        "hit_count": hit_count,
        "hit_rate": round(hit_count / len(hit_rows), 6) if hit_rows else "",
        "avg_close_odds": round(float(avg_odds), 6) if avg_odds is not None else "",
        "roi_proxy_flat_1u": "" if market == "DOUBLE_CHANCE_PROXY" or roi is None else round(float(roi), 6),
        "max_fail_streak": max_fail_streak(roi_rows),
        "max_drawdown_proxy": "" if market == "DOUBLE_CHANCE_PROXY" else round(float(drawdown), 6),
        "price_missing_count": price_missing_count,
        "settlement_uncertain_count": uncertain_count,
        "confidence_flag": conf,
        "risk_flags": "|".join(risk_flags or ["RESEARCH_ONLY_NO_EDGE_CLAIM"]),
    }


def build() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    ledger = read_ledger()
    grouped: dict[tuple[str, ...], list[dict[str, str]]] = defaultdict(list)
    for row in ledger:
        grouped[bucket_key(row)].append(row)
    rows = [metric_row(key, entries) for key, entries in sorted(grouped.items())]
    market_counts = Counter(row["market"] for row in ledger)
    confidence_counts = Counter(row["confidence_flag"] for row in rows)
    positive_roi = [
        row for row in rows
        if row["roi_proxy_flat_1u"] != "" and float(row["roi_proxy_flat_1u"]) > 0
    ]
    risky_positive = [row for row in positive_roi if "HIGH_DRAWDOWN_RISK" in row["risk_flags"]]
    summary = {
        "schema_version": "v4_price_aware_bucket_summary.v1",
        "generated_at": BUILD_TIMESTAMP,
        "source_ledger": str(LEDGER.relative_to(ROOT)),
        "ledger_rows": len(ledger),
        "bucket_rows": len(rows),
        "markets": dict(sorted(market_counts.items())),
        "bucket_dimensions": [
            "market",
            "league_code",
            "season",
            "close_odds_band",
            "asian_handicap_line_bucket",
            "over25_price_band",
            "home_away_side",
            "sample_size_bucket",
        ],
        "confidence_counts": dict(sorted(confidence_counts.items())),
        "positive_roi_bucket_count": len(positive_roi),
        "positive_roi_high_drawdown_risk_count": len(risky_positive),
        "top_research_candidates": sorted(
            [
                row for row in rows
                if row["confidence_flag"] in {"MEDIUM_CONFIDENCE", "HIGH_CONFIDENCE"}
                and row["roi_proxy_flat_1u"] != ""
                and float(row["roi_proxy_flat_1u"]) > 0
            ],
            key=lambda row: (float(row["roi_proxy_flat_1u"]), int(row["sample_count"])),
            reverse=True,
        )[:20],
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
    return rows, summary


def main() -> int:
    rows, summary = build()
    with OUT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=BUCKET_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    OUT_SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "conclusion": "PASS",
        "bucket_rows": len(rows),
        "summary": str(OUT_SUMMARY.relative_to(ROOT)),
        "csv": str(OUT_CSV.relative_to(ROOT)),
        "confidence_counts": summary["confidence_counts"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
