#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent.parent
LEDGER_DIR = BASE_DIR / "data" / "runtime" / "ledger"
CN_TZ = timezone(timedelta(hours=8))


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def main() -> None:
    parser = argparse.ArgumentParser(description="Check Daily Run Ledger v1")
    parser.add_argument("--date", required=True, help="YYYYMMDD")
    args = parser.parse_args()
    date_key = args.date.strip().replace("-", "")
    path = LEDGER_DIR / f"{date_key}.json"

    result = {
        "date": date_key,
        "ledger_exists": path.exists(),
        "status": "FAIL",
        "warnings": [],
        "errors": [],
        "production_verified": False,
    }
    if not path.exists():
        result["errors"].append("ledger_missing")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        raise SystemExit(1)

    ledger = _load_json(path, {})
    required_top = ["date", "generated_at", "source_root", "v2", "v4_scan", "v4_review", "dashboard", "issues", "final_status"]
    for k in required_top:
        if k not in ledger:
            result["errors"].append(f"missing_top_field:{k}")

    v2 = ledger.get("v2", {})
    v4_scan = ledger.get("v4_scan", {})
    v4_review = ledger.get("v4_review", {})
    final_status = ledger.get("final_status", {})

    # Rule: production_verified guard
    if bool(final_status.get("production_verified")):
        result["errors"].append("production_verified_must_be_false_in_phase_ab")

    # Rule: V2 official lock from formal status, no candidate_stage inference
    if "selected_fixtures_used_for_lock_decision" in v2.get("evidence", {}) and bool(v2["evidence"]["selected_fixtures_used_for_lock_decision"]):
        result["errors"].append("v2_lock_inferred_from_selected_fixtures_forbidden")

    # Rule: fallback not production evidence
    prod_windows = v4_scan.get("production_evidence_windows", [])
    for w in ("late", "early", "evening", "night"):
        if w in prod_windows:
            result["errors"].append(f"forbidden_production_window:{w}")
    if "midday" not in prod_windows:
        result["warnings"].append("midday_not_in_production_windows")

    # Rule: due time semantics
    due = str(v4_review.get("due_time", ""))
    cur = datetime.now(CN_TZ)
    try:
        due_dt = datetime.fromisoformat(due)
        if cur < due_dt and str(v4_review.get("status")) == "MISSING":
            result["errors"].append("review_before_due_cannot_be_missing")
    except Exception:
        result["warnings"].append("invalid_due_time_format")

    # warning on path mismatch
    for w in ledger.get("warnings", []):
        if isinstance(w, dict) and w.get("type") == "path_mismatch":
            result["warnings"].append("path_mismatch_detected")

    # secret / legacy keyword scan
    dump = json.dumps(ledger, ensure_ascii=False)
    lowered = dump.lower()
    if "v33" in lowered:
        result["errors"].append("forbidden_keyword_v33")
    if "api_key" in lowered or "appsecret" in lowered or "token" in lowered:
        result["warnings"].append("possible_secret_keyword_detected")

    if result["errors"]:
        result["status"] = "FAIL"
        code = 1
    elif result["warnings"]:
        result["status"] = "PASS_WITH_WARNINGS"
        code = 0
    else:
        result["status"] = "PASS"
        code = 0

    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(code)


if __name__ == "__main__":
    main()

