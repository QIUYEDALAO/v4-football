#!/usr/bin/env python3
"""
V4-F: Rolling Schema Checker

Verifies that rolling validation schema, guard, and sample contract docs exist
with correct exclusion rules and production guard flags.
"""

import json
import sys
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parents[1]

DOCS = {
    "schema": MODULE_ROOT / "docs" / "V4_ROLLING_VALIDATION_SCHEMA.md",
    "guard": MODULE_ROOT / "docs" / "V4_ROLLING_VALIDATION_GUARD.md",
    "sample": MODULE_ROOT / "docs" / "V4_ROLLING_SAMPLE_CONTRACT.md",
}

REQUIRED_EXCLUSIONS = [
    "UNKNOWN",
    "API_DISABLED",
    "result_known=false",
    "SKIP",
    "observation-only",
    "observation_only",
]

REQUIRED_WINDOWS = ["7", "14", "30"]


def main():
    results = {
        "check_status": "PASS",
        "schema_doc_exists": False,
        "guard_doc_exists": False,
        "sample_contract_exists": False,
        "windows": [],
        "ab_hit_rate_rule_found": False,
        "c_observation_only_found": False,
        "skip_not_scored_found": False,
        "unknown_excluded_found": False,
        "api_disabled_excluded_found": False,
        "result_unknown_excluded_found": False,
        "rule_change_allowed": False,
        "verified_write_allowed": False,
        "production_verified": False,
        "phase_e_allowed": False,
        "v4_g_allowed_to_generate": True,
        "v4_g_allowed_to_execute": False,
        "blockers": [],
        "warnings": [],
    }

    block = False

    # Check docs exist
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
        for w in REQUIRED_WINDOWS:
            if w in content:
                results["windows"].append(int(w))
        if any(p in content.lower() for p in ["hit_rate", "hit_count", "miss_count"]):
            results["ab_hit_rate_rule_found"] = True
        if "observation" in content.lower():
            results["c_observation_only_found"] = True
        if "skip" in content.lower():
            results["skip_not_scored_found"] = True
        if "UNKNOWN" in content and ("excluded" in content.lower() or "hit/miss" in content.lower()):
            results["unknown_excluded_found"] = True
        if "API_DISABLED" in content and ("excluded" in content.lower() or "hit/miss" in content.lower()):
            results["api_disabled_excluded_found"] = True
        if "result_known" in content and ("excluded" in content.lower()):
            results["result_unknown_excluded_found"] = True

    # Check guard doc content
    if results["guard_doc_exists"]:
        guard_content = DOCS["guard"].read_text()
        for exc in REQUIRED_EXCLUSIONS:
            # observation_only and observation-only are equivalent
            if exc == "observation_only":
                if "observation-only" in guard_content.lower() or "observation_only" in guard_content.lower():
                    continue
            if exc.lower() not in guard_content.lower():
                results["warnings"].append(f"Exclusion rule '{exc}' not found in guard doc")

    # Check blocker conditions
    if not results["ab_hit_rate_rule_found"]:
        results["warnings"].append("A/B hit-rate rule not confirmed in schema")
    if not results["c_observation_only_found"]:
        results["warnings"].append("C observation-only rule not confirmed in schema")
    if not results["skip_not_scored_found"]:
        results["blockers"].append("SKIP not-scored rule not found")
        block = True
    if not results["unknown_excluded_found"]:
        results["blockers"].append("UNKNOWN excluded rule not found")
        block = True
    if not results["api_disabled_excluded_found"]:
        results["blockers"].append("API_DISABLED excluded rule not found")
        block = True
    if not results["result_unknown_excluded_found"]:
        results["blockers"].append("result_known=false excluded rule not found")
        block = True
    if results["production_verified"]:
        results["blockers"].append("production_verified is true")
        block = True
    if results["phase_e_allowed"]:
        results["blockers"].append("phase_e_allowed is true")
        block = True

    # Determine status
    if block:
        results["check_status"] = "BLOCKER"
    elif results["warnings"]:
        results["check_status"] = "WARN"

    # Print
    print("=" * 60)
    print("V4 ROLLING SCHEMA CHECKER")
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
        print(f"\nWARNINGS ({len(results['warnings'])}):")
        for w in results["warnings"]:
            print(f"  ? {w}")

    # Write marker
    marker_dir = MODULE_ROOT / "data" / "runtime" / "status"
    marker_dir.mkdir(parents=True, exist_ok=True)
    marker_path = marker_dir / "v4_rolling_schema_check.json"
    with open(marker_path, "w") as fh:
        json.dump(results, fh, indent=2, ensure_ascii=False)
    print(f"\nMarker: {marker_path} (NOT committed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
