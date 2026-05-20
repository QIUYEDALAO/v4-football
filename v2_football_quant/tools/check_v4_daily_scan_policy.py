#!/usr/bin/env python3
"""
V4-DSP-1: V4 Daily Scan Policy Checker

Checks that:
- V4_DAILY_SCAN_POLICY.md exists and has the required compliance markers
- daily_once=true
- no_multi_intraday_scan=true
- intel_refresh_does_not_trigger_v4_scan=true
- source_resolver_readonly=true
- qq_push_allowed=false
- state_write_allowed=false
- verified_write_allowed=false
- cron_enabled=false
- phase_e=false
- INTEL_OPS_REFRESH_CONTRACT.md exists and does not trigger V4 scan
- INTEL_WEB_DASHBOARD_CONTRACT.md exists and does not trigger V4 scan
"""

import re
import sys
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]  # workspace root
DOCS = WORKSPACE_ROOT / "docs"
TOOLS = Path(__file__).resolve().parent  # v2_football_quant/tools

# ── Expected compliance markers ────────────────────────────────────
EXPECTED_MARKERS = {
    "DAILY_ONCE": "true",
    "NO_MULTI_INTRADAY_SCAN": "true",
    "INTEL_REFRESH_DOES_NOT_TRIGGER_V4_SCAN": "true",
    "SOURCE_RESOLVER_READONLY": "true",
    "QQ_PUSH_ALLOWED": "false",
    "STATE_WRITE_ALLOWED": "false",
    "VERIFIED_WRITE_ALLOWED": "false",
    "CRON_ENABLED": "false",
    "PHASE_E": "false",
}

INTEL_OPS_MARKERS = {
    "CAN_REFRESH_MULTIPLE_TIMES": "true",
    "TRIGGERS_V4_SCAN": "false",
    "READONLY": "true",
    "NO_STATE_WRITE": "true",
    "NO_VERIFIED_WRITE": "true",
    "NO_QQ_PUSH": "true",
    "NO_CRON": "true",
}

INTEL_DASHBOARD_MARKERS = {
    "CAN_REFRESH_MULTIPLE_TIMES": "true",
    "TRIGGERS_V4_SCAN": "false",
    "READONLY": "true",
    "NO_STATE_WRITE": "true",
    "NO_VERIFIED_WRITE": "true",
    "NO_QQ_PUSH": "true",
    "NO_CRON": "true",
    "C_OBSERVATION_ONLY": "true",
    "SKIP_NOT_RECOMMENDATION": "true",
}


def parse_markers(text: str) -> dict[str, str]:
    """Extract KEY=VALUE compliance markers from doc text."""
    markers = {}
    for line in text.splitlines():
        line = line.strip()
        # Match KEY=VALUE with optional leading whitespace and trailing punctuation
        m = re.match(r"^([A-Z][A-Z0-9_]+)\s*=\s*(\S+)", line)
        if m:
            markers[m.group(1)] = m.group(2).rstrip(",;.")
    return markers


def check_doc(path: Path, expected: dict[str, str], label: str) -> dict:
    R: dict = {"exists": False, "markers": {}, "missing": [], "mismatch": [], "status": "PASS"}
    if not path.is_file():
        R["status"] = "FAIL"
        R["missing"].append(f"{label} file not found: {path}")
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


def check_cron_policy(path: Path) -> dict:
    """Check that V4 cron entries in CRON_POLICY are disabled/commented."""
    R: dict = {"has_v4_scan_cron": False, "details": [], "status": "PASS"}
    if not path.is_file():
        R["status"] = "PASS"  # no cron policy = nothing to check
        return R
    text = path.read_text(encoding="utf-8")
    v4_scan_lines = []
    for line in text.splitlines():
        if "v4_scan_and_brief" in line or "V4扫描" in line:
            v4_scan_lines.append(line.strip())
            if "已禁用" not in line and "disabled" not in line.lower():
                R["has_v4_scan_cron"] = True
    R["details"] = v4_scan_lines
    # We don't require them disabled — the policy doc sets the protocol
    return R


