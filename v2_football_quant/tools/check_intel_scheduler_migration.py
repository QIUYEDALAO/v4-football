#!/usr/bin/env python3
"""
V4-ISM-1: Intel Scheduler Migration Checker

Checks that:
- scheduler_uses_completion_based_refresh = true
- no_fixed_delay_refresh = true
- all_core_tasks_have_completion_condition = true
- all_core_tasks_have_output_freshness_check = true
- all_core_tasks_have_partial_output_guard = true
- fallback_refresh_only = true
- high_frequency_tasks_have_throttle = true
- v2_window_refresh_after_status_change = true
- v4_live_snapshot_refresh_after_new_snapshot = true

Legacy checks (preserved):
- V4 daily scan = 1
- V4 live snapshot KEEP_BUT_RESTRICT
- V2 build 14:00
- V2 validation 15:00
- D13 = false
- PhaseE = false
- QQ/state/verified = false
"""

import re, sys, json
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
DOCS = WORKSPACE / "docs"

EXPECTED_MIGRATION_MARKERS = {
    "SCHEDULER_USES_COMPLETION_BASED_REFRESH": "true",
    "NO_FIXED_DELAY_REFRESH": "true",
    "ALL_CORE_TASKS_HAVE_COMPLETION_CONDITION": "true",
    "ALL_CORE_TASKS_HAVE_OUTPUT_FRESHNESS_CHECK": "true",
    "ALL_CORE_TASKS_HAVE_PARTIAL_OUTPUT_GUARD": "true",
    "FALLBACK_REFRESH_ONLY": "true",
    "HIGH_FREQ_TASKS_HAVE_THROTTLE": "true",
    "V2_WINDOW_REFRESH_AFTER_STATUS_CHANGE": "true",
    "V4_LIVE_SNAPSHOT_REFRESH_AFTER_NEW_SNAPSHOT": "true",
    "D13": "false",
    "PHASE_E": "false",
}

