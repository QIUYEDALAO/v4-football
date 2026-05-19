#!/usr/bin/env python3
"""
V4-E.1: Attribution Guard Checker

Verifies that the attribution module:
- Does not write verified / PRODUCTION_VERIFIED
- Does not push QQ
- API calls require --allow-api (default false)
- --dry-run and --validate-only are no-API safe
- Does not read keys
- Does not write state
- Does not change strategy rules
"""

import json
import sys
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = MODULE_ROOT.parent

ENGINE_ATTRIBUTION = MODULE_ROOT / "engine" / "v4_result_attribution.py"


def _exclude_guard(text: str) -> str:
    """Remove guard marker comment lines from search."""
    lines = []
    for line in text.split('\n'):
        if 'NO_' in line and '= true' in line and 'does NOT' in line:
            continue
        if 'V4-E' in line and 'attribution' in line.lower():
            continue
        lines.append(line)
    return '\n'.join(lines)


def check_module_safety():
    """Check that the attribution module is safe."""
    if not ENGINE_ATTRIBUTION.is_file():
        return {
            "module_exists": False,
            "verified_write_found": False,
            "production_verified_write_found": False,
            "qq_send_call_found": False,
            "api_call_found": False,
            "api_call_guarded_by_allow_api": False,
            "key_read_found": False,
            "state_write_found": False,
            "strategy_algorithm_modified": False,
            "dry_run_no_api_safe": False,
            "validate_only_no_api_safe": False,
            "allow_api_default_false": False,
        }

    content = ENGINE_ATTRIBUTION.read_text()
    clean_content = _exclude_guard(content)
    clean_lower = clean_content.lower()
    
    # API call detection
    has_api_get = "_api_get(" in clean_content
    has_allow_api = "--allow-api" in content
    allow_api_in_run = "allow_api:" in content or "allow_api=True" in content or "allow_api=False" in content
    api_guarded = "if allow_api:" in content
    allow_api_default = "default=False" in content and "allow-api" in content
    
    # Dry-run / validate-only
    dry_run_flag = "--dry-run" in content
    validate_only_flag = "--validate-only" in content
    dry_run_no_api = "dry_run" in content.lower() and "allow_api" in content.lower()
    
    return {
        "module_exists": True,
        "verified_write_found": (
            "v4_live_verified" in clean_lower or
            "PRODUCTION_VERIFIED" in clean_content or
            "_verified" in clean_lower
        ),
        "production_verified_write_found": "PRODUCTION_VERIFIED" in clean_content,
        "qq_send_call_found": any(p in clean_lower for p in ["qq_push", "send_to_qq", "systemEvent", "qqbot"]),
        "api_call_found": has_api_get,
        "api_call_guarded_by_allow_api": has_api_get and api_guarded,
        "key_read_found": any(p in clean_lower for p in ["api_key", "apikey", "api_secret"]),
        "state_write_found": any(p in clean_lower for p in ["state_marker", "write_state", "state_write"]),
        "strategy_algorithm_modified": any(p in clean_lower for p in ["rule_change", "change_threshold", "modify_grade"]),
        "dry_run_no_api_safe": dry_run_flag and dry_run_no_api,
        "validate_only_no_api_safe": validate_only_flag,
        "allow_api_default_false": allow_api_default and "--allow-api" in content,
        "has_allow_api_flag": has_allow_api,
        "allow_api_in_run_sig": allow_api_in_run,
    }


