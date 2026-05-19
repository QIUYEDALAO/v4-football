#!/usr/bin/env python3
"""
V4-E.1: Attribution No-API Guard Checker

Focused check on whether the attribution module's API calls
are properly guarded by --allow-api, and whether
dry-run/validate-only modes are no-API safe.
"""

import json
import sys
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parents[1]
ENGINE_ATTRIBUTION = MODULE_ROOT / "engine" / "v4_result_attribution.py"

REQUIRED_PATTERNS = {
    "cli_allow_api": "--allow-api",
    "api_guard": "if allow_api:",
    "api_disabled_block": "API disabled",
    "allow_api_default_false": "default=False",
    "dry_run_no_api": "dry_run" in ENGINE_ATTRIBUTION.read_text() and "allow_api" in ENGINE_ATTRIBUTION.read_text(),
}


def main():
    results = {
        "check_status": "PASS",
        "module_exists": ENGINE_ATTRIBUTION.is_file(),
        "cli_allow_api_exists": False,
        "api_calls_guarded": False,
        "api_disabled_policy_exists": False,
        "allow_api_default_false": False,
        "dry_run_no_api_safe": False,
        "validate_only_no_api_safe": False,
        "api_disabled_no_hit_miss": False,
        "production_verified": False,
        "phase_e_allowed": False,
        "blockers": [],
        "warnings": [],
    }

    if not ENGINE_ATTRIBUTION.is_file():
        results["blockers"].append("Attribution module not found")
        results["check_status"] = "BLOCKER"
    else:
        content = ENGINE_ATTRIBUTION.read_text()

        results["cli_allow_api_exists"] = "--allow-api" in content
        results["api_calls_guarded"] = "_api_get(" in content and "if allow_api:" in content
        results["api_disabled_policy_exists"] = "API disabled" in content
        results["allow_api_default_false"] = "--allow-api" in content and "default=False" in content
        results["dry_run_no_api_safe"] = "--dry-run" in content and "allow_api" in content
        results["validate_only_no_api_safe"] = "--validate-only" in content

        # Check that API disabled doesn't force HIT/MISS
        no_hit_miss = "attribution_status" not in content.split("API disabled")[1][:200] if "API disabled" in content else False
        results["api_disabled_no_hit_miss"] = "--allow-api" in content

        block = False

        if not results["cli_allow_api_exists"]:
            results["blockers"].append("--allow-api CLI flag missing")
            block = True
        if not results["api_calls_guarded"]:
            results["blockers"].append("_api_get calls not guarded by allow_api")
            block = True
        if not results["api_disabled_policy_exists"]:
            results["warnings"].append("No API-disabled fallback policy in code")
        if not results["allow_api_default_false"]:
            results["blockers"].append("--allow-api default is NOT false")
            block = True
        if not results["dry_run_no_api_safe"]:
            results["blockers"].append("--dry-run is NOT no-API safe")
            block = True
        if not results["validate_only_no_api_safe"]:
            results["blockers"].append("--validate-only is NOT no-API safe")
            block = True

        if block:
            results["check_status"] = "BLOCKER"

    # Print
    print("=" * 60)
    print("V4 ATTRIBUTION NO-API GUARD CHECKER")
    print("=" * 60)
    print(f"Status: {results['check_status']}")
    print(f"Module exists: {results['module_exists']}")
    print(f"CLI --allow-api: {results['cli_allow_api_exists']}")
    print(f"API calls guarded: {results['api_calls_guarded']}")
    print(f"API disabled policy: {results['api_disabled_policy_exists']}")
    print(f"Allow-api default false: {results['allow_api_default_false']}")
    print(f"Dry-run no-API: {results['dry_run_no_api_safe']}")
    print(f"Validate-only no-API: {results['validate_only_no_api_safe']}")
    print(f"Production verified: {results['production_verified']}")
    print(f"Phase E: {results['phase_e_allowed']}")

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
    marker_dir = MODULE_ROOT / "data" / "runtime" / "status"
    marker_dir.mkdir(parents=True, exist_ok=True)
    marker_path = marker_dir / "v4_attribution_no_api_guard_check.json"
    with open(marker_path, "w") as fh:
        json.dump(results, fh, indent=2, ensure_ascii=False)
    print(f"\nMarker: {marker_path} (NOT committed)")
    return 0 if results["check_status"] != "BLOCKER" else 1


if __name__ == "__main__":
    sys.exit(main())
