#!/usr/bin/env python3
"""Build expanded V4 market strategy card replay ledger from local artifacts."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.build_v4_five_dimension_lite import sample_from_row, source_rows
from tools.build_v4_market_strategy_research_cards import ALLOWED_CONCLUSIONS, card_from_five_dimension
from tools.build_v4_market_strategy_card_replay_ledger import result_fields, validation_index


SCHEMA = ROOT / "config/v4_market_strategy_card_replay_expansion_schema.json"
OUT_DIR = ROOT / "data/manual_sources/v4/market_strategy_replay"
OUT_LEDGER = OUT_DIR / "v4_market_strategy_card_replay_expansion_20260607.json"
OUT_SUMMARY = OUT_DIR / "v4_market_strategy_card_replay_expansion_summary_20260607.json"
BUILD_TIMESTAMP = "2026-06-07T00:00:00+08:00"
GAP_TAGS = ["PRICE_MISSING", "LINE_MISSING", "MARKET_MISSING", "DATA_INSUFFICIENT"]


def direction_names(card: dict[str, Any]) -> list[str]:
    return [
        str(row.get("direction"))
        for row in card.get("strategy_directions", [])
        if isinstance(row, dict) and row.get("direction")
    ]


def status_fields(card: dict[str, Any]) -> dict[str, str]:
    missing = set(card.get("missing_context") or [])
    market = card.get("market_confirmation_readout") or {}
    return {
        "price_status": "PRICE_MISSING" if "PRICE_MISSING" in missing else str(market.get("price_status") or "UNKNOWN"),
        "line_status": "LINE_MISSING" if "LINE_MISSING" in missing else "LINE_PRESENT",
        "market_status": "MARKET_MISSING" if "MARKET_MISSING" in missing else "MARKET_PRESENT",
    }


def expanded_cards() -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row, path in source_rows():
        fixture_id = str(row.get("fixture_id") or "")
        if not fixture_id or fixture_id in seen:
            continue
        seen.add(fixture_id)
        five = sample_from_row(row, path)
        cards.append(card_from_five_dimension(five))
    return cards


def ledger_row(card: dict[str, Any], results: dict[str, dict[str, Any]]) -> dict[str, Any]:
    missing = list(card.get("missing_context") or [])
    result = result_fields(card, results)
    return {
        "fixture_id": (card.get("match_info") or {}).get("fixture_id"),
        "match_info": card.get("match_info") or {},
        "league_admission_status": card.get("league_admission_status") or {},
        "strategy_card_conclusion": card.get("conclusion"),
        "strategy_directions": direction_names(card),
        "missing_context": missing,
        **status_fields(card),
        **result,
        "edge_inference": "NOT_EVALUATED",
        "source_artifact": card.get("source_artifact"),
        "policy_lock": {
            "research_only": True,
            "official_grade_changed": False,
            "pending_written": False,
            "qq_sent": False,
            "cron_or_launchd_modified": False,
            "realtime_reminder": False,
            "b_realtime_restored": False,
            "rf_shadow_promotion_released": False,
        },
    }


def coverage_by_conclusion(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    coverage: dict[str, dict[str, Any]] = {}
    for conclusion in ALLOWED_CONCLUSIONS:
        bucket = [row for row in rows if row.get("strategy_card_conclusion") == conclusion]
        available = [row for row in bucket if row.get("result_available") is True]
        hit_count = sum(1 for row in available if row.get("result_hit") is True)
        coverage[conclusion] = {
            "sample_count": len(bucket),
            "result_available_count": len(available),
            "result_missing_count": len(bucket) - len(available),
            "hit_count": hit_count,
            "hit_rate": round(hit_count / len(available), 4) if available else None,
            "hit_rate_policy": "EXCLUDES_RESULT_MISSING" if available else "NOT_COMPUTED_RESULT_MISSING_OR_EMPTY",
        }
    return coverage


def gap_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {
        tag: sum(1 for row in rows if tag in set(row.get("missing_context") or []))
        for tag in GAP_TAGS
    }


def observe_blockers(rows: list[dict[str, Any]]) -> dict[str, int]:
    blockers: dict[str, int] = {}
    for row in rows:
        if row.get("strategy_card_conclusion") == "OBSERVE":
            continue
        for tag in row.get("missing_context") or []:
            blockers[str(tag)] = blockers.get(str(tag), 0) + 1
    return dict(sorted(blockers.items(), key=lambda item: (-item[1], item[0])))


def main() -> int:
    results = validation_index()
    cards = expanded_cards()
    rows = [ledger_row(card, results) for card in cards]
    conclusion_counts = {label: sum(1 for row in rows if row.get("strategy_card_conclusion") == label) for label in ALLOWED_CONCLUSIONS}
    observe_count = conclusion_counts.get("OBSERVE", 0)
    warn_only: list[str] = []
    if observe_count < 10:
        warn_only.append("OBSERVE_SAMPLE_INSUFFICIENT")
    if any(row.get("result_available") is not True for row in rows):
        warn_only.append("RESULT_COVERAGE_PARTIAL")
    summary = {
        "schema_version": "v4_market_strategy_card_replay_expansion_summary.v1",
        "generated_at": BUILD_TIMESTAMP,
        "sample_count": len(rows),
        "source_unique_fixture_count": len(rows),
        "conclusion_distribution": conclusion_counts,
        "result_coverage": coverage_by_conclusion(rows),
        "missing_context_summary": gap_counts(rows),
        "observe_sample_sufficient": observe_count >= 10,
        "observe_blockers": observe_blockers(rows),
        "next_stage_research_status": "WAIT_SAMPLE_INSUFFICIENT" if warn_only else "READY_FOR_REVIEW",
        "warn_only": sorted(set(warn_only)),
        "policy_lock": {
            "official_grade_changed": False,
            "ab_threshold_changed": False,
            "pending_written": False,
            "qq_sent": False,
            "cron_or_launchd_modified": False,
            "b_realtime_restored": False,
            "rf_shadow_promotion_released": False,
            "live_api_called": False,
        },
    }
    payload = {
        "schema_version": "v4_market_strategy_card_replay_expansion.v1",
        "generated_at": BUILD_TIMESTAMP,
        "schema_ref": str(SCHEMA.relative_to(ROOT)),
        "source_policy": "existing_local_artifacts_only",
        "live_api_called": False,
        "records": rows,
        "summary": summary,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_LEDGER.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    OUT_SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "conclusion": "PASS",
        "ledger": str(OUT_LEDGER.relative_to(ROOT)),
        "summary": str(OUT_SUMMARY.relative_to(ROOT)),
        "sample_count": len(rows),
        "conclusion_distribution": conclusion_counts,
        "warn_only": summary["warn_only"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
