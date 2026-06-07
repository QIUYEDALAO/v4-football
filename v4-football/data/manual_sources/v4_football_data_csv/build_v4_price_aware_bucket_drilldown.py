#!/usr/bin/env python3
"""Build offline drilldown for V4 price-aware bucket analysis."""
from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
BUCKET_CSV = ROOT / "processed/v4_price_aware_bucket_analysis.csv"
BUCKET_SUMMARY = ROOT / "processed/v4_price_aware_bucket_summary.json"
OUT_JSON = ROOT / "processed/v4_price_aware_bucket_drilldown.json"
OUT_MD = ROOT / "processed/v4_price_aware_bucket_drilldown.md"
BUILD_TIMESTAMP = "2026-06-07T00:00:00+08:00"

PRIMARY_MARKETS = {"ASIAN_HANDICAP", "FT_OVER25"}
SECONDARY_MARKETS = {"1X2"}
DC_MARKET = "DOUBLE_CHANCE_PROXY"


def read_rows() -> list[dict[str, str]]:
    with BUCKET_CSV.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def load_summary() -> dict[str, Any]:
    return json.loads(BUCKET_SUMMARY.read_text(encoding="utf-8"))


def as_float(value: str) -> float | None:
    if value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def as_int(value: str) -> int:
    return int(value or 0)


def similar_direction_key(row: dict[str, str]) -> tuple[str, str, str, str]:
    return (
        row["market"],
        row["close_odds_band"],
        row["asian_handicap_line_bucket"],
        row["home_away_side"],
    )


def peer_support(row: dict[str, str], rows: list[dict[str, str]]) -> dict[str, Any]:
    key = similar_direction_key(row)
    peers = [
        peer for peer in rows
        if similar_direction_key(peer) == key
        and peer["confidence_flag"] in {"LOW_CONFIDENCE", "MEDIUM_CONFIDENCE"}
        and as_float(peer["roi_proxy_flat_1u"]) is not None
        and as_float(peer["roi_proxy_flat_1u"]) > 0
    ]
    return {
        "positive_peer_count": len(peers),
        "season_count": len({peer["season"] for peer in peers}),
        "league_count": len({peer["league_code"] for peer in peers}),
    }


def drawdown_too_large(row: dict[str, str]) -> bool:
    drawdown = as_float(row["max_drawdown_proxy"])
    if drawdown is None:
        return False
    sample_count = as_int(row["sample_count"])
    return abs(drawdown) > max(30.0, sample_count * 0.20)


def fail_streak_extreme(row: dict[str, str]) -> bool:
    return as_int(row["max_fail_streak"]) > 12


def candidate_reason(row: dict[str, str], rows: list[dict[str, str]]) -> str | None:
    roi = as_float(row["roi_proxy_flat_1u"])
    support = peer_support(row, rows)
    if row["market"] not in PRIMARY_MARKETS:
        return "NOT_PRIMARY_MARKET"
    if row["confidence_flag"] != "MEDIUM_CONFIDENCE":
        return f"{row['confidence_flag']}_NOT_CANDIDATE"
    if as_int(row["sample_count"]) < 300:
        return "SAMPLE_BELOW_300"
    if roi is None or roi <= 0:
        return "ROI_NOT_POSITIVE"
    if "HIGH_DRAWDOWN_RISK" in row["risk_flags"] or drawdown_too_large(row):
        return "HIGH_DRAWDOWN_RISK"
    if fail_streak_extreme(row):
        return "EXTREME_FAIL_STREAK"
    if support["season_count"] < 2 and support["league_count"] < 2:
        return "NO_CROSS_SEASON_OR_LEAGUE_SUPPORT"
    return None


def compact_row(row: dict[str, str], rows: list[dict[str, str]]) -> dict[str, Any]:
    support = peer_support(row, rows)
    return {
        "market": row["market"],
        "league_code": row["league_code"],
        "season": row["season"],
        "close_odds_band": row["close_odds_band"],
        "asian_handicap_line_bucket": row["asian_handicap_line_bucket"],
        "over25_price_band": row["over25_price_band"],
        "home_away_side": row["home_away_side"],
        "sample_count": as_int(row["sample_count"]),
        "hit_rate": as_float(row["hit_rate"]),
        "avg_close_odds": as_float(row["avg_close_odds"]),
        "roi_proxy_flat_1u": as_float(row["roi_proxy_flat_1u"]),
        "max_fail_streak": as_int(row["max_fail_streak"]),
        "max_drawdown_proxy": as_float(row["max_drawdown_proxy"]),
        "confidence_flag": row["confidence_flag"],
        "risk_flags": row["risk_flags"].split("|") if row["risk_flags"] else [],
        "peer_support": support,
    }