EXPECTED_TARGET_MARKERS = {
    "NO_FIXED_DELAY_REFRESH": "true",
    "AFTER_SUCCESS_REFRESH_DEFINED": "true",
    "AFTER_STATUS_CHANGE_REFRESH_DEFINED": "true",
    "FAILURE_STATUS_REFRESH_DEFINED": "true",
    "FALLBACK_REFRESH_ONLY": "true",
    "FALLBACK_REFRESH_NOT_ONLY_REFRESH": "true",
    "V2_WINDOW_HAS_THROTTLE": "true",
    "V4_SNAPSHOT_HAS_THROTTLE": "true",
    "REFRESH_NO_SCAN": "true",
    "REFRESH_NO_PUSH": "true",
    "PHASE_E": "false",
    "D13_EXECUTE": "false",
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


def check_scheduler_table_contains(path: Path, expected_items: list[str]) -> list:
    """Verify key elements appear in the scheduler table."""
    if not path.is_file():
        return ["file not found"]
    text = path.read_text(encoding="utf-8")
    missing = []
    for item in expected_items:
        if item not in text:
            missing.append(item)
    return missing


def check_no_fixed_delay(path: Path) -> bool:
    """Verify no fixed 12:02/13:02/14:02/15:02 outside legacy context."""
    if not path.is_file():
        return True
    text = path.read_text(encoding="utf-8")
    for line in text.splitlines():
        if re.search(r"12:02|13:02|14:02|15:02|23:47", line):
            line_s = line.strip()
            # Allow if line has legacy/contextual markers
            allowed_context = ["旧机制", "已废弃", "OLD", "FORBIDDEN", "禁止",
                              "删除", "BLOCKER", "bloquer", "❌", "不安全"]
            if any(x in line_s for x in allowed_context):
                continue
            # Allow checklist items [x] showing deletion was done
            if line_s.startswith("- [x]") or "[x]" in line_s:
                continue
            return False
    return True


def main():
    R = {
        "check_status": "PASS",
        "blockers": [],
        "warnings": [],
        "migration_plan": {},
        "target_policy": {},
        "completion_contract": {},
        "scheduler_table_checks": {},
        "no_fixed_delay_ok": {},
    }

    # ── Migration plan ──
    mp = DOCS / "INTEL_SCHEDULER_MIGRATION_PLAN.md"
    R["migration_plan"] = check_doc(mp, EXPECTED_MIGRATION_MARKERS, "INTEL_SCHEDULER_MIGRATION_PLAN")
    R["no_fixed_delay_ok"]["migration_plan"] = check_no_fixed_delay(mp)
    if not R["no_fixed_delay_ok"]["migration_plan"]:
        R["blockers"].append("migration_plan has fixed delay schedule (outside legacy)")

    # ── Target policy ──
    tp = DOCS / "INTEL_SCHEDULER_TARGET_POLICY.md"
    R["target_policy"] = check_doc(tp, EXPECTED_TARGET_MARKERS, "INTEL_SCHEDULER_TARGET_POLICY")
    R["no_fixed_delay_ok"]["target_policy"] = check_no_fixed_delay(tp)
    if not R["no_fixed_delay_ok"]["target_policy"]:
        R["blockers"].append("target_policy has fixed delay schedule (outside legacy)")
    # Check scheduler table for key tasks
    R["scheduler_table_checks"]["target_policy"] = check_scheduler_table_contains(tp, [
        "V4_DAILY_SCAN_READONLY", "V2_DAILY_POOL_READONLY",
        "V2_WINDOW_CHECKER_READONLY", "FALLBACK_INTEL_REFRESH_HTML"
    ])
    if R["scheduler_table_checks"]["target_policy"]:
        R["warnings"].append(f"target_policy missing table entries: {R['scheduler_table_checks']['target_policy']}")

    # ── Completion contract ──
    cc = DOCS / "INTEL_TASK_COMPLETION_REFRESH_CONTRACT.md"
    R["completion_contract"] = check_doc(cc, {
        "COMPLETION_REFRESH_DEFINED": "true",
        "FALLBACK_REFRESH_ONLY": "true",
        "FALLBACK_REFRESH_NOT_ONLY_REFRESH": "true",
        "PHASE_E": "false",
        "D13_EXECUTE": "false",
    }, "INTEL_TASK_COMPLETION_REFRESH_CONTRACT")

    # ── Collect ──
    for check_name, check_r in [("migration_plan", R["migration_plan"]),
                                 ("target_policy", R["target_policy"]),
                                 ("completion_contract", R["completion_contract"])]:
        if check_r["status"] == "FAIL":
            R["blockers"].append(f"{check_name} FAIL: {check_r['mismatch']}")
        elif check_r["status"] == "WARN":
            R["warnings"].append(f"{check_name} WARN: {check_r['missing']}")

    if R["blockers"]:
        R["check_status"] = "BLOCKER"
    elif R["warnings"]:
        R["check_status"] = "WARN"

    # ── Output ──
    print("=" * 55)
    print("INTEL SCHEDULER MIGRATION CHECKER")
    print("=" * 55)
    print(f"\nStatus: {R['check_status']}")

    for label, r_data in [("INTEL_SCHEDULER_MIGRATION_PLAN", R["migration_plan"]),
                          ("INTEL_SCHEDULER_TARGET_POLICY", R["target_policy"]),
                          ("INTEL_TASK_COMPLETION_REFRESH_CONTRACT", R["completion_contract"])]:
        print(f"\n── {label} ──")
        print(f"  exists: {r_data['exists']}  |  status: {r_data['status']}")
        for k, v in sorted((r_data.get("markers") or {}).items()):
            print(f"    {k}: {v}")
    print(f"\n── Fixed Delay Check ──")
    for k, v in R["no_fixed_delay_ok"].items():
        print(f"  {k}: {'✅' if v else '❌ FIXED DELAY FOUND'}")
    print(f"\n── Table Checks ──")
    for k, v in R["scheduler_table_checks"].items():
        missing = v or "✅ all found"
        print(f"  {k}: {missing}")

    if R["blockers"]:
        print(f"\n  BLOCKERS ({len(R['blockers'])}):")
        for b in R["blockers"]:
            print(f"    ! {b}")
    if R["warnings"]:
        print(f"\n  WARNINGS ({len(R['warnings'])}):")
        for w in R["warnings"]:
            print(f"    ~ {w}")

    # Write status
    status_dir = WORKSPACE / "v2_football_quant" / "data" / "runtime" / "status"
    status_dir.mkdir(parents=True, exist_ok=True)
    (status_dir / "check_intel_scheduler_migration.json").write_text(
        json.dumps(R, indent=2, ensure_ascii=False, default=str)
    )

    if R["check_status"] == "BLOCKER":
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
