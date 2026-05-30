#!/usr/bin/env python3
from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any

import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.rf_shadow_fields import build_rf_shadow_grade_layer

REPORT_DIR = ROOT / "data" / "daily_reports"
OUT_DIR = ROOT / "data" / "runtime" / "acceptance"

RF_SHADOW_FIELDS = [
    "rf_shadow_grade",
    "rf_shadow_score",
    "rf_shadow_route",
    "rf_shadow_reason",
    "rf_shadow_confidence",
    "rf_entry_rule",
    "rf_recent10_gate_status",
    "rf_recent5_grade_status",
    "rf_heating_exception",
    "rf_heating_exception_reason",
]

TEAM_BALANCE_FIELDS = [
    "rf_balance_status",
    "rf_balance_driver_side",
    "rf_balance_driver_level",
    "rf_balance_weak_side_status",
    "rf_balance_adjustment",
    "rf_balance_reason",
]

H2H_BONUS_FIELDS = [
    "h2h_recent5_support_status",
    "h2h_recent5_bonus_level",
    "h2h_recent5_bonus_reason",
]

OPENING_MARKET_FIELDS = [
    "opening_market_support_status",
    "opening_market_reason",
    "market_adjusted_shadow_grade",
    "market_adjustment_reason",
]


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _rows_from_payload(payload: Any) -> list[dict]:
    if isinstance(payload, list):
        return [r for r in payload if isinstance(r, dict)]
    if isinstance(payload, dict):
        for key in ("rows", "scout", "data", "items"):
            rows = payload.get(key)
            if isinstance(rows, list):
                return [r for r in rows if isinstance(r, dict)]
    return []


def _find_latest_non_empty_scout() -> tuple[Path, list[dict]]:
    candidates = sorted(REPORT_DIR.glob("scout_v4_*.json"), key=lambda p: p.name, reverse=True)
    for path in candidates:
        payload = _load_json(path)
        rows = _rows_from_payload(payload)
        if rows:
            return path, rows
    raise RuntimeError("未找到非空 scout_v4_*.json 样本")


def _to_number(v: Any) -> float | None:
    try:
        if v is None or v == "":
            return None
        n = float(v)
        if math.isnan(n) or math.isinf(n):
            return None
        return n
    except Exception:
        return None


def _build_factors(row: dict) -> dict[str, Any]:
    return {
        "h2h_official_sample_size": row.get("h2h_official_sample_size", row.get("h2h_sample_size")),
        "h2h_sample_size": row.get("h2h_sample_size"),
        "h2h_ht_goal_rate": row.get("h2h_ht_goal_rate"),
        "h2h_total": row.get("h2h_total"),
        "h2h_3y_count": row.get("h2h_3y_count"),
    }


def _is_defined(v: Any) -> bool:
    if v is None:
        return False
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return False
    if isinstance(v, str) and v.strip().lower() in {"", "undefined", "null", "nan"}:
        return False
    return True


def _coverage(rows: list[dict], fields: list[str]) -> dict[str, dict[str, Any]]:
    total = len(rows)
    out: dict[str, dict[str, Any]] = {}
    for f in fields:
        present = sum(1 for r in rows if f in r)
        defined = sum(1 for r in rows if _is_defined(r.get(f)))
        out[f] = {
            "present_count": present,
            "defined_count": defined,
            "present_ratio": round((present / total), 4) if total else 0.0,
            "defined_ratio": round((defined / total), 4) if total else 0.0,
        }
    return out


def _candidate_view_like(rows: list[dict]) -> dict[str, list[dict]]:
    result = {"A_candidates": [], "B_candidates": [], "C_candidates": [], "SKIP_candidates": []}
    for r in rows:
        shadow_grade = str(r.get("market_adjusted_shadow_grade") or r.get("rf_shadow_grade") or "SKIP").upper()
        grade_key = shadow_grade if shadow_grade in {"A", "B", "C", "SKIP"} else "SKIP"
        view_row = {
            "fixture_id": r.get("fixture_id"),
            "league_name": r.get("league_name"),
            "home_team_name": r.get("home_team_name"),
            "away_team_name": r.get("away_team_name"),
            "grade": r.get("grade"),
            "official_grade": r.get("official_grade"),
            "rf_shadow_grade": r.get("rf_shadow_grade"),
            "market_adjusted_shadow_grade": r.get("market_adjusted_shadow_grade"),
            "rf_balance_reason": r.get("rf_balance_reason"),
            "h2h_recent5_bonus_reason": r.get("h2h_recent5_bonus_reason"),
            "opening_market_reason": r.get("opening_market_reason"),
            "market_adjustment_reason": r.get("market_adjustment_reason"),
        }
        result[f"{grade_key}_candidates"].append(view_row)
    return result