def build() -> dict[str, Any]:
    rows = read_rows()
    summary = load_summary()
    confidence_counts = Counter(row["confidence_flag"] for row in rows)
    candidates: list[dict[str, Any]] = []
    watchlist: list[dict[str, Any]] = []
    exclusions: list[dict[str, Any]] = []
    for row in rows:
        roi = as_float(row["roi_proxy_flat_1u"])
        reason = candidate_reason(row, rows)
        if reason is None:
            candidates.append({**compact_row(row, rows), "status": "RESEARCH_CANDIDATE"})
            continue
        if (
            row["confidence_flag"] == "LOW_CONFIDENCE"
            and row["market"] in PRIMARY_MARKETS
            and roi is not None
            and roi > 0
            and "HIGH_DRAWDOWN_RISK" not in row["risk_flags"]
        ):
            watchlist.append({**compact_row(row, rows), "status": "WATCHLIST_ONLY", "not_candidate_reason": reason})
            continue
        if (
            row["confidence_flag"] == "MEDIUM_CONFIDENCE"
            and row["market"] in PRIMARY_MARKETS | SECONDARY_MARKETS
        ):
            exclusions.append({**compact_row(row, rows), "status": "EXCLUDED", "exclude_reason": reason})
    exclusions.extend(
        {**compact_row(row, rows), "status": "EXCLUDED", "exclude_reason": "SMALL_SAMPLE"}
        for row in rows
        if row["confidence_flag"] == "SMALL_SAMPLE"
    )
    dc_rows = [row for row in rows if row["market"] == DC_MARKET]
    result = {
        "schema_version": "v4_price_aware_bucket_drilldown.v1",
        "generated_at": BUILD_TIMESTAMP,
        "source_bucket_summary": str(BUCKET_SUMMARY.relative_to(ROOT)),
        "source_bucket_csv": str(BUCKET_CSV.relative_to(ROOT)),
        "input_bucket_rows": len(rows),
        "input_confidence_counts": dict(sorted(confidence_counts.items())),
        "source_top_research_candidates_count": len(summary.get("top_research_candidates", [])),
        "drilldown_focus": {
            "primary": ["ASIAN_HANDICAP", "FT_OVER25"],
            "secondary": ["1X2"],
            "hit_rate_only": ["DOUBLE_CHANCE_PROXY"],
        },
        "candidate_rules": {
            "confidence": "MEDIUM_CONFIDENCE_ONLY",
            "sample_count_min": 300,
            "roi_proxy_flat_1u": "POSITIVE_REQUIRED",
            "cross_support": "AT_LEAST_2_SEASONS_OR_2_LEAGUES_WITH_SIMILAR_POSITIVE_DIRECTION",
            "drawdown": "HIGH_DRAWDOWN_RISK_EXCLUDED",
            "fail_streak": "EXTREME_FAIL_STREAK_EXCLUDED",
        },
        "candidates": sorted(candidates, key=lambda row: row["roi_proxy_flat_1u"] or 0, reverse=True),
        "watchlist": sorted(watchlist, key=lambda row: row["roi_proxy_flat_1u"] or 0, reverse=True)[:50],
        "exclusions_sample": sorted(
            exclusions,
            key=lambda row: (row["confidence_flag"], row.get("exclude_reason", ""), row["market"]),
        )[:200],
        "exclusion_counts": {
            "small_sample": sum(1 for row in rows if row["confidence_flag"] == "SMALL_SAMPLE"),
            "low_confidence_not_candidate": sum(1 for row in rows if row["confidence_flag"] == "LOW_CONFIDENCE"),
            "medium_roi_not_positive": sum(
                1 for row in rows
                if row["confidence_flag"] == "MEDIUM_CONFIDENCE"
                and (as_float(row["roi_proxy_flat_1u"]) is None or as_float(row["roi_proxy_flat_1u"]) <= 0)
            ),
            "high_drawdown_risk": sum(1 for row in rows if "HIGH_DRAWDOWN_RISK" in row["risk_flags"]),
            "double_chance_no_real_roi": len(dc_rows),
        },
        "double_chance_policy": {
            "roi_proxy_flat_1u": None,
            "reason": "NO_REAL_DC_ODDS",
            "row_count": len(dc_rows),
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
    return result


def write_markdown(result: dict[str, Any]) -> None:
    lines = [
        "# V4 Price-Aware Bucket Drilldown",
        "",
        "## Scope",
        "",
        "Offline drilldown of MEDIUM_CONFIDENCE and LOW_CONFIDENCE buckets from Football-Data price-aware replay. This is research-only and is not connected to V4 production.",
        "",
        "## Input Summary",
        "",
        f"- bucket_rows: {result['input_bucket_rows']}",
        f"- confidence_counts: {result['input_confidence_counts']}",
        f"- source_top_research_candidates_count: {result['source_top_research_candidates_count']}",
        "",
        "## Candidate Result",
        "",
        f"- research_candidate_count: {len(result['candidates'])}",
        f"- watchlist_count: {len(result['watchlist'])}",
        "",
        "No bucket is promoted from small sample or low confidence. Double Chance proxy has no real price and no ROI.",
        "",
        "## Exclusion Counts",
        "",
    ]
    for key, value in result["exclusion_counts"].items():
        lines.append(f"- {key}: {value}")
    lines.extend([
        "",
        "## Safety Lock",
        "",
        "- api_football_called=false",
        "- v4_scan_executed=false",
        "- official_grade_changed=false",
        "- pending_written=false",
        "- qq_sent=false",
        "- cron_or_launchd_modified=false",
        "- strategy_online=false",
        "- recommendation_generated=false",
        "- edge_claim_generated=false",
    ])
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    result = build()
    OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(result)
    print(json.dumps({
        "conclusion": "PASS",
        "candidate_count": len(result["candidates"]),
        "watchlist_count": len(result["watchlist"]),
        "exclusion_counts": result["exclusion_counts"],
        "json": str(OUT_JSON.relative_to(ROOT)),
        "md": str(OUT_MD.relative_to(ROOT)),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
