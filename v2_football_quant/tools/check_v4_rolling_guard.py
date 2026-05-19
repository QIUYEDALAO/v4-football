#!/usr/bin/env python3
"""
V4-F: Rolling Guard Checker

Verifies that the rolling validation module is safe:
- No API, no key, no QQ, no state, no verified
- UNKNOWN/API_DISABLED excluded from hit/miss
- C observation-only and SKIP not-scored enforced
"""

import json
import sys
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parents[1]
ROLLING_MODULE = MODULE_ROOT / "engine" / "v4_rolling_validation.py"


def check_module():
    """Check rolling module for guard compliance."""
    if not ROLLING_MODULE.is_file():
        return {
            "module_exists": False,
            "no_write_safe": False,
            "api_call_found": False,
            "key_read_found": False,
            "qq_send_call_found": False,
            "verified_write_found": False,
            "state_write_found": False,
            "unknown_excluded": False,
            "api_disabled_excluded": False,
            "result_unknown_excluded": False,
            "skip_not_scored": False,
            "c_observation_only": False,
        }

    content = ROLLING_MODULE.read_text()
    # Exclude guard marker lines (NO_*) from search
    clean_lines = []
    for line in content.split('\n'):
        if 'NO_' in line and '= true' in line:
            continue
        clean_lines.append(line)
    clean = '\n'.join(clean_lines)
    lower = clean.lower()

    return {
        "module_exists": True,
        "no_write_safe": "--dry-run" in content and "--validate-only" in content,
        "api_call_found": any(p in lower for p in ["_api_get", "requests.", "net_utils.get"]),
        "key_read_found": any(p in lower for p in ["api_key", "apikey", "api_secret"]),
        "qq_send_call_found": any(p in lower for p in ["qq_push", "send_to_qq", "systemEvent", "qqbot"]),
        "verified_write_found": (
            "v4_live_verified" in lower or
            "_verified" in lower
        ),
        "state_write_found": any(p in lower for p in ["state_marker", "write_state"]),
        "unknown_excluded": "UNKNOWN" in content and "excluded" in lower,
        "api_disabled_excluded": "API_DISABLED" in content and "excluded" in lower,
        "result_unknown_excluded": "result_known" in lower and "excluded" in lower,
        "skip_not_scored": "SKIP" in content and ("skip" in lower and "excluded" in lower),
        "c_observation_only": "C" in content and "observation" in lower,
    }


def main():
    mc = check_module()

    results = {
        "check_status": "PASS",
        "rolling_module_exists": mc["module_exists"],
        "rolling_module_no_write_safe": mc["no_write_safe"],
        "api_call_found": mc["api_call_found"],
        "key_read_found": mc["key_read_found"],
        "qq_send_call_found": mc["qq_send_call_found"],
        "verified_write_found": mc["verified_write_found"],
        "state_write_found": mc["state_write_found"],
        "unknown_excluded_from_hit_miss": mc["unknown_excluded"],
        "api_disabled_excluded_from_hit_miss": mc["api_disabled_excluded"],
        "result_unknown_excluded_from_hit_miss": mc["result_unknown_excluded"],
        "skip_not_scored": mc["skip_not_scored"],
        "c_observation_only": mc["c_observation_only"],
        "rule_change_allowed": False,
        "production_verified": False,
        "phase_e_allowed": False,
        "v4_g_allowed_to_generate": True,
        "v4_g_allowed_to_execute": False,
        "blockers": [],
        "warnings": [],
    }

    block = False

    if not mc["no_write_safe"]:
        results["warnings"].append("Rolling module missing --dry-run or --validate-only")
    if mc["api_call_found"]:
        results["blockers"].append("API call found in rolling module")
        block = True
    if mc["key_read_found"]:
        results["blockers"].append("Key read found in rolling module")
        block = True
    if mc["qq_send_call_found"]:
        results["blockers"].append("QQ send found in rolling module")
        block = True
    if mc["verified_write_found"]:
        results["blockers"].append("Verified write found in rolling module")
        block = True
    if mc["state_write_found"]:
        results["blockers"].append("State write found in rolling module")
        block = True
    if not mc["unknown_excluded"]:
        results["blockers"].append("UNKNOWN not excluded from hit/miss")
        block = True
    if not mc["api_disabled_excluded"]:
        results["blockers"].append("API_DISABLED not excluded from hit/miss")
        block = True
    if not mc["result_unknown_excluded"]:
        results["blockers"].append("result_known=false not excluded")
        block = True
    if not mc["skip_not_scored"]:
        results["blockers"].append("SKIP not excluded from recommendation stats")
        block = True
    if not mc["c_observation_only"]:
        results["blockers"].append("C not observation-only")
        block = True

    if block:
        results["check_status"] = "BLOCKER"
    elif results["warnings"]:
        results["check_status"] = "WARN"

    # Print
    print("=" * 60)
    print("V4 ROLLING GUARD CHECKER")
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
    marker_path = marker_dir / "v4_rolling_guard_check.json"
    with open(marker_path, "w") as fh:
        json.dump(results, fh, indent=2, ensure_ascii=False)
    print(f"\nMarker: {marker_path} (NOT committed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
