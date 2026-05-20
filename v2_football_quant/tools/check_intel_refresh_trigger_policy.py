#!/usr/bin/env python3
"""
V4-IRT-1: Intel Refresh Trigger Policy Checker

Checks that:
- no_fixed_delay_refresh = true
- fixed_1202_absent = true, fixed_1302_absent = true, etc.
- event_refresh_after_success_defined = true
- completion_condition_required = true
- output_freshness_check_required = true
- partial_output_guard_required = true
- failure_status_refresh_defined = true
- fallback_refresh_time = 15:10
- fallback_refresh_only = true
- fallback_refresh_not_only_refresh = true
- qq_preview_reads_latest = true
- qq_preview_does_not_trigger_scan = true
- refresh_does_not_trigger_scan = true
- refresh_does_not_trigger_validation = true
- refresh_no_push = true
- refresh_no_state_write = true
- refresh_no_verified_write = true
- phase_e = false
- d13_execute = false
"""

import re, sys, json
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
DOCS = WORKSPACE / "docs"

EXPECTED_MARKERS = {
    "NO_FIXED_DELAY_REFRESH": "true",
    "NO_1202_FIXED": "true",
    "NO_1302_FIXED": "true",
    "NO_1402_FIXED": "true",
    "NO_1502_FIXED": "true",
    "NO_2347_FIXED": "true",
    "EVENT_REFRESH_AFTER_SUCCESS_DEFINED": "true",
    "COMPLETION_CONDITION_REQUIRED": "true",
    "OUTPUT_FRESHNESS_CHECK_REQUIRED": "true",
    "PARTIAL_OUTPUT_GUARD_REQUIRED": "true",
    "FAILURE_STATUS_REFRESH_DEFINED": "true",
    "FALLBACK_REFRESH_ONLY": "true",
    "FALLBACK_REFRESH_NOT_ONLY_REFRESH": "true",
    "QQ_PREVIEW_READS_LATEST": "true",
    "QQ_PREVIEW_NO_SCAN": "true",
    "REFRESH_NO_SCAN": "true",
    "REFRESH_NO_VALIDATION": "true",
    "REFRESH_NO_PUSH": "true",
    "REFRESH_NO_STATE_WRITE": "true",
    "REFRESH_NO_VERIFIED_WRITE": "true",
    "PHASE_E": "false",
    "D13_EXECUTE": "false",
}

# In trigger policy doc and target policy doc, check for fallback_time
FALLBACK_TIME_TARGETS = {
    "INTEL_SCHEDULER_TARGET_POLICY.md": "15:10",
    "INTEL_REFRESH_TRIGGER_POLICY.md": "15:10",
    "INTEL_TASK_COMPLETION_REFRESH_CONTRACT.md": "15:10",
}


def parse_markers(text: str) -> dict[str, str]:
    markers = {}
    for line in text.splitlines():
        line = line.strip()
        m = re.match(r"^([A-Z][A-Z0-9_]+)\s*=\s*(\S+)", line)
        if m:
            markers[m.group(1)] = m.group(2).rstrip(",;.")
    return markers


def check_doc(path: Path, expected: dict[str, str], label: str) -> dict:
    R: dict = {"exists": False, "markers": {}, "missing": [], "mismatch": [], "status": "PASS"}
    if not path.is_file():
        R["status"] = "FAIL"
        R["missing"].append(f"{label} not found: {path}")
        return R
    R["exists"] = True
    text = path.read_text(encoding="utf-8")
    R["markers"] = parse_markers(text)
    for key, expected_val in expected.items():
        actual = R["markers"].get(key)
        if actual is None:
            R["missing"].append(f"{key} (expected={expected_val})")
            R["status"] = "WARN"
        elif actual.lower() != expected_val.lower():
            R["mismatch"].append(f"{key}={actual} (expected={expected_val})")
            R["status"] = "FAIL"
    if R["status"] == "PASS" and not R["missing"] and not R["mismatch"]:
        R["status"] = "PASS"
    elif R["status"] != "FAIL" and R["missing"]:
        R["status"] = "WARN"
    return R


