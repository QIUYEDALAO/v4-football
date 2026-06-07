#!/usr/bin/env python3
"""Build strict-filter context replay for FT Over 2.5 and Asian Handicap."""
from __future__ import annotations

import csv
import json
import sys
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import build_v4_context_aware_replay as context_replay  # noqa: E402


DATASET = ROOT / "processed/v4_replay_feature_enriched_dataset.csv"
AUDIT_JSON = ROOT / "processed/v4_context_positive_bucket_explanation_audit.json"
OUT_CSV = ROOT / "processed/v4_context_strict_filter_replay.csv"
OUT_SUMMARY = ROOT / "processed/v4_context_strict_filter_replay_summary.json"
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
    "confidence_flag",
    "risk_flags",
    "candidate_status",
    "excluded_reason",
]


def read_rows() -> list[dict[str, str]]:
    with DATASET.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def strict_confidence(sample_count: int) -> str:
    if sample_count < 300:
        return "SMALL_SAMPLE"
    if sample_count < 1000:
        return "MEDIUM_RESEARCH_ONLY"
    return "HIGH_CONFIDENCE"


def max_fail_streak(entries: list[dict[str, Any]]) -> int:
    streak = 0
    best = 0
    for row in entries:
        pnl = row["pnl"]
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
        cumulative += row["pnl"]
        peak = max(peak, cumulative)
        worst = min(worst, cumulative - peak)
    return worst


def share_largest(values: list[str]) -> float:
    if not values:
        return 0.0
    counts = Counter(values)
    return max(counts.values()) / len(values)


def single_cluster(entries: list[dict[str, Any]]) -> bool:
    return share_largest([row["league_code"] for row in entries]) >= 0.70 or share_largest([row["season"] for row in entries]) >= 0.70


def strict_grouped_entries(rows: list[dict[str, str]]) -> tuple[dict[tuple[str, str, str], list[dict[str, Any]]], Counter[str]]:
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    excluded: Counter[str] = Counter()
    for row in rows:
        if "EARLY_SEASON_INSUFFICIENT" in row["team_strength_context_flags"]:
            excluded["EARLY_SEASON_INSUFFICIENT"] += 3
            continue
        home_goals = context_replay.int_value(row["full_time_home_goals"])
        away_goals = context_replay.int_value(row["full_time_away_goals"])
        if home_goals is None or away_goals is None:
            excluded["RESULT_MISSING"] += 3
            continue

        over_odds = context_replay.dec(row["odds_over25_close"])
        over_open = context_replay.dec(row["odds_over25_open"])
        if over_odds is None or over_open is None:
            excluded["FT_OVER25_PRICE_MOVEMENT_MISSING"] += 1
        else:
            hit = home_goals + away_goals > 2.5
            pnl = context_replay.outcome_pnl(hit, over_odds)
            entry = {
                "hit": hit,
                "odds": over_odds,
                "pnl": pnl,
                "league_code": row["league_code"],
                "season": row["season"],
            }
            for context_filter, context_value in context_replay.ft_contexts(row):
                if context_filter != "early_season_status":
                    grouped[("FT_OVER25", context_filter, context_value)].append(entry)

        line = context_replay.dec(row["asian_handicap_line"])
        if line is None:
            excluded["AH_LINE_MISSING"] += 2
            continue
        for side in ["HOME", "AWAY"]:
            odds_field = "asian_handicap_home_close" if side == "HOME" else "asian_handicap_away_close"
            open_field = "asian_handicap_home_open" if side == "HOME" else "asian_handicap_away_open"
            odds = context_replay.dec(row[odds_field])
            open_odds = context_replay.dec(row[open_field])
            if odds is None or open_odds is None:
                excluded[f"AH_{side}_PRICE_MOVEMENT_MISSING"] += 1
                continue
            status, unit = context_replay.ah_unit_result(row, side)
            if status != "SETTLED" or unit is None:
                excluded[f"AH_{side}_SETTLEMENT_UNCERTAIN"] += 1
                continue
            pnl = unit * (odds - Decimal("1")) if unit > 0 else unit
            entry = {
                "hit": unit > 0,
                "odds": odds,
                "pnl": pnl,
                "league_code": row["league_code"],
                "season": row["season"],
            }
            for context_filter, context_value in context_replay.ah_contexts(row, side):
                if context_filter != "early_season_status":
                    grouped[("ASIAN_HANDICAP", context_filter, context_value)].append(entry)
    return grouped, excluded


