#!/usr/bin/env python3
"""V4 Wrapper Regression Checker — validates wrapper supports all required flags and guards."""
import argparse
import ast
import json
import re
import subprocess
import sys
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]
WRAPPER = MODULE / "tools" / "run_v4_window_scan_capture_readonly.py"


def extract_argparse_adds(source: str):
    """Extract add_argument calls from source."""
    calls = []
    for m in re.finditer(r"p\.add_argument\((['\"])(--[^'\"]+)\\1", source):
        calls.append(m.group(2))
    return calls


def check_arg_in_source(source: str, flag: str) -> bool:
    return flag in source


def check_default_true(source: str, flag: str) -> bool:
    """Check if a flag has default=True."""
    pattern = rf"add_argument\(['\"]{re.escape(flag)}['\"].*default\s*=\s*True"
    return bool(re.search(pattern, source))


def check_synthetic_evidence(source: str) -> bool:
    return '"synthetic_evidence": False' in source or "synthetic_evidence" in source and "False" in source


def check_before_after_hash(source: str) -> bool:
    return "before_hash" in source or "scout_before_hash" in source


def check_window_specific_checker_not_bypassed(source: str) -> bool:
    """Wrapper should not call check_v4_next_scan_window_capture or bypass it."""
    return "check_v4_next_scan_window_capture" not in source


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="Output JSON only")
    args = parser.parse_args()

    R = {
        "checker": "v4_wrapper_regression",
        "check_status": "PASS",
        "wrapper_path": str(WRAPPER),
        "wrapper_exists": False,
        "tests": {},
        "blockers": [],
        "warnings": [],
        "generated_at": None,
    }

    from datetime import datetime, timezone, timedelta
    tz = timezone(timedelta(hours=8))
    R["generated_at"] = datetime.now(tz).strftime("%Y-%m-%dT%H:%M:%S+08:00")

    if not WRAPPER.is_file():
        R["check_status"] = "BLOCKER"
        R["blockers"].append("wrapper_file_not_found")
        R["wrapper_exists"] = False
        print(json.dumps(R, ensure_ascii=False, indent=2))
        return 2

    R["wrapper_exists"] = True
    source = WRAPPER.read_text()

    # 1. --window support
    t1 = check_arg_in_source(source, "--window")
    R["tests"]["supports_window_flag"] = t1
    if not t1:
        R["blockers"].append("missing --window flag")

    # 2. --scan-date support
    t2 = check_arg_in_source(source, "--scan-date")
    R["tests"]["supports_scan_date_flag"] = t2
    if not t2:
        R["blockers"].append("missing --scan-date flag")

    # 3. Correctly passes runner date parameter
    t3 = "--date" in source and "scan_date" in source
    R["tests"]["passes_date_to_runner"] = t3
    if not t3:
        R["warnings"].append("runner date parameter not found")

    # 4. --preflight support
    t4 = check_arg_in_source(source, "--preflight")
    R["tests"]["supports_preflight"] = t4
    if not t4:
        R["warnings"].append("missing --preflight flag")

    # 5. --no-push
    t5 = check_arg_in_source(source, "--no-push") and check_default_true(source, "--no-push")
    R["tests"]["supports_no_push_default_true"] = t5
    if not t5:
        R["blockers"].append("missing --no-push or default not True")

    # 6. --no-d13
    t6 = check_arg_in_source(source, "--no-d13") and check_default_true(source, "--no-d13")
    R["tests"]["supports_no_d13_default_true"] = t6
    if not t6:
        R["blockers"].append("missing --no-d13 or default not True")

    # 7. --no-v33
    t7 = check_arg_in_source(source, "--no-v33") and check_default_true(source, "--no-v33")
    R["tests"]["supports_no_v33_default_true"] = t7
    if not t7:
        R["blockers"].append("missing --no-v33 or default not True")

    # 8. --no-hourly
    t8 = check_arg_in_source(source, "--no-hourly") and check_default_true(source, "--no-hourly")
    R["tests"]["supports_no_hourly_default_true"] = t8
    if not t8:
        R["blockers"].append("missing --no-hourly or default not True")

    # 9. No synthetic evidence
    t9 = check_synthetic_evidence(source)
    R["tests"]["no_synthetic_evidence"] = t9
    if not t9:
        R["blockers"].append("synthetic_evidence not hardcoded False")

    # 10. Does not bypass window-specific checker
    t10 = check_window_specific_checker_not_bypassed(source)
    R["tests"]["does_not_bypass_window_checker"] = t10
    if not t10:
        R["warnings"].append("wrapper imports or calls check_v4_next_scan_window_capture")

    # Bonus checks
    R["tests"]["has_before_after_hash"] = check_before_after_hash(source)
    R["tests"]["env_openclaw_no_push_set"] = "OPENCLAW_NO_PUSH" in source
    R["tests"]["scout_after_hash_evidence"] = "scout_after_hash" in source
    R["tests"]["production_evidence_logic"] = "production_evidence" in source and "scout_after_hash" in source

    passed = sum(1 for v in R["tests"].values() if v)
    R["tests_passed"] = passed
    R["tests_total"] = len(R["tests"])

    if R["blockers"]:
        R["check_status"] = "BLOCKER"
    elif R["warnings"]:
        R["check_status"] = "WARN"

    if not args.json:
        print("=" * 60)
        print("V4 WRAPPER REGRESSION CHECKER")
        print("=" * 60)
        print(f"Status: {R['check_status']} | Passed: {passed}/{len(R['tests'])}")
        for k, v in R["tests"].items():
            print(f"  {k}: {'PASS' if v else 'FAIL'}")
        if R["blockers"]:
            print(f"\nBLOCKERS: {R['blockers']}")
        if R["warnings"]:
            print(f"\nWARNINGS: {R['warnings']}")

    out = MODULE / "data" / "runtime" / "status" / "v4_wrapper_regression_check_20260520.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(R, ensure_ascii=False, indent=2))

    print(json.dumps(R, ensure_ascii=False, indent=2) if args.json else "")
    return 0 if R["check_status"] == "PASS" else (1 if R["check_status"] == "WARN" else 2)


if __name__ == "__main__":
    sys.exit(main())
