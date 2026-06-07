#!/usr/bin/env python3
"""Audit positive ROI buckets from the V4 context-aware replay output."""
from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import build_v4_context_aware_replay as context_replay  # noqa: E402


CONTEXT_CSV = ROOT / "processed/v4_context_aware_replay.csv"
CONTEXT_SUMMARY = ROOT / "processed/v4_context_aware_replay_summary.json"
OUT_JSON = ROOT / "processed/v4_context_positive_bucket_explanation_audit.json"
OUT_MD = ROOT / "processed/v4_context_positive_bucket_explanation_audit.md"
BUILD_TIMESTAMP = "2026-06-07T00:00:00+08:00"


def read_context_rows() -> list[dict[str, str]]:
    with CONTEXT_CSV.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def as_float(value: str) -> float | None:
    if value == "":
        return None
    return float(value)


def matching_entries(bucket: dict[str, str]) -> list[dict[str, Any]]:
    rows = context_replay.read_rows()
    matches: list[dict[str, Any]] = []
    for row in rows:
        if bucket["market"] == "FT_OVER25":
            contexts = context_replay.ft_contexts(row)
            if (bucket["context_filter"], bucket["context_value"]) not in contexts:
                continue
            home_goals = context_replay.int_value(row["full_time_home_goals"])
            away_goals = context_replay.int_value(row["full_time_away_goals"])
            if home_goals is None or away_goals is None:
                continue
            hit = home_goals + away_goals > 2.5
            odds = context_replay.dec(row["odds_over25_close"])
            pnl = context_replay.outcome_pnl(hit, odds)
            matches.append({**row, "side": "OVER_2_5", "hit": hit, "odds": odds, "pnl": pnl})
        if bucket["market"] == "ASIAN_HANDICAP":
            for side in ["HOME", "AWAY"]:
                contexts = context_replay.ah_contexts(row, side)
                if (bucket["context_filter"], bucket["context_value"]) not in contexts:
                    continue
                status, unit = context_replay.ah_unit_result(row, side)
                odds = context_replay.dec(row["asian_handicap_home_close" if side == "HOME" else "asian_handicap_away_close"])
                pnl = None
                hit = False
                if status == "SETTLED" and unit is not None:
                    hit = unit > 0
                    if odds is not None:
                        pnl = unit * (odds - Decimal("1")) if unit > 0 else unit
                matches.append({**row, "side": side, "hit": hit, "odds": odds, "pnl": pnl})
    return matches


