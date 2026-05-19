#!/usr/bin/env python3
"""
V4-G: Reporting Schema Checker

Verifies that reporting schema, guard, and sample contract docs exist
with correct grade classification and production guard flags.
"""

import json
import sys
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parents[1]

DOCS = {
    "schema": MODULE_ROOT / "docs" / "V4_REPORTING_SCHEMA.md",
    "guard": MODULE_ROOT / "docs" / "V4_REPORT_GUARD.md",
    "sample": MODULE_ROOT / "docs" / "V4_REPORT_SAMPLE_CONTRACT.md",
}

REQUIRED_RULES = [
    "observation", "SKIP", "UNKNOWN", "API_DISABLED",
    "primary", "daily", "weekly", "monthly",
]


def main():
    results = {
        "check_status": "PASS",
        "schema_doc_exists": False,
        "guard_doc_exists": False,
        "sample_contract_exists": False,
        "daily_report_schema": False,
        "weekly_report_schema": False,
        "monthly_report_schema": False,
        "ab_primary_summary": False,
        "c_observation_only": False,
        "skip_not_recommendation": False,
        "unknown_excluded": False,
        "api_disabled_excluded": False,
        "report_not_verified": True,
        "report_not_qq_sent": True,
        "rule_change_allowed": False,
        "production_verified": False,
        "phase_e_allowed": False,
        "v4_h_allowed_to_generate": True,
        "v4_h_allowed_to_execute": False,
        "blockers": [],
        "warnings": [],
    }

    block = False

    # Check docs
    for key, path in DOCS.items():
        exists = path.is_file()
        display_name = f"{key}_doc_exists" if key != "sample" else "sample_contract_exists"
        results[display_name] = exists
        if not exists:
            results["blockers"].append(f"Missing: {path.name}")
            block = True

    # Check schema doc content
    if results["schema_doc_exists"]:
        content = DOCS["schema"].read_text()
        results["daily_report_schema"] = "daily" in content.lower()
        results["weekly_report_schema"] = "weekly" in content.lower()
        results["monthly_report_schema"] = "monthly" in content.lower()
        results["ab_primary_summary"] = "primary" in content.lower() and "a/b" in content.lower()
        results["c_observation_only"] = "observation" in content.lower() and "C" in content
        results["skip_not_recommendation"] = "SKIP" in content and ("skip behavior" in content.lower() or "not recommendation" in content.lower())
        results["unknown_excluded"] = "UNKNOWN" in content and "excluded" in content.lower()
        results["api_disabled_excluded"] = "API_DISABLED" in content and "excluded" in content.lower()

    # Check guard doc content
    if results["guard_doc_exists"]:
        guard_content = DOCS["guard"].read_text()
        for rule in REQUIRED_RULES:
            if rule.lower() not in guard_content.lower():
                results["warnings"].append(f"Rule '{rule}' not found in guard doc")

    # Blocker checks
    if not results["daily_report_schema"]:
        results["warnings"].append("Daily report schema not confirmed")
    if not results["weekly_report_schema"]:
        results["warnings"].append("Weekly report schema not confirmed")
    if not results["monthly_report_schema"]:
        results["warnings"].append("Monthly report schema not confirmed")
    if not results["ab_primary_summary"]:
        results["blockers"].append("A/B primary summary rule not found")
        block = True
    if not results["c_observation_only"]:
        results["blockers"].append("C observation-only rule not found")
        block = True
    if not results["skip_not_recommendation"]:
        results["blockers"].append("SKIP not recommendation rule not found")
        block = True
    if not results["unknown_excluded"]:
        results["blockers"].append("UNKNOWN excluded rule not found")
        block = True
    if not results["api_disabled_excluded"]:
        results["blockers"].append("API_DISABLED excluded rule not found")
        block = True
    if results["production_verified"]:
        results["blockers"].append("production_verified is true")
        block = True
    if results["phase_e_allowed"]:
        results["blockers"].append("phase_e_allowed is true")
        block = True

    if block:
        results["check_status"] = "BLOCKER"
    elif results["warnings"]:
        results["check_status"] = "WARN"

    # Print
    print("=" * 60)
    print("V4 REPORTING SCHEMA CHECKER")
    print("=" * 60)
    print(f"Status: {results['check_status']}")
    for k, v in results.items():
        if k in ("blockers", "warnings"):
            continue
        print(f"  {k}: {v}")
    if results["blockers"]:
        print(f"\nBLOCKERS:")
        for b in results["blockers"]:
            print(f"  ! {b}")
        sys.exit(1)
    elif results["warnings"]:
        print(f"\nWARNINGS:")
        for w in results["warnings"]:
            print(f"  ? {w}")

    # Write marker
    marker_dir = MODULE_ROOT / "data" / "runtime" / "status"
    marker_dir.mkdir(parents=True, exist_ok=True)
    marker_path = marker_dir / "v4_reporting_schema_check.json"
    with open(marker_path, "w") as fh:
        json.dump(results, fh, indent=2, ensure_ascii=False)
    print(f"\nMarker: {marker_path} (NOT committed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
