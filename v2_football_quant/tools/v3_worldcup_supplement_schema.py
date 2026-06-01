#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ALLOWED_DATA_STATUS = {"PRESENT", "PARTIAL", "MISSING", "TEMPLATE_ONLY", "STALE", "NEED_REVIEW"}
ALLOWED_CONFIDENCE = {"HIGH", "MEDIUM", "LOW", "UNKNOWN"}

SUPPLEMENT_SCHEMA: dict[str, list[str]] = {
    "caps_goals_minutes": [
        "team", "player_name", "position", "caps", "goals",
        "national_team_minutes_last_12m", "club_minutes_2025_26",
        "source", "source_date", "confidence", "data_status",
    ],
    "injuries": [
        "team", "player_name", "injury_status", "expected_return",
        "availability_risk", "source", "source_date", "confidence", "data_status",
    ],
    "friendly_form": [
        "team", "match_date", "opponent", "venue", "score_for", "score_against",
        "rotation_level", "notes", "source", "data_status",
    ],
    "market_baseline": [
        "team", "market_type", "baseline_value", "current_value", "movement",
        "public_hype_level", "underdog_discount_signal", "source", "source_date", "data_status",
    ],
    "club_form": [
        "player_name", "team", "club", "club_minutes_recent", "club_form_signal",
        "fatigue_risk", "data_status",
    ],
    "coach_profiles": [
        "team", "coach", "tenure_days", "tactical_style", "tournament_experience",
        "volatility_risk", "data_status",
    ],
    "wc_history": [
        "team", "wc_appearances", "recent_wc_result", "tournament_consistency",
        "pressure_profile", "data_status",
    ],
}


def validate_record(category: str, row: dict[str, Any]) -> tuple[bool, list[str]]:
    errors: list[str] = []
    required = SUPPLEMENT_SCHEMA.get(category, [])
    for k in required:
        if k not in row:
            errors.append(f"MISSING:{k}")
    ds = str(row.get("data_status") or "")
    if ds and ds not in ALLOWED_DATA_STATUS:
        errors.append(f"BAD_DATA_STATUS:{ds}")
    cf = str(row.get("confidence") or "")
    if "confidence" in required and cf and cf not in ALLOWED_CONFIDENCE:
        errors.append(f"BAD_CONFIDENCE:{cf}")
    return (len(errors) == 0, errors)


def validate_file(category: str, payload: dict[str, Any]) -> dict[str, Any]:
    records = payload.get("records") if isinstance(payload.get("records"), list) else []
    errors: list[str] = []
    ok_count = 0
    for i, rec in enumerate(records):
        if not isinstance(rec, dict):
            errors.append(f"ROW_NOT_DICT:{i}")
            continue
        ok, row_errors = validate_record(category, rec)
        if ok:
            ok_count += 1
        else:
            errors.extend([f"ROW{i}:{x}" for x in row_errors])
    return {
        "records_total": len(records),
        "records_valid": ok_count,
        "errors": errors,
    }


def summarize_coverage(category: str, payload: dict[str, Any]) -> dict[str, Any]:
    v = validate_file(category, payload)
    records = payload.get("records") if isinstance(payload.get("records"), list) else []
    statuses = {str((x or {}).get("data_status") or "MISSING") for x in records if isinstance(x, dict)}
    if not records:
        coverage = "MISSING"
    elif statuses == {"TEMPLATE_ONLY"}:
        coverage = "TEMPLATE_ONLY"
    elif "STALE" in statuses:
        coverage = "STALE"
    elif "MISSING" in statuses or "NEED_REVIEW" in statuses:
        coverage = "PARTIAL"
    else:
        coverage = "PRESENT"
    return {
        "category": category,
        "coverage_status": coverage,
        "records_total": v["records_total"],
        "records_valid": v["records_valid"],
        "validation_errors": v["errors"],
    }


if __name__ == "__main__":
    print(json.dumps({"schema_categories": list(SUPPLEMENT_SCHEMA.keys()), "status": "SCHEMA_READY"}, ensure_ascii=False, indent=2))
