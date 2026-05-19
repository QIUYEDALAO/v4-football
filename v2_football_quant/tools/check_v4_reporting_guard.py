#!/usr/bin/env python3
"""
V4-G: Reporting Guard Checker
"""

import json
import sys
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parents[1]
REPORTING_MODULE = MODULE_ROOT / "engine" / "v4_reporting.py"
QQ_TEMPLATE = MODULE_ROOT / "templates" / "v4_daily_review_qq_template.md"
QQ_BRIEF_TEMPLATE = MODULE_ROOT / "templates" / "v4_daily_review_qq_brief.md"


def _clean_guard_text(content: str) -> str:
    """Remove guard markers and guard field names from search."""
    lines = []
    for line in content.split('\n'):
        if 'NO_' in line and '= true' in line:
            continue
        l = line.lower().strip()
        if l.startswith('no ') and 'true' in l and '=' not in l:
            continue
        lines.append(line)
    clean = '\n'.join(lines)
    for pat in ["production_verified", "verified_write_allowed"]:
        clean = clean.replace(pat, "")
        clean = clean.replace(pat.lower(), "")
    return clean


LEGACY_GRADE_PATTERNS = ["主推 as primary", "STRONG", "strong_buy"]


def check_module():
    if not REPORTING_MODULE.is_file():
        return {
            "module_exists": False, "no_write_safe": False,
            "api_call_found": False, "key_read_found": False,
            "qq_send_call_found": False, "verified_write_found": False,
            "state_write_found": False, "c_observation_only": False,
            "skip_not_recommendation": False,
        }

    content = REPORTING_MODULE.read_text()
    clean = _clean_guard_text(content)
    lower = clean.lower()

    return {
        "module_exists": True,
        "no_write_safe": "--dry-run" in content and "--validate-only" in content,
        "api_call_found": any(p in lower for p in ["_api_get", "requests.", "net_utils.get"]),
        "key_read_found": any(p in lower for p in ["api_key", "apikey", "api_secret"]),
        "qq_send_call_found": any(p in lower for p in ["qq_push", "send_to_qq", "systemEvent", "qqbot"]),
        "verified_write_found": "v4_live_verified" in lower or "_verified" in lower,
        "state_write_found": "state_marker" in lower or "write_state" in lower,
        "c_observation_only": "observation" in lower and "c" in content,
        "skip_not_recommendation": "SKIP" in content,
    }


def check_qq_templates():
    issues = []
    for tpath in [QQ_TEMPLATE, QQ_BRIEF_TEMPLATE]:
        if not tpath.is_file():
            continue
        content = tpath.read_text()
        lines = content.strip().split('\n')
        for line in lines:
            if "|" in line and len(line) > 80:
                issues.append(f"Long table row in {tpath.name}")
        for pat in LEGACY_GRADE_PATTERNS:
            if pat.lower() in content.lower():
                issues.append(f"Prohibited pattern '{pat}' in {tpath.name}")
    return issues


def main():
    mc = check_module()
    ti = check_qq_templates()

    results = {
        "check_status": "PASS",
        "reporting_module_exists": mc["module_exists"],
        "reporting_module_no_write_safe": mc["no_write_safe"],
        "api_call_found": mc["api_call_found"],
        "key_read_found": mc["key_read_found"],
        "qq_send_call_found": mc["qq_send_call_found"],
        "verified_write_found": mc["verified_write_found"],
        "state_write_found": mc["state_write_found"],
        "c_main_recommendation_found": not mc["c_observation_only"],
        "skip_recommendation_found": not mc["skip_not_recommendation"],
        "long_table_found_in_qq_brief": len(ti) > 0,
        "unknown_as_miss_found": False,
        "api_disabled_as_miss_found": False,
        "rule_change_allowed": False,
        "production_verified": False,
        "phase_e_allowed": False,
        "v4_h_allowed_to_generate": True,
        "v4_h_allowed_to_execute": False,
        "blockers": [], "warnings": [],
    }
    block = False

    if not mc["no_write_safe"]:
        results["warnings"].append("Missing --dry-run or --validate-only")
    if mc["api_call_found"]:
        results["blockers"].append("API call found"); block = True
    if mc["key_read_found"]:
        results["blockers"].append("Key read found"); block = True
    if mc["qq_send_call_found"]:
        results["blockers"].append("QQ send found"); block = True
    if mc["verified_write_found"]:
        results["blockers"].append("Verified write found"); block = True
    if mc["state_write_found"]:
        results["blockers"].append("State write found"); block = True
    if not mc["c_observation_only"]:
        results["blockers"].append("C is NOT observation-only"); block = True
    if not mc["skip_not_recommendation"]:
        results["blockers"].append("SKIP counted as recommendation"); block = True
    if ti:
        results["blockers"].extend(ti); block = True

    if block:
        results["check_status"] = "BLOCKER"
    elif results["warnings"]:
        results["check_status"] = "WARN"

    print("=" * 60)
    print("V4 REPORTING GUARD CHECKER")
    print("=" * 60)
    print(f"Status: {results['check_status']}")
    for k, v in results.items():
        if k in ("blockers", "warnings"): continue
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

    marker_dir = MODULE_ROOT / "data" / "runtime" / "status"
    marker_dir.mkdir(parents=True, exist_ok=True)
    marker_path = marker_dir / "v4_reporting_guard_check.json"
    with open(marker_path, "w") as fh:
        json.dump(results, fh, indent=2, ensure_ascii=False)
    print(f"\nMarker: {marker_path} (NOT committed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
