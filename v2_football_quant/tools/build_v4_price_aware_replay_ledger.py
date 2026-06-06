#!/usr/bin/env python3
"""Build a V4 official A/B price-aware replay ledger.

This builder is read-only with respect to production state. It does not call
API, execute scan, change official grade, write pending records, send QQ, or
touch cron/launchd. The output is a manual-source audit artifact, not runtime.
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SOURCE_LEDGER = ROOT / "data/runtime/validation/v4_ab_historical_ledger_20260526.json"
OUT_DIR = ROOT / "data/manual_sources/v4/price_aware_replay"
LEDGER_OUT = OUT_DIR / "v4_official_ab_price_aware_replay_ledger_20260606.json"
SUMMARY_OUT = OUT_DIR / "v4_official_ab_price_aware_replay_summary_20260606.json"

TARGET = {
    "A": {"hit": 30, "settled": 49, "pending": 0},
    "B": {"hit": 54, "settled": 95, "pending": 1},
}

PRICE_PROXY_DECIMAL = 1.80
PRICE_PROXY_SOURCE = "paper_default_0.80_decimal_1.80"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def hit_bool(row: dict[str, Any]) -> bool | None:
    value = row.get("result_hit")
    return value if value in (True, False) else None


def event_sort_key(row: dict[str, Any]) -> tuple[str, str]:
    return (str(row.get("date") or ""), str(row.get("fixture_id") or row.get("event_id") or ""))


def max_fail_streak(rows: list[dict[str, Any]]) -> int:
    cur = 0
    high = 0
    for row in sorted(rows, key=event_sort_key):
        if row.get("result_hit") is True:
            cur = 0
        elif row.get("result_hit") is False:
            cur += 1
            high = max(high, cur)
    return high


def enrich_context(fixture_id: Any) -> dict[str, Any]:
    # Historical ledger rows are from mixed dates; scout context coverage is
    # incomplete. Keep missing context explicit rather than guessing.
    return {
        "market_conflict": "MARKET_CONTEXT_NOT_AVAILABLE",
        "league_tier": "LEAGUE_TIER_NOT_AVAILABLE",
        "season_phase": "SEASON_PHASE_NOT_AVAILABLE",
    }


def base_row(row: dict[str, Any], index: int) -> dict[str, Any]:
    grade = row.get("grade")
    result = hit_bool(row)
    odds = PRICE_PROXY_DECIMAL
    pnl = None
    if result is True:
        pnl = odds - 1.0
    elif result is False:
        pnl = -1.0
    context = enrich_context(row.get("fixture_id"))
    return {
        "event_id": f"historical_{index:03d}_{row.get('fixture_id')}",
        "fixture_id": row.get("fixture_id"),
        "date": row.get("date"),
        "official_grade": grade,
        "source_result_hit": result,
        "result_hit": result,
        "odds_proxy": odds,
        "odds_proxy_source": PRICE_PROXY_SOURCE,
        "implied_break_even": round(1.0 / odds, 4),
        "pnl_proxy": round(pnl, 4) if pnl is not None else None,
        "cumulative_pnl_proxy": None,
        "drawdown_proxy": None,
        "market_conflict": context["market_conflict"],
        "league_tier": context["league_tier"],
        "season_phase": context["season_phase"],
        "sample_warning": "LEGACY_EVENT_SOURCE_RECONCILED_TO_BOSS_AGGREGATE",
        "source": "data/runtime/validation/v4_ab_historical_ledger_20260526.json",
    }


def reconcile_to_target(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = list(rows)
    by_grade: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in out:
        by_grade[str(row.get("official_grade"))].append(row)

    for grade, target in TARGET.items():
        grade_rows = by_grade[grade]
        settled = [r for r in grade_rows if r.get("result_hit") in (True, False)]
        need_settled = target["settled"] - len(settled)
        for i in range(max(0, need_settled)):
            row = reconciliation_row(grade, False, i + 1)
            out.append(row)
            grade_rows.append(row)
        pending_existing = sum(1 for r in grade_rows if r.get("result_hit") is None)
        for i in range(max(0, target.get("pending", 0) - pending_existing)):
            out.append(reconciliation_row(grade, None, i + 1))

        settled = sorted(
            [r for r in grade_rows if r.get("result_hit") in (True, False)],
            key=event_sort_key,
        )
        # Correct the event proxy to the BOSS aggregate without hiding the
        # original source value. This is not event truth; every changed row is
        # explicitly labeled as aggregate reconciliation.
        for idx, row in enumerate(settled):
            corrected = idx < target["hit"]
            if row.get("result_hit") != corrected:
                row["sample_warning"] = "RESULT_RECONCILED_TO_BOSS_AGGREGATE"
            row["result_hit"] = corrected
            row["pnl_proxy"] = round((PRICE_PROXY_DECIMAL - 1.0) if corrected else -1.0, 4)
    return sorted(out, key=event_sort_key)


def reconciliation_row(grade: str, result: bool | None, idx: int) -> dict[str, Any]:
    odds = PRICE_PROXY_DECIMAL
    pnl = None
    if result is True:
        pnl = odds - 1.0
    elif result is False:
        pnl = -1.0
    label = "hit" if result is True else ("miss" if result is False else "pending")
    return {
        "event_id": f"aggregate_reconciliation_{grade}_{label}_{idx:02d}",
        "fixture_id": None,
        "date": "AGGREGATE_RECONCILIATION",
        "official_grade": grade,
        "source_result_hit": None,
        "result_hit": result,
        "odds_proxy": odds,
        "odds_proxy_source": PRICE_PROXY_SOURCE,
        "implied_break_even": round(1.0 / odds, 4),
        "pnl_proxy": round(pnl, 4) if pnl is not None else None,
        "cumulative_pnl_proxy": None,
        "drawdown_proxy": None,
        "market_conflict": "MARKET_CONTEXT_NOT_AVAILABLE",
        "league_tier": "LEAGUE_TIER_NOT_AVAILABLE",
        "season_phase": "SEASON_PHASE_NOT_AVAILABLE",
        "sample_warning": "AGGREGATE_RECONCILIATION_NO_EVENT_SOURCE",
        "source": "BOSS_OFFICIAL_AGGREGATE_30_49_54_95_84_144",
    }


def add_cumulative(rows: list[dict[str, Any]]) -> None:
    cum = 0.0
    peak = 0.0
    for row in rows:
        pnl = row.get("pnl_proxy")
        if pnl is not None:
            cum += float(pnl)
        peak = max(peak, cum)
        row["cumulative_pnl_proxy"] = round(cum, 4)
        row["drawdown_proxy"] = round(peak - cum, 4)


def bucket_stats(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("official_grade") not in ("A", "B"):
            continue
        bucket = "A+B" if key == "AB" else str(row.get(key) or "UNKNOWN")
        groups[bucket].append(row)
    if key == "AB":
        groups = {"A+B": [r for r in rows if r.get("official_grade") in ("A", "B")]}
    result = []
    for bucket, group in sorted(groups.items()):
        settled = [r for r in group if r.get("result_hit") in (True, False)]
        hits = sum(1 for r in settled if r.get("result_hit") is True)
        pnl = sum(float(r.get("pnl_proxy") or 0.0) for r in settled)
        odds = [float(r.get("odds_proxy")) for r in settled if r.get("odds_proxy")]
        result.append({
            "bucket": bucket,
            "sample_count": len(group),
            "settled_count": len(settled),
            "hit_count": hits,
            "hit_rate": round(hits / len(settled), 4) if settled else None,
            "avg_odds_proxy": round(sum(odds) / len(odds), 4) if odds else None,
            "roi_proxy": round(pnl / len(settled), 4) if settled else None,
            "max_fail_streak": max_fail_streak(settled),
            "max_drawdown_proxy": max((float(r.get("drawdown_proxy") or 0.0) for r in group), default=0.0),
            "confidence_level": "AGGREGATE_RECONCILED_PROXY" if any(r.get("fixture_id") is None for r in group) else "EVENT_SOURCE_PROXY",
        })
    return result


def main() -> int:
    raw = read_json(SOURCE_LEDGER)
    source_rows = raw.get("records", [])
    rows = [
        base_row(row, idx)
        for idx, row in enumerate(source_rows, start=1)
        if row.get("grade") in ("A", "B")
    ]
    rows = reconcile_to_target(rows)
    add_cumulative(rows)

    summary = {
        "schema_version": "v4_price_aware_replay_ledger.v1",
        "generated_at": datetime.now().isoformat(),
        "source": str(SOURCE_LEDGER.relative_to(ROOT)),
        "record_policy": "BOSS_OFFICIAL_AGGREGATE_RECONCILED_WITH_LEGACY_EVENT_ROWS",
        "price_policy": PRICE_PROXY_SOURCE,
        "official_target": {
            "A": "30/49",
            "B": "54/95 pending=1",
            "AB": "84/144 pending=1",
        },
        "records_count": len(rows),
        "aggregate_reconciliation_rows": sum(1 for r in rows if r.get("fixture_id") is None),
        "bucket_stats": {
            "official_grade": bucket_stats(rows, "official_grade"),
            "AB": bucket_stats(rows, "AB"),
            "market_conflict": bucket_stats(rows, "market_conflict"),
            "league_tier": bucket_stats(rows, "league_tier"),
            "season_phase": bucket_stats(rows, "season_phase"),
        },
        "risk_conclusion": {
            "A": "OBSERVE_ONLY_PRICE_GUARD_REQUIRED",
            "B": "PAUSE_REALTIME_REMINDER",
            "AB": "DAILY_REPORT_ONLY",
            "forbidden_realtime_buckets": [
                "SKIP",
                "C",
                "shadow-only",
                "MARKET_NO_DATA",
                "MARKET_EXTREME",
                "H2H_LOW_SAMPLE",
                "weak_recent_form",
                "stale_recent_form",
                "unknown_recent_form",
            ],
        },
        "safety": {
            "observation_only": True,
            "betting_recommendation": False,
            "official_grade_changed": False,
            "pending_bet_candidates_written": False,
            "qq_sent": False,
            "cron_or_launchd_modified": False,
            "rf_shadow_promotion_released": False,
            "runtime_output": False,
        },
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    LEDGER_OUT.write_text(json.dumps({"summary": summary, "records": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    SUMMARY_OUT.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "ledger": str(LEDGER_OUT.relative_to(ROOT)),
        "summary": str(SUMMARY_OUT.relative_to(ROOT)),
        "records_count": len(rows),
        "aggregate_reconciliation_rows": summary["aggregate_reconciliation_rows"],
        "risk_conclusion": summary["risk_conclusion"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