def _dashboard_model_like(rows: list[dict]) -> dict[str, Any]:
    items = []
    for r in rows:
        items.append(
            {
                "fixture_id": r.get("fixture_id"),
                "official_grade": r.get("official_grade"),
                "rf_shadow_grade": r.get("rf_shadow_grade"),
                "market_adjusted_shadow_grade": r.get("market_adjusted_shadow_grade"),
                "rf_shadow_route": r.get("rf_shadow_route"),
                "rf_shadow_reason": r.get("rf_shadow_reason"),
                "rf_shadow_confidence": r.get("rf_shadow_confidence"),
                "rf_balance_status": r.get("rf_balance_status"),
                "rf_balance_reason": r.get("rf_balance_reason"),
                "h2h_recent5_support_status": r.get("h2h_recent5_support_status"),
                "h2h_recent5_bonus_reason": r.get("h2h_recent5_bonus_reason"),
                "opening_market_support_status": r.get("opening_market_support_status"),
                "opening_market_reason": r.get("opening_market_reason"),
                "market_adjustment_reason": r.get("market_adjustment_reason"),
            }
        )
    return {
        "candidates": {"items": items, "count": len(items)},
        "meta": {"generated_by": "run_v4_rf_shadow_grade_light_runtime_acceptance", "mode": "LIGHT_RUNTIME_ACCEPTANCE"},
    }


def _rule_samples() -> list[dict[str, Any]]:
    base = {
        "recent10_sample_count_home": 10,
        "recent10_sample_count_away": 10,
        "home_recent10_fh_involved_rate": 0.7,
        "away_recent10_fh_involved_rate": 0.6,
        "combined_recent10_fh_involved_rate": 0.65,
        "home_recent5_fh_involved_rate": 1.0,
        "away_recent5_fh_involved_rate": 0.6,
        "combined_recent5_fh_involved_rate": 0.8,
        "recent_form_primary_score": 73.0,
        "prematch_ht_line": 1.0,
        "prematch_over_odds": 1.92,
    }
    factors = {"h2h_official_sample_size": 5, "h2h_ht_goal_rate": 0.4, "h2h_total": 10, "h2h_3y_count": 10}

    def case(name: str, override: dict, expect: Any, predicate: Any, factor_override: dict | None = None) -> dict[str, Any]:
        rec = dict(base)
        rec.update(override)
        ff = dict(factors)
        if factor_override:
            ff.update(factor_override)
        out = build_rf_shadow_grade_layer(rec, factors=ff)
        observed = out.get(expect) if isinstance(expect, str) else {k: out.get(k) for k in expect}
        return {"name": name, "pass": bool(predicate(out)), "observed": observed}

    return [
        case(
            "rule_1_recent10_7of10_entry_pass",
            {"combined_recent10_fh_involved_rate": 0.7, "combined_recent5_fh_involved_rate": 0.8},
            "rf_recent10_gate_status",
            lambda o: o.get("rf_recent10_gate_status") == "RECENT10_GATE_PASS_7_OF_10",
        ),
        case("rule_2_recent5_5of5_A_base", {"combined_recent10_fh_involved_rate": 0.7, "combined_recent5_fh_involved_rate": 1.0}, "rf_shadow_grade", lambda o: o.get("rf_shadow_grade") == "A"),
        case("rule_3_recent5_4of5_B_base", {"combined_recent10_fh_involved_rate": 0.7, "combined_recent5_fh_involved_rate": 0.8}, "rf_shadow_grade", lambda o: o.get("rf_shadow_grade") == "B"),
        case("rule_4_recent5_3of5_C_observe", {"combined_recent10_fh_involved_rate": 0.7, "combined_recent5_fh_involved_rate": 0.6}, "rf_shadow_grade", lambda o: o.get("rf_shadow_grade") == "C"),
        case("rule_5_6of10_plus_5of5_is_B", {"combined_recent10_fh_involved_rate": 0.6, "combined_recent5_fh_involved_rate": 1.0, "home_recent5_fh_involved_rate": 1.0, "away_recent5_fh_involved_rate": 1.0}, "rf_shadow_grade", lambda o: o.get("rf_shadow_grade") == "B"),
        case("rule_6_5of10_plus_5of5_is_C", {"combined_recent10_fh_involved_rate": 0.5, "combined_recent5_fh_involved_rate": 1.0, "home_recent5_fh_involved_rate": 1.0, "away_recent5_fh_involved_rate": 1.0}, "rf_shadow_grade", lambda o: o.get("rf_shadow_grade") == "C"),
        case("rule_7_le4_not_ab", {"combined_recent10_fh_involved_rate": 0.4, "combined_recent5_fh_involved_rate": 0.4}, "rf_shadow_grade", lambda o: o.get("rf_shadow_grade") not in {"A", "B"}),
        case("rule_8_hot_driver_acceptable_to_B", {}, "market_adjusted_shadow_grade", lambda o: o.get("market_adjusted_shadow_grade") == "B"),
        case("rule_9_weak3of5_not_direct_skip", {}, "market_adjusted_shadow_grade", lambda o: o.get("market_adjusted_shadow_grade") != "SKIP"),
        case("rule_10_h2h_weak_no_downgrade", {"combined_recent10_fh_involved_rate": 0.7, "combined_recent5_fh_involved_rate": 0.8}, ["rf_shadow_grade", "h2h_recent5_support_status"], lambda o: o.get("h2h_recent5_support_status") == "H2H_NO_BONUS" and o.get("rf_shadow_grade") in {"A", "B", "C", "SKIP"}, {"h2h_ht_goal_rate": 0.2}),
        case("rule_11_h2h_strong_not_manufacture_ab", {"combined_recent10_fh_involved_rate": 0.5, "combined_recent5_fh_involved_rate": 0.6}, "rf_shadow_grade", lambda o: o.get("h2h_recent5_support_status") == "H2H_STRONG_BONUS" and o.get("rf_shadow_grade") not in {"A", "B"}, {"h2h_ht_goal_rate": 1.0}),
        case("rule_12_market_strong_not_manufacture_ab", {"combined_recent10_fh_involved_rate": 0.5, "combined_recent5_fh_involved_rate": 0.6, "prematch_ht_line": 1.25, "prematch_over_odds": 1.8}, "rf_shadow_grade", lambda o: o.get("opening_market_support_status") == "MARKET_STRONG_CONFIRM" and o.get("rf_shadow_grade") not in {"A", "B"}),
        case("rule_13_market_hard_veto_shadow_only", {"combined_recent10_fh_involved_rate": 0.7, "combined_recent5_fh_involved_rate": 1.0, "prematch_ht_line": 0.25, "prematch_over_odds": 2.4}, ["opening_market_support_status", "market_adjusted_shadow_grade"], lambda o: o.get("opening_market_support_status") == "MARKET_HARD_VETO" and o.get("market_adjusted_shadow_grade") in {"C", "SKIP"}),
        case("rule_14_market_no_market_skip", {"no_market_excluded": True, "prematch_ht_line": None, "prematch_over_odds": None}, ["opening_market_support_status", "market_adjusted_shadow_grade"], lambda o: o.get("opening_market_support_status") == "MARKET_NO_MARKET" and o.get("market_adjusted_shadow_grade") == "SKIP"),
    ]


