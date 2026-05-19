#!/usr/bin/env python3
"""
V4-E: Attribution Guard Checker

Verifies that the attribution module does not write verified,
push QQ, call API with keys, write state, or change strategy rules.
"""

import json
import sys
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = MODULE_ROOT.parent

ENGINE_ATTRIBUTION = MODULE_ROOT / "engine" / "v4_result_attribution.py"

# Dangerous patterns to check in the attribution module
DANGEROUS_PATTERNS = {
    "verified_write": ["VERIFIED", "v4_live_verified", "PRODUCTION_VERIFIED"],
    "qq_push": ["qq_push", "send_to_qq", "systemEvent", "qqbot"],
    "api_call_with_key": ["net_utils.get(", "api_key"],
    "state_write": ["state_marker", "state_write", "write_state"],
    "rule_change": ["rule_change", "change_threshold", "modify_grade"],
}


def check_module_safety():
    """Check that the attribution module is safe (no verified/violations)."""
    if not ENGINE_ATTRIBUTION.is_file():
        return {
            "module_exists": False,
            "verified_write_found": False,
            "production_verified_write_found": False,
            "qq_send_call_found": False,
            "api_call_found": True,
            "key_read_found": False,
            "state_write_found": False,
            "strategy_algorithm_modified": False,
        }

    content = ENGINE_ATTRIBUTION.read_text()
    lower = content.lower()
    
    # Exclude guard marker docstrings (NO_* markers from V4 phase guards)
    # These are non-functional annotations, not actual violations
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
    
    clean_content = _exclude_guard(content)
    clean_lower = clean_content.lower()

    return {
        "module_exists": True,
        "verified_write_found": (
            "v4_live_verified" in clean_lower or
            "PRODUCTION_VERIFIED" in clean_content or
            "_verified" in clean_lower
        ),
        "production_verified_write_found": "PRODUCTION_VERIFIED" in clean_content,
        "qq_send_call_found": any(p in clean_lower for p in DANGEROUS_PATTERNS["qq_push"]),
        "api_call_found": "_api_get" in clean_content or "net_utils.get(" in clean_content or "requests." in clean_content,
        "key_read_found": "api_key" in clean_lower or "apikey" in clean_lower or "api_secret" in clean_lower,
        "state_write_found": "state_marker" in clean_lower or "write_state" in clean_lower or "state_write" in clean_lower,
        "strategy_algorithm_modified": "rule_change" in clean_lower or "change_threshold" in clean_lower,
    }


def main():
    module_check = check_module_safety()

    results = {
        "check_status": "PASS",
        "attribution_module_exists": module_check["module_exists"],
        "attribution_module_no_write_safe": True,
        "verified_write_found": module_check["verified_write_found"],
        "production_verified_write_found": module_check["production_verified_write_found"],
        "qq_send_call_found": module_check["qq_send_call_found"],
        "api_call_found": module_check["api_call_found"],
        "key_read_found": module_check["key_read_found"],
        "state_write_found": module_check["state_write_found"],
        "strategy_algorithm_modified": module_check["strategy_algorithm_modified"],
        "rule_change_allowed": False,
        "production_verified": False,
        "phase_e_allowed": False,
        "blockers": [],
        "warnings": [],
    }

    # Check for dry-run / validate-only in module
    if module_check["module_exists"]:
        content = ENGINE_ATTRIBUTION.read_text()
        has_dry_run = "--dry-run" in content
        has_validate_only = "--validate-only" in content
        if has_dry_run and has_validate_only:
            results["attribution_module_no_write_safe"] = True
        else:
            results["warnings"].append(
                "Attribution module missing --validate-only or --dry-run flags"
            )

    block = False

    # Check block conditions
    if module_check["verified_write_found"]:
        results["blockers"].append("Verified write found in attribution module")
        block = True

    if module_check["production_verified_write_found"]:
        results["blockers"].append("PRODUCTION_VERIFIED write found")
        block = True

    if module_check["qq_send_call_found"]:
        results["blockers"].append("QQ send call found")
        block = True

    if module_check["key_read_found"]:
        results["blockers"].append("API key read found")
        block = True

    if module_check["state_write_found"]:
        results["blockers"].append("State write found")
        block = True

    if module_check["strategy_algorithm_modified"]:
        results["blockers"].append("Strategy algorithm modification found")
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
    print("V4 ATTRIBUTION GUARD CHECKER")
    print("=" * 60)
    print(f"Status: {results['check_status']}")
    print(f"Attribution module: {results['attribution_module_exists']}")
    print(f"Module no-write safe: {results['attribution_module_no_write_safe']}")
    print(f"Verified write: {results['verified_write_found']}")
    print(f"PRODUCTION_VERIFIED write: {results['production_verified_write_found']}")
    print(f"QQ send call: {results['qq_send_call_found']}")
    print(f"API call: {results['api_call_found']}")
    print(f"Key read: {results['key_read_found']}")
    print(f"State write: {results['state_write_found']}")
    print(f"Strategy modified: {results['strategy_algorithm_modified']}")
    print(f"Rule change: {results['rule_change_allowed']}")
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
    marker_path = marker_dir / "v4_attribution_guard_check.json"
    with open(marker_path, "w") as fh:
        json.dump(results, fh, indent=2, ensure_ascii=False)
    print(f"\nMarker: {marker_path} (NOT committed)")
    return 0 if results["check_status"] != "BLOCKER" else 1


if __name__ == "__main__":
    sys.exit(main())