def distribution(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    return dict(sorted(Counter(str(row[field]) for row in rows).items()))


def share_largest(counts: dict[str, int], total: int) -> float:
    if total == 0 or not counts:
        return 0.0
    return max(counts.values()) / total


def classify(bucket: dict[str, str], rows: list[dict[str, Any]], league_dist: dict[str, int], season_dist: dict[str, int], early_share: float) -> list[str]:
    flags: list[str] = []
    sample_count = int(bucket["sample_count"])
    drawdown = abs(float(bucket["max_drawdown_proxy"])) if bucket["max_drawdown_proxy"] else 0.0
    if share_largest(league_dist, sample_count) >= 0.70 or share_largest(season_dist, sample_count) >= 0.70:
        flags.append("SINGLE_CLUSTER_RISK")
    if early_share >= 0.25:
        flags.append("EARLY_SEASON_RISK")
    if sample_count < 1000:
        flags.append("NOT_HIGH_CONFIDENCE")
    if drawdown > max(30.0, sample_count * 0.20):
        flags.append("HIGH_DRAWDOWN_RISK")
    if len(league_dist) < 2 or len(season_dist) < 2:
        flags.append("STRUCTURAL_NOISE")
    if not flags:
        flags.append("RESEARCH_ONLY_UNCONFIRMED")
    return flags


def audit_bucket(bucket: dict[str, str]) -> dict[str, Any]:
    rows = matching_entries(bucket)
    league_dist = distribution(rows, "league_code")
    season_dist = distribution(rows, "season")
    early_count = sum("EARLY_SEASON_INSUFFICIENT" in row["team_strength_context_flags"] for row in rows)
    early_share = round(early_count / len(rows), 6) if rows else 0.0
    price_moves = Counter(row["price_move_direction_flag"] for row in rows)
    strength_context = {
        "rank_gap_bucket": distribution([row for row in rows if row.get("rank_gap") is not None], "rank_gap"),
        "points_gap_bucket": distribution([row for row in rows if row.get("points_gap") is not None], "points_gap"),
        "recent_5_points_gap_bucket": distribution([row for row in rows if row.get("recent_5_points_gap") is not None], "recent_5_points_gap"),
    }
    return {
        "market": bucket["market"],
        "context_filter": bucket["context_filter"],
        "context_value": bucket["context_value"],
        "sample_count": int(bucket["sample_count"]),
        "hit_rate": as_float(bucket["hit_rate"]),
        "avg_close_odds": as_float(bucket["avg_close_odds"]),
        "roi_proxy_flat_1u": as_float(bucket["roi_proxy_flat_1u"]),
        "max_fail_streak": int(bucket["max_fail_streak"]),
        "max_drawdown_proxy": as_float(bucket["max_drawdown_proxy"]),
        "confidence_flag": bucket["confidence_flag"],
        "league_distribution": league_dist,
        "season_distribution": season_dist,
        "early_season_share": early_share,
        "price_move_direction": dict(sorted(price_moves.items())),
        "strength_context": strength_context,
        "risk_flags": sorted(set(bucket["risk_flags"].split("|") + classify(bucket, rows, league_dist, season_dist, early_share))),
        "online_policy": "NO_ONLINE_ACTION_RESEARCH_ONLY",
    }


def build() -> dict[str, Any]:
    context_summary = load_json(CONTEXT_SUMMARY)
    context_rows = read_context_rows()
    positive = [row for row in context_rows if row["roi_proxy_flat_1u"] and float(row["roi_proxy_flat_1u"]) > 0]
    audits = [audit_bucket(row) for row in positive]
    return {
        "schema_version": "v4_context_positive_bucket_explanation_audit.v1",
        "generated_at": BUILD_TIMESTAMP,
        "source_context_csv": str(CONTEXT_CSV.relative_to(ROOT)),
        "source_context_summary": str(CONTEXT_SUMMARY.relative_to(ROOT)),
        "context_bucket_count": context_summary.get("context_bucket_count"),
        "positive_roi_bucket_count": len(positive),
        "research_candidate_count": context_summary.get("research_candidate_count"),
        "markets": context_summary.get("markets"),
        "audited_buckets": audits,
        "classification_summary": dict(sorted(Counter(flag for row in audits for flag in row["risk_flags"]).items())),
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


def write_markdown(result: dict[str, Any]) -> None:
    lines = [
        "# V4 Context Positive Bucket Explanation Audit",
        "",
        "## Scope",
        "",
        "Offline explanation audit for positive ROI context buckets. This audit is research-only and has no online action.",
        "",
        "## Summary",
        "",
        f"- context_bucket_count: {result['context_bucket_count']}",
        f"- positive_roi_bucket_count: {result['positive_roi_bucket_count']}",
        f"- research_candidate_count: {result['research_candidate_count']}",
        "",
        "## Audited Buckets",
        "",
    ]
    for idx, bucket in enumerate(result["audited_buckets"], start=1):
        lines.extend([
            f"### Bucket {idx}",
            "",
            f"- market: {bucket['market']}",
            f"- context_filter: {bucket['context_filter']}",
            f"- context_value: {bucket['context_value']}",
            f"- sample_count: {bucket['sample_count']}",
            f"- hit_rate: {bucket['hit_rate']}",
            f"- roi_proxy_flat_1u: {bucket['roi_proxy_flat_1u']}",
            f"- max_drawdown_proxy: {bucket['max_drawdown_proxy']}",
            f"- early_season_share: {bucket['early_season_share']}",
            f"- risk_flags: {', '.join(bucket['risk_flags'])}",
            "",
        ])
    lines.extend([
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
        "positive_roi_bucket_count": result["positive_roi_bucket_count"],
        "research_candidate_count": result["research_candidate_count"],
        "classification_summary": result["classification_summary"],
        "json": str(OUT_JSON.relative_to(ROOT)),
        "md": str(OUT_MD.relative_to(ROOT)),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
