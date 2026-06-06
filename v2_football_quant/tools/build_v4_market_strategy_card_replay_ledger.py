#!/usr/bin/env python3
"""Build a read-only replay ledger for V4 market strategy research cards."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "config/v4_market_strategy_card_replay_ledger_schema.json"
CARDS = ROOT / "data/manual_sources/v4/market_strategy_research_cards/v4_market_strategy_research_cards_20260607.json"
OUT_DIR = ROOT / "data/manual_sources/v4/market_strategy_replay"
OUT_LEDGER = OUT_DIR / "v4_market_strategy_card_replay_ledger_20260607.json"
OUT_SUMMARY = OUT_DIR / "v4_market_strategy_card_replay_summary_20260607.json"
VALIDATION_DIR = ROOT / "data/daily_reports"
BUILD_TIMESTAMP = "2026-06-07T00:00:00+08:00"
ALLOWED_CONCLUSIONS = ["OBSERVE", "WAIT", "PASS"]
GAP_TAGS = ["PRICE_MISSING", "LINE_MISSING", "MARKET_MISSING"]


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def validation_index() -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for path in sorted(VALIDATION_DIR.glob("v4_ht_recommend_validation_*.json")):
        data = load_json(path)
        if not isinstance(data, dict):
            continue
        details = data.get("details")
        if not isinstance(details, list):
            continue
        for row in details:
            if not isinstance(row, dict):
                continue
            fixture_id = row.get("fixture_id")
            if fixture_id in (None, ""):
                continue
            index[str(fixture_id)] = {**row, "_source": str(path.relative_to(ROOT))}
    return index


def direction_names(card: dict[str, Any]) -> list[str]:
    return [
        str(row.get("direction"))
        for row in card.get("strategy_directions", [])
        if isinstance(row, dict) and row.get("direction")
    ]


def result_fields(card: dict[str, Any], results: dict[str, dict[str, Any]]) -> dict[str, Any]:
    fixture_id = str((card.get("match_info") or {}).get("fixture_id") or "")
    result = results.get(fixture_id)
    if not result or result.get("pending") is True:
        return {
            "result_available": False,
            "result_hit": None,
            "result_outcome": "RESULT_MISSING",
            "replay_status": "RESULT_MISSING",
            "result_source": "",
        }
    hit = result.get("hit")
    return {
        "result_available": True,
        "result_hit": bool(hit) if hit is not None else None,
        "result_outcome": "HIT" if hit is True else "MISS" if hit is False else "RESULT_UNKNOWN",
        "replay_status": "RESULT_AVAILABLE",
        "result_source": result.get("_source") or "",
    }


def status_fields(card: dict[str, Any]) -> dict[str, str]:
    missing = set(card.get("missing_context") or [])
    market = card.get("market_confirmation_readout") or {}
    return {
        "price_status": "PRICE_MISSING" if "PRICE_MISSING" in missing else str(market.get("price_status") or "UNKNOWN"),
        "line_status": "LINE_MISSING" if "LINE_MISSING" in missing else "LINE_PRESENT",
        "market_status": "MARKET_MISSING" if "MARKET_MISSING" in missing else "MARKET_PRESENT",
    }


def ledger_row(card: dict[str, Any], results: dict[str, dict[str, Any]]) -> dict[str, Any]:
    missing = list(card.get("missing_context") or [])
    row = {
        "fixture_id": (card.get("match_info") or {}).get("fixture_id"),
        "match_info": card.get("match_info") or {},
        "league_admission_status": card.get("league_admission_status") or {},
        "strategy_card_conclusion": card.get("conclusion"),
        "strategy_directions": direction_names(card),
        "five_dimension_missing_context": missing,
        **status_fields(card),
        **result_fields(card, results),
        "sample_warning": "SAMPLE_INSUFFICIENT",
        "edge_inference": "NOT_EVALUATED",
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
    return row


def coverage_by_conclusion(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for conclusion in ALLOWED_CONCLUSIONS:
        bucket = [row for row in rows if row.get("strategy_card_conclusion") == conclusion]
        available = [row for row in bucket if row.get("result_available") is True]
        hit_count = sum(1 for row in available if row.get("result_hit") is True)
        out[conclusion] = {
            "sample_count": len(bucket),
            "result_available_count": len(available),
            "result_missing_count": len(bucket) - len(available),
            "hit_count": hit_count,
            "hit_rate": round(hit_count / len(available), 4) if available else None,
            "hit_rate_policy": "EXCLUDES_RESULT_MISSING" if available else "NOT_COMPUTED_RESULT_MISSING_OR_EMPTY",
        }
    return out


def main() -> int:
    payload = load_json(CARDS) or {}
    cards = payload.get("cards", []) if isinstance(payload, dict) else []
    results = validation_index()
    rows = [ledger_row(card, results) for card in cards if isinstance(card, dict)]
    conclusion_counts = {label: sum(1 for row in rows if row.get("strategy_card_conclusion") == label) for label in ALLOWED_CONCLUSIONS}
    gap_counts = {
        tag: sum(1 for row in rows if tag in set(row.get("five_dimension_missing_context") or []))
        for tag in GAP_TAGS
    }
    observe_count = conclusion_counts.get("OBSERVE", 0)
    warn_only = []
    if observe_count < 10:
        warn_only.append("OBSERVE_SAMPLE_INSUFFICIENT")
    if any(row.get("result_available") is not True for row in rows):
        warn_only.append("RESULT_COVERAGE_PARTIAL")
    summary = {
        "schema_version": "v4_market_strategy_card_replay_summary.v1",
        "generated_at": BUILD_TIMESTAMP,
        "source_strategy_cards": str(CARDS.relative_to(ROOT)),
        "ledger_records": len(rows),
        "conclusion_counts": conclusion_counts,
        "result_coverage_by_conclusion": coverage_by_conclusion(rows),
        "gap_counts": gap_counts,
        "observe_sample_sufficient": observe_count >= 10,
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
    ledger = {
        "schema_version": "v4_market_strategy_card_replay_ledger.v1",
        "generated_at": BUILD_TIMESTAMP,
        "schema_ref": str(SCHEMA.relative_to(ROOT)),
        "source_strategy_cards": str(CARDS.relative_to(ROOT)),
        "source_policy": "existing_local_artifacts_only",
        "live_api_called": False,
        "records": rows,
        "summary": summary,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_LEDGER.write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")
    OUT_SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "conclusion": "PASS",
        "ledger": str(OUT_LEDGER.relative_to(ROOT)),
        "summary": str(OUT_SUMMARY.relative_to(ROOT)),
        "records": len(rows),
        "conclusion_counts": conclusion_counts,
        "warn_only": summary["warn_only"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