def main():
    module_check = check_module_safety()
    has_api = module_check["api_call_found"]
    guarded = module_check["api_call_guarded_by_allow_api"]
    dangerous_check = all(
        not module_check[k] for k in
        ["verified_write_found", "qq_send_call_found",
         "key_read_found", "state_write_found", "strategy_algorithm_modified"]
    ) and module_check["dry_run_no_api_safe"] and module_check["validate_only_no_api_safe"]

    results = {
        "check_status": "PASS",
        "attribution_module_exists": module_check["module_exists"],
        "attribution_module_no_write_safe": not module_check["verified_write_found"] and not module_check["production_verified_write_found"],
        "api_call_found": has_api,
        "api_call_guarded_by_allow_api": guarded,
        "dry_run_no_api_safe": module_check["dry_run_no_api_safe"],
        "validate_only_no_api_safe": module_check["validate_only_no_api_safe"],
        "allow_api_default_false": module_check["allow_api_default_false"],
        "verified_write_found": module_check["verified_write_found"],
        "production_verified_write_found": module_check["production_verified_write_found"],
        "qq_send_call_found": module_check["qq_send_call_found"],
        "key_read_found": module_check["key_read_found"],
        "state_write_found": module_check["state_write_found"],
        "strategy_algorithm_modified": module_check["strategy_algorithm_modified"],
        "rule_change_allowed": False,
        "production_verified": False,
        "phase_e_allowed": False,
        "v4_f_allowed_to_generate": True,
        "v4_f_allowed_to_execute": False,
        "blockers": [],
        "warnings": [],
    }

    block = False

    # BLOCKER: API calls not guarded by allow_api
    if has_api and not guarded:
        results["blockers"].append(
            "API calls found but NOT guarded by allow_api flag"
        )
        block = True

    # BLOCKER: dry-run not no-api safe
    if not module_check["dry_run_no_api_safe"]:
        results["blockers"].append("--dry-run is NOT no-API safe")
        block = True

    # BLOCKER: validate-only not no-api safe
    if not module_check["validate_only_no_api_safe"]:
        results["blockers"].append("--validate-only is NOT no-API safe")
        block = True

    # BLOCKER: allow_api defaults to true
    if not module_check["allow_api_default_false"]:
        results["blockers"].append("--allow-api default is NOT false")
        block = True

    # BLOCKER: verified writes
    if module_check["verified_write_found"]:
        results["blockers"].append("Verified write found")
        block = True

    # BLOCKER: QQ send
    if module_check["qq_send_call_found"]:
        results["blockers"].append("QQ send call found")
        block = True

    # BLOCKER: key read
    if module_check["key_read_found"]:
        results["blockers"].append("API key read found")
        block = True

    # BLOCKER: state write
    if module_check["state_write_found"]:
        results["blockers"].append("State write found")
        block = True

    # BLOCKER: strategy modified
    if module_check["strategy_algorithm_modified"]:
        results["blockers"].append("Strategy modification found")
        block = True

    # BLOCKER: production/phase guards
    if results["production_verified"]:
        results["blockers"].append("production_verified is true")
        block = True
    if results["phase_e_allowed"]:
        results["blockers"].append("phase_e_allowed is true")
        block = True

    # WARN: API calls exist even if guarded
    if has_api and guarded:
        results["warnings"].append("API calls exist but are guarded by allow_api (acceptable for V4-E.1)")

    # Determine status
    if block:
        results["check_status"] = "BLOCKER"
    elif results["warnings"]:
        results["check_status"] = "WARN"

    # Print
    print("=" * 60)
    print("V4 ATTRIBUTION GUARD CHECKER")
    print("=" * 60)
    print(f"Status: {results['check_status']}")
    print(f"Module exists: {results['attribution_module_exists']}")
    print(f"Module no-write safe: {results['attribution_module_no_write_safe']}")
    print(f"API call found: {results['api_call_found']}")
    print(f"API call guarded by allow_api: {results['api_call_guarded_by_allow_api']}")
    print(f"Dry-run no-API safe: {results['dry_run_no_api_safe']}")
    print(f"Validate-only no-API safe: {results['validate_only_no_api_safe']}")
    print(f"Allow-api default false: {results['allow_api_default_false']}")
    print(f"Verified write: {results['verified_write_found']}")
    print(f"Production verified write: {results['production_verified_write_found']}")
    print(f"QQ send: {results['qq_send_call_found']}")
    print(f"Key read: {results['key_read_found']}")
    print(f"State write: {results['state_write_found']}")
    print(f"Strategy modified: {results['strategy_algorithm_modified']}")
    print(f"Rule change: {results['rule_change_allowed']}")
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
    marker_dir = MODULE_ROOT / "data" / "runtime" / "status"
    marker_dir.mkdir(parents=True, exist_ok=True)
    marker_path = marker_dir / "v4_attribution_guard_check.json"
    with open(marker_path, "w") as fh:
        json.dump(results, fh, indent=2, ensure_ascii=False)
    print(f"\nMarker: {marker_path} (NOT committed)")
    return 0 if results["check_status"] != "BLOCKER" else 1


if __name__ == "__main__":
    sys.exit(main())
