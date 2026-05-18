#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent.parent
LEDGER_DIR = BASE_DIR / "data" / "runtime" / "ledger"
RUNTIME_DIR = BASE_DIR / "data" / "runtime"
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
    dashboard = ledger.get("dashboard", {})
    issues = ledger.get("issues", {})
    runtime_root_policy = ledger.get("runtime_root_policy", {})
    final_status = ledger.get("final_status", {})

    # Rule: production_verified guard
    if bool(final_status.get("production_verified")):
        result["errors"].append("production_verified_must_be_false_in_phase_ab")

    # Rule: old dashboard split issue key forbidden, new key required
    p2_items = issues.get("p2", []) if isinstance(issues, dict) else []
    if "P2_DASHBOARD_INTERNAL_PUBLIC_NOT_SPLIT" in p2_items:
        result["errors"].append("old_dashboard_issue_key_forbidden")
    if "P2_DASHBOARD_PRODUCT_READING_LAYER_GAP" not in p2_items:
        result["errors"].append("new_dashboard_issue_key_missing")

    # Rule: runtime root canonicalization
    source_root = str(ledger.get("source_root", ""))
    expected_root = str(RUNTIME_DIR)
    if source_root != expected_root:
        result["errors"].append("source_root_not_canonical_runtime")
    if not isinstance(runtime_root_policy, dict):
        result["errors"].append("runtime_root_policy_missing")
    else:
        if str(runtime_root_policy.get("canonical_runtime_root", "")) != expected_root:
            result["errors"].append("runtime_root_policy_canonical_path_invalid")
        if runtime_root_policy.get("project_runtime_used_as_primary") is not True:
            result["errors"].append("project_runtime_not_primary")
        if runtime_root_policy.get("workspace_root_runtime_allowed_as_primary") is not False:
            result["errors"].append("workspace_runtime_primary_forbidden")
        if runtime_root_policy.get("path_mismatch_warning_only") is not True:
            result["errors"].append("path_mismatch_warning_policy_invalid")

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

    # Dashboard product direction checks
    pd = dashboard.get("product_direction", {}) if isinstance(dashboard, dict) else {}
    if not isinstance(pd, dict):
        result["warnings"].append("dashboard_product_direction_missing")
    else:
        if pd.get("single_dashboard") is not True:
            result["errors"].append("dashboard_single_dashboard_required")
        if pd.get("default_layer") != "product_reading":
            result["errors"].append("dashboard_default_layer_must_be_product_reading")
        if pd.get("evidence_collapsed") is not True:
            result["warnings"].append("dashboard_evidence_should_be_collapsed")
        if pd.get("single_match_card_future_core") is not True:
            result["warnings"].append("single_match_card_future_core_missing")
        if pd.get("internal_public_split_required") is not False:
            result["errors"].append("internal_public_split_must_be_false")

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
