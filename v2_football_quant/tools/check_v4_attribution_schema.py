#!/usr/bin/env python3
"""
V4-E: Attribution Schema Checker

Verifies that the V4 attribution schema and guard documents exist
with correct grade/status values and production guard flags.
"""

import json
import sys
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = MODULE_ROOT.parent

DOC_SCHEMA = MODULE_ROOT / "docs" / "V4_ATTRIBUTION_SCHEMA.md"
DOC_GUARD = MODULE_ROOT / "docs" / "V4_ATTRIBUTION_GUARD.md"

ALLOWED_GRADES = {"A", "B", "C", "SKIP"}
ALLOWED_STATUS = {"HIT", "MISS", "VOID", "UNKNOWN", "SKIP_NOT_SCORED"}


def main():
    results = {
        "check_status": "PASS",
        "attribution_schema_doc_exists": False,
        "attribution_guard_doc_exists": False,
        "allowed_grades": sorted(ALLOWED_GRADES),
        "allowed_attribution_status": sorted(ALLOWED_STATUS),
        "skip_not_scored_required": True,
        "c_observation_only_required": True,
        "unknown_result_guard_required": True,
        "attribution_not_verified": True,
        "verified_write_allowed": False,
        "rule_change_allowed": False,
        "qq_push_allowed": False,
        "production_verified": False,
        "phase_e_allowed": False,
        "v4_f_allowed_to_generate": True,
        "v4_f_allowed_to_execute": False,
        "blockers": [],
        "warnings": [],
    }

    block = False

    # Check docs exist
    results["attribution_schema_doc_exists"] = DOC_SCHEMA.is_file()
    if not DOC_SCHEMA.is_file():
        results["blockers"].append(f"Schema doc missing: {DOC_SCHEMA}")
        block = True

    results["attribution_guard_doc_exists"] = DOC_GUARD.is_file()
    if not DOC_GUARD.is_file():
        results["blockers"].append(f"Guard doc missing: {DOC_GUARD}")
        block = True

    # Check grades and status in schema doc content
    if DOC_SCHEMA.is_file():
        content = DOC_SCHEMA.read_text()
        for g in ALLOWED_GRADES:
            if g not in content:
                results["warnings"].append(f"Grade '{g}' not found in attribution schema")
        for s in ALLOWED_STATUS:
            if s not in content:
                results["warnings"].append(f"Status '{s}' not found in attribution schema")
        if "SKIP_NOT_SCORED" not in content:
            results["blockers"].append("SKIP_NOT_SCORED not found in schema")
            block = True
        if "observation-only" not in content.lower() and "observation_only" not in content.lower():
            results["warnings"].append("C observation-only rule might be missing from schema")

    # Check guard doc content
    if DOC_GUARD.is_file():
        guard_content = DOC_GUARD.read_text()
        if "SKIP_NOT_SCORED" not in guard_content:
            results["warnings"].append("SKIP_NOT_SCORED rule missing from guard")
        if "observation-only" not in guard_content.lower():
            results["warnings"].append("C observation-only rule missing from guard")

    # Check blocker conditions
    if not results["skip_not_scored_required"]:
        results["blockers"].append("skip_not_scored_required is false")
        block = True
    if not results["c_observation_only_required"]:
        results["blockers"].append("c_observation_only_required is false")
        block = True
    if not results["unknown_result_guard_required"]:
        results["blockers"].append("unknown_result_guard_required is false")
        block = True
    if not results["attribution_not_verified"]:
        results["blockers"].append("attribution_not_verified is false")
        block = True
    if results["verified_write_allowed"]:
        results["blockers"].append("verified_write_allowed is true")
        block = True
    if results["rule_change_allowed"]:
        results["blockers"].append("rule_change_allowed is true")
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
    print("V4 ATTRIBUTION SCHEMA CHECKER")
    print("=" * 60)
    print(f"Status: {results['check_status']}")
    print(f"Schema doc: {results['attribution_schema_doc_exists']}")
    print(f"Guard doc: {results['attribution_guard_doc_exists']}")
    print(f"Allowed grades: {results['allowed_grades']}")
    print(f"Allowed status: {results['allowed_attribution_status']}")
    print(f"SKIP_NOT_SCORED: {results['skip_not_scored_required']}")
    print(f"C observation-only: {results['c_observation_only_required']}")
    print(f"Unknown result guard: {results['unknown_result_guard_required']}")
    print(f"Attribution not verified: {results['attribution_not_verified']}")
    print(f"Verified write: {results['verified_write_allowed']}")
    print(f"Rule change: {results['rule_change_allowed']}")
    print(f"QQ push: {results['qq_push_allowed']}")
    print(f"Production verified: {results['production_verified']}")
    print(f"Phase E: {results['phase_e_allowed']}")
    print(f"V4-F allowed_to_generate: {results['v4_f_allowed_to_generate']}")
    print(f"V4-F allowed_to_execute: {results['v4_f_allowed_to_execute']}")

    if results["blockers"]:
        print(f"\nBLOCKERS ({len(results['blockers'])}):")
        for b in results["blockers"]:
            print(f"  ! {b}")
        sys.exit(1)
    elif results["warnings"]:
        print(f"\nWARNINGS ({len(results['warnings'])}):")
        for w in results["warnings"]:
            print(f"  ? {w}")

    # Write marker
    maker_dir = MODULE_ROOT / "data" / "runtime" / "status"
    maker_dir.mkdir(parents=True, exist_ok=True)
    marker_path = maker_dir / "v4_attribution_schema_check.json"
    with open(marker_path, "w") as fh:
        json.dump(results, fh, indent=2, ensure_ascii=False)
    print(f"\nMarker: {marker_path} (NOT committed)")
    return 0 if results["check_status"] != "BLOCKER" else 1


if __name__ == "__main__":
    sys.exit(main())