def main() -> int:
    source_path, source_rows = _find_latest_non_empty_scout()
    enriched_rows: list[dict] = []
    no_regrade_violations: list[dict[str, Any]] = []

    for row in source_rows:
        before_grade = row.get("grade")
        before_official_grade = row.get("official_grade")
        shadow = build_rf_shadow_grade_layer(dict(row), factors=_build_factors(row))
        enriched = dict(row)
        enriched.update(shadow)
        enriched_rows.append(enriched)

        if enriched.get("grade") != before_grade or enriched.get("official_grade") != before_official_grade:
            no_regrade_violations.append(
                {
                    "fixture_id": row.get("fixture_id"),
                    "before_grade": before_grade,
                    "after_grade": enriched.get("grade"),
                    "before_official_grade": before_official_grade,
                    "after_official_grade": enriched.get("official_grade"),
                }
            )

    all_fields = RF_SHADOW_FIELDS + TEAM_BALANCE_FIELDS + H2H_BONUS_FIELDS + OPENING_MARKET_FIELDS
    coverage = _coverage(enriched_rows, all_fields)
    coverage_pass = all(v["present_count"] == len(enriched_rows) for v in coverage.values())
    rule_samples = _rule_samples()
    rule_pass = all(x["pass"] for x in rule_samples)
    no_regrade_pass = len(no_regrade_violations) == 0

    candidate_like = _candidate_view_like(enriched_rows)
    dashboard_like = _dashboard_model_like(enriched_rows)

    status = "PASS" if (enriched_rows and coverage_pass and rule_pass and no_regrade_pass) else "FAIL"

    out = {
        "generated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "acceptance_mode": "LIGHT_RUNTIME_ACCEPTANCE",
        "api_calls_made": False,
        "formal_scan_executed": False,
        "source_scout_path": str(source_path),
        "source_row_count": len(source_rows),
        "enriched_row_count": len(enriched_rows),
        "rf_shadow_field_coverage": coverage,
        "no_regrade_check": {
            "pass": no_regrade_pass,
            "violation_count": len(no_regrade_violations),
            "violations": no_regrade_violations[:20],
        },
        "sample_rows": enriched_rows[:5],
        "candidate_view_like_rows": candidate_like,
        "dashboard_model_like_rows": dashboard_like,
        "rule_sample_results": rule_samples,
        "acceptance_status": status,
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = OUT_DIR / f"v4_rf_shadow_grade_light_acceptance_{ts}.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({"artifact_path": str(out_path), "source_scout_path": str(source_path), "source_row_count": len(source_rows), "enriched_row_count": len(enriched_rows), "acceptance_status": status}, ensure_ascii=False, indent=2))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