def grep_fixed_delay(path: Path) -> list:
    """Check for any 12:02/13:02/14:02/15:02 references in doc text."""
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8")
    found = []
    for line in text.splitlines():
        if re.search(r"12:02|13:02|14:02|15:02|23:47", line):
            line_stripped = line.strip()
            # Allow if in legacy/context/checklist context
            allowed = ["已废弃", "旧机制", "OLD", "FORBIDDEN", "严禁", "禁止",
                       "删除", "BLOCKER", "❌", "不安全", "absent"]
            if any(x in line_stripped for x in allowed):
                continue
            if "[x]" in line_stripped or line_stripped.startswith("- ["):
                continue
            found.append(f"{path.name}: {line_stripped[:120]}")
    return found


def main():
    R = {
        "check_status": "PASS",
        "blockers": [],
        "warnings": [],
        "trigger_policy": {},
        "target_policy": {},
        "migration_plan": {},
        "completion_contract": {},
        "fixed_delay_residue": [],
        "fallback_time_checks": {},
    }

    # ── Check refresh trigger policy doc ──
    tp = DOCS / "INTEL_REFRESH_TRIGGER_POLICY.md"
    R["trigger_policy"] = check_doc(tp, EXPECTED_MARKERS, "INTEL_REFRESH_TRIGGER_POLICY")

    # ── Check target policy doc ──
    tgt = DOCS / "INTEL_SCHEDULER_TARGET_POLICY.md"
    TARGET_EXPECTED = {k: v for k, v in EXPECTED_MARKERS.items()
                       if k in ["NO_FIXED_DELAY_REFRESH", "NO_1202_FIXED", "NO_1302_FIXED",
                                "NO_1402_FIXED", "NO_1502_FIXED", "NO_2347_FIXED",
                                "FALLBACK_REFRESH_ONLY", "FALLBACK_REFRESH_NOT_ONLY_REFRESH",
                                "QQ_PREVIEW_READS_LATEST", "QQ_PREVIEW_NO_SCAN",
                                "REFRESH_NO_SCAN", "REFRESH_NO_VALIDATION",
                                "REFRESH_NO_PUSH", "PHASE_E", "D13_EXECUTE"]}
    R["target_policy"] = check_doc(tgt, TARGET_EXPECTED, "INTEL_SCHEDULER_TARGET_POLICY")

    # ── Check migration plan doc ──
    mp = DOCS / "INTEL_SCHEDULER_MIGRATION_PLAN.md"
    R["migration_plan"] = check_doc(mp, {
        "SCHEDULER_USES_COMPLETION_BASED_REFRESH": "true",
        "NO_FIXED_DELAY_REFRESH": "true",
        "ALL_CORE_TASKS_HAVE_COMPLETION_CONDITION": "true",
        "FALLBACK_REFRESH_ONLY": "true",
        "HIGH_FREQ_TASKS_HAVE_THROTTLE": "true",
        "D13": "false",
        "PHASE_E": "false",
    }, "INTEL_SCHEDULER_MIGRATION_PLAN")

    # ── Check completion contract doc ──
    cc = DOCS / "INTEL_TASK_COMPLETION_REFRESH_CONTRACT.md"
    R["completion_contract"] = check_doc(cc, {
        "COMPLETION_REFRESH_DEFINED": "true",
        "FALLBACK_REFRESH_ONLY": "true",
        "FALLBACK_REFRESH_NOT_ONLY_REFRESH": "true",
        "OUTPUT_FRESHNESS_CHECK_DEFINED": "true",
        "PARTIAL_OUTPUT_GUARD_DEFINED": "true",
        "QQ_PREVIEW_READS_LATEST": "true",
        "REFRESH_NO_SCAN": "true",
        "PHASE_E": "false",
        "D13_EXECUTE": "false",
    }, "INTEL_TASK_COMPLETION_REFRESH_CONTRACT")

    # ── Check for fixed delay residue ──
    for doc_name in ["INTEL_REFRESH_TRIGGER_POLICY.md", "INTEL_SCHEDULER_TARGET_POLICY.md",
                     "INTEL_SCHEDULER_MIGRATION_PLAN.md", "INTEL_TASK_COMPLETION_REFRESH_CONTRACT.md"]:
        residue = grep_fixed_delay(DOCS / doc_name)
        R["fixed_delay_residue"].extend(residue)
    if R["fixed_delay_residue"]:
        R["blockers"].append(f"Fixed delay residue found: {R['fixed_delay_residue']}")

    # ── Check fallback time ──
    for fname, expected_time in FALLBACK_TIME_TARGETS.items():
        fp = DOCS / fname
        if fp.is_file():
            text = fp.read_text(encoding="utf-8")
            match_15_10 = re.search(r"15:10", text)
            match_fallback = re.search(r"fallback", text, re.IGNORECASE)
            R["fallback_time_checks"][fname] = {
                "has_15_10": bool(match_15_10),
                "has_fallback_keyword": bool(match_fallback),
            }
            if not match_15_10:
                R["warnings"].append(f"{fname}: missing 15:10 fallback time")

    # ── Collect blockers ──
    for check_name, check_r in [("trigger_policy", R["trigger_policy"]),
                                 ("target_policy", R["target_policy"]),
                                 ("migration_plan", R["migration_plan"]),
                                 ("completion_contract", R["completion_contract"])]:
        if check_r["status"] == "FAIL":
            R["blockers"].append(f"{check_name} FAIL: {check_r['mismatch']}")
        elif check_r["status"] == "WARN":
            R["warnings"].append(f"{check_name} WARN: {check_r['missing']}")

    # ── Final ──
    if R["blockers"]:
        R["check_status"] = "BLOCKER"
    elif R["warnings"]:
        R["check_status"] = "WARN"

    # ── Output ──
    print("=" * 55)
    print("INTEL REFRESH TRIGGER POLICY CHECKER")
    print("=" * 55)
    print(f"\nStatus: {R['check_status']}")

    for label, r_data in [("INTEL_REFRESH_TRIGGER_POLICY", R["trigger_policy"]),
                          ("INTEL_SCHEDULER_TARGET_POLICY", R["target_policy"]),
                          ("INTEL_SCHEDULER_MIGRATION_PLAN", R["migration_plan"]),
                          ("INTEL_TASK_COMPLETION_REFRESH_CONTRACT", R["completion_contract"])]:
        print(f"\n── {label} ──")
        print(f"  exists: {r_data['exists']}  |  status: {r_data['status']}")
        for k, v in sorted((r_data.get("markers") or {}).items()):
            print(f"    {k}: {v}")

    print(f"\n── Fixed Delay Residue ──")
    if R["fixed_delay_residue"]:
        for r in R["fixed_delay_residue"]:
            print(f"  ! {r}")
    else:
        print("  ✅ None found")

    print(f"\n── Fallback Time Checks ──")
    for fname, checks in R["fallback_time_checks"].items():
        print(f"  {fname}: 15:10={checks['has_15_10']} fallback={checks['has_fallback_keyword']}")

    if R["blockers"]:
        print(f"\n  BLOCKERS ({len(R['blockers'])}):")
        for b in R["blockers"]:
            print(f"    ! {b}")
    if R["warnings"]:
        print(f"\n  WARNINGS ({len(R['warnings'])}):")
        for w in R["warnings"]:
            print(f"    ~ {w}")

    print(f"\nFinal: {R['check_status']}")

    # Write status
    status_dir = WORKSPACE / "v2_football_quant" / "data" / "runtime" / "status"
    status_dir.mkdir(parents=True, exist_ok=True)
    (status_dir / "check_intel_refresh_trigger_policy.json").write_text(
        json.dumps({k: v for k, v in R.items() if k != "fixed_delay_residue"}, indent=2, ensure_ascii=False, default=str)
    )

    if R["check_status"] == "BLOCKER":
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