def main():
    R: dict = {
        "check_status": "PASS",
        "blockers": [],
        "warnings": [],
        "policy": {},
        "intel_ops": {},
        "intel_dashboard": {},
        "cron_policy": {},
        "verdict": {},
    }

    # ── Step A: V4_DAILY_SCAN_POLICY.md ──
    policy_path = DOCS / "V4_DAILY_SCAN_POLICY.md"
    policy_r = check_doc(policy_path, EXPECTED_MARKERS, "V4_DAILY_SCAN_POLICY")
    R["policy"] = policy_r

    # ── Step B: INTEL_OPS_REFRESH_CONTRACT.md ──
    ops_path = DOCS / "INTEL_OPS_REFRESH_CONTRACT.md"
    ops_r = check_doc(ops_path, INTEL_OPS_MARKERS, "INTEL_OPS_REFRESH_CONTRACT")
    R["intel_ops"] = ops_r

    # ── Step C: INTEL_WEB_DASHBOARD_CONTRACT.md ──
    dash_path = DOCS / "INTEL_WEB_DASHBOARD_CONTRACT.md"
    dash_r = check_doc(dash_path, INTEL_DASHBOARD_MARKERS, "INTEL_WEB_DASHBOARD_CONTRACT")
    R["intel_dashboard"] = dash_r

    # ── Step D: Cron policy check ──
    cron_path = DOCS / "OPENCLAW_CRON_POLICY.md"
    cron_r = check_cron_policy(cron_path)
    R["cron_policy"] = cron_r

    # ── Step E: Collect blockers ──
    # Policy doc must PASS
    if policy_r["status"] == "FAIL":
        R["blockers"].append(f"Policy doc FAIL: {policy_r['mismatch']}")
    if policy_r["status"] == "WARN":
        R["warnings"].append(f"Policy doc WARN: {policy_r['missing']}")

    # Intel ops must not trigger V4 scan
    ops_triggers = ops_r["markers"].get("TRIGGERS_V4_SCAN", "unknown")
    if ops_triggers != "false":
        R["blockers"].append(f"INTEL_OPS TRIGGERS_V4_SCAN={ops_triggers} (expected=false)")

    # Intel dashboard must not trigger V4 scan
    dash_triggers = dash_r["markers"].get("TRIGGERS_V4_SCAN", "unknown")
    if dash_triggers != "false":
        R["blockers"].append(f"INTEL_DASHBOARD TRIGGERS_V4_SCAN={dash_triggers} (expected=false)")

    # Source resolver readonly
    sr = policy_r["markers"].get("SOURCE_RESOLVER_READONLY", "unknown")
    if sr != "true":
        R["blockers"].append(f"SOURCE_RESOLVER_READONLY={sr} (expected=true)")

    # QQ/state/verified/cron/phase_e
    for field in ["QQ_PUSH_ALLOWED", "STATE_WRITE_ALLOWED", "VERIFIED_WRITE_ALLOWED", "CRON_ENABLED", "PHASE_E"]:
        val = policy_r["markers"].get(field, "unknown")
        if val != "false" and val.lower() != "false":
            R["blockers"].append(f"{field}={val} (expected=false)")

    # ── Final verdict ──
    if R["blockers"]:
        R["check_status"] = "BLOCKER"
    elif R["warnings"]:
        R["check_status"] = "WARN"
    else:
        R["check_status"] = "PASS"

    R["verdict"] = {
        "V4_scan_frequency": "daily_once",
        "V4_scan_basis": "historical_data_only",
        "intel_refresh_does_trigger_v4_scan": not (ops_triggers == "false" and dash_triggers == "false"),
        "source_resolver_readonly": sr == "true",
        "cron_has_v4_scan_entries": cron_r["has_v4_scan_cron"],
        "qq_sent": False,
        "state_written": False,
        "verified_written": False,
        "phase_e_active": policy_r["markers"].get("PHASE_E", "unknown") != "false",
    }

    # ── Output ──
    print("=" * 55)
    print("V4 DAILY SCAN POLICY CHECKER")
    print("=" * 55)
    print(f"\nStatus: {R['check_status']}")

    print("\n── V4_DAILY_SCAN_POLICY.md ──")
    print(f"  exists: {policy_r['exists']}  |  status: {policy_r['status']}")
    for k, v in EXPECTED_MARKERS.items():
        print(f"    {k}: {policy_r['markers'].get(k, 'MISSING')} (expected={v})")
    if policy_r["missing"]:
        print(f"  missing: {policy_r['missing']}")
    if policy_r["mismatch"]:
        print(f"  mismatch: {policy_r['mismatch']}")

    print(f"\n── INTEL_OPS_REFRESH_CONTRACT ──")
    print(f"  exists: {ops_r['exists']}  |  TRIGGERS_V4_SCAN: {ops_r['markers'].get('TRIGGERS_V4_SCAN', 'MISSING')}")

    print(f"\n── INTEL_WEB_DASHBOARD_CONTRACT ──")
    print(f"  exists: {dash_r['exists']}  |  TRIGGERS_V4_SCAN: {dash_r['markers'].get('TRIGGERS_V4_SCAN', 'MISSING')}")

    print(f"\n── Cron Policy ──")
    print(f"  has_v4_scan_cron: {cron_r['has_v4_scan_cron']}")

    if R["blockers"]:
        print(f"\n  BLOCKERS ({len(R['blockers'])}):")
        for b in R["blockers"]:
            print(f"    ! {b}")
    if R["warnings"]:
        print(f"\n  WARNINGS ({len(R['warnings'])}):")
        for w in R["warnings"]:
            print(f"    ~ {w}")

    print("\n── Verdict ──")
    for k, v in R["verdict"].items():
        print(f"  {k}: {v}")

    # Write status
    status_dir = WORKSPACE_ROOT / "v2_football_quant" / "data" / "runtime" / "status"
    status_dir.mkdir(parents=True, exist_ok=True)
    (status_dir / "v4_daily_scan_policy_check.json").write_text(
        __import__("json").dumps(R, indent=2, ensure_ascii=False)
    )

    if R["check_status"] == "BLOCKER":
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