def metric_row(key: tuple[str, str, str], entries: list[dict[str, Any]]) -> dict[str, Any]:
    market, context_filter, context_value = key
    sample_count = len(entries)
    hit_count = sum(1 for row in entries if row["hit"])
    odds = [row["odds"] for row in entries]
    pnls = [row["pnl"] for row in entries]
    roi = sum(pnls) / Decimal(len(pnls)) if pnls else None
    avg_odds = sum(odds) / Decimal(len(odds)) if odds else None
    drawdown = max_drawdown(entries)
    conf = strict_confidence(sample_count)
    reasons: list[str] = []
    flags: list[str] = ["STRICT_FILTER_RESEARCH_ONLY"]
    if sample_count < 300:
        reasons.append("SMALL_SAMPLE")
        flags.append("SMALL_SAMPLE_EXCLUDED")
    if conf != "HIGH_CONFIDENCE":
        reasons.append("LOW_CONFIDENCE")
    if single_cluster(entries):
        reasons.append("SINGLE_CLUSTER_RISK")
        flags.append("SINGLE_CLUSTER_RISK")
    if roi is not None and roi > 0 and abs(drawdown) > Decimal(max(30, sample_count // 8)):
        reasons.append("HIGH_DRAWDOWN_RISK")
        flags.append("HIGH_DRAWDOWN_RISK")
    if roi is not None and roi <= 0:
        reasons.append("ROI_NOT_POSITIVE")
    candidate = sample_count >= 1000 and roi is not None and roi > 0 and not reasons
    if candidate:
        flags.append("STRICT_RESEARCH_CANDIDATE")
    return {
        "market": market,
        "context_filter": context_filter,
        "context_value": context_value,
        "sample_count": sample_count,
        "settled_count": sample_count,
        "hit_count": hit_count,
        "hit_rate": round(hit_count / sample_count, 6) if sample_count else "",
        "avg_close_odds": round(float(avg_odds), 6) if avg_odds is not None else "",
        "roi_proxy_flat_1u": round(float(roi), 6) if roi is not None else "",
        "max_fail_streak": max_fail_streak(entries),
        "max_drawdown_proxy": round(float(drawdown), 6) if entries else "",
        "confidence_flag": conf,
        "risk_flags": "|".join(sorted(set(flags))),
        "candidate_status": "STRICT_RESEARCH_CANDIDATE" if candidate else "EXCLUDED",
        "excluded_reason": "|".join(sorted(set(reasons))) if reasons else "",
    }


def build() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    audit = load_json(AUDIT_JSON)
    rows = read_rows()
    grouped, row_excluded = strict_grouped_entries(rows)
    metrics = [metric_row(key, entries) for key, entries in sorted(grouped.items())]
    candidates = [row for row in metrics if row["candidate_status"] == "STRICT_RESEARCH_CANDIDATE"]
    excluded_reasons = Counter()
    for row in metrics:
        for reason in row["excluded_reason"].split("|"):
            if reason:
                excluded_reasons[reason] += 1
    summary = {
        "schema_version": "v4_context_strict_filter_replay_summary.v1",
        "generated_at": BUILD_TIMESTAMP,
        "source_dataset": str(DATASET.relative_to(ROOT)),
        "source_positive_bucket_audit": str(AUDIT_JSON.relative_to(ROOT)),
        "positive_bucket_audit": {
            "positive_roi_bucket_count": audit.get("positive_roi_bucket_count"),
            "research_candidate_count": audit.get("research_candidate_count"),
            "classification_summary": audit.get("classification_summary"),
        },
        "strict_filters": [
            "exclude sample_count < 300 from candidates",
            "exclude EARLY_SEASON_INSUFFICIENT rows",
            "exclude SINGLE_CLUSTER_RISK buckets",
            "exclude HIGH_DRAWDOWN_RISK buckets",
            "exclude LOW_CONFIDENCE buckets",
            "exclude missing price/line/market rows",
        ],
        "total_buckets_after_filter": len(metrics),
        "positive_roi_buckets_after_filter": sum(1 for row in metrics if row["roi_proxy_flat_1u"] != "" and row["roi_proxy_flat_1u"] > 0),
        "research_candidate_count": len(candidates),
        "research_candidates": candidates,
        "confidence_counts": dict(sorted(Counter(row["confidence_flag"] for row in metrics).items())),
        "row_excluded_reason_counts": dict(sorted(row_excluded.items())),
        "bucket_excluded_reason_counts": dict(sorted(excluded_reasons.items())),
        "markets": sorted({row["market"] for row in metrics}),
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
        "total_buckets_after_filter": summary["total_buckets_after_filter"],
        "positive_roi_buckets_after_filter": summary["positive_roi_buckets_after_filter"],
        "research_candidate_count": summary["research_candidate_count"],
        "output": str(OUT_CSV.relative_to(ROOT)),
        "summary": str(OUT_SUMMARY.relative_to(ROOT)),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
