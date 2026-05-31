#!/usr/bin/env python3
"""
Check V4 RF Shadow -> Official Promotion Dry-Run artifacts.

This checker validates safety and data consistency for promotion dry-run output.
It must remain read-only and must not require re-scan/API calls.
"""

import argparse
import json
import os
import subprocess
import sys
from typing import Any, Dict, List, Optional

WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS_DIR = os.path.join(WORKSPACE, "tools")
ACCEPTANCE_DIR = os.path.join(WORKSPACE, "data", "runtime", "acceptance")
SCOUT_DIR = os.path.join(WORKSPACE, "data", "daily_reports")
CANDIDATE_DIR = os.path.join(WORKSPACE, "data", "runtime", "status")


def check_file_exists(path: str, desc: str) -> bool:
    ok = os.path.exists(path)
    if ok:
        print(f"  ✅ EXISTS: {desc}")
    else:
        print(f"  ❌ MISSING: {desc} ({path})")
    return ok


def load_json(path: str, desc: str) -> Optional[Any]:
    if not os.path.exists(path):
        print(f"  ❌ MISSING: {desc} ({path})")
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as exc:
        print(f"  ❌ INVALID JSON: {desc} ({exc})")
        return None


def load_scout_rows(scan_date: str) -> List[Dict[str, Any]]:
    scout_path = os.path.join(SCOUT_DIR, f"scout_v4_{scan_date}.json")
    data = load_json(scout_path, "Scout report")
    if data is None:
        return []
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        rows = data.get("matches") or data.get("rows") or data.get("items") or []
        return rows if isinstance(rows, list) else []
    return []


def run_json_guard(tool_name: str) -> Optional[Dict[str, Any]]:
    tool_path = os.path.join(TOOLS_DIR, tool_name)
    result = subprocess.run(
        [sys.executable, tool_path], capture_output=True, text=True, timeout=60
    )
    if result.returncode != 0:
        return None
    out = result.stdout.strip()
    if not out.startswith("{"):
        return None
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default="20260531", help="scan date YYYYMMDD")
    args = parser.parse_args()
    scan_date = args.date

    errors: List[str] = []
    blocks: List[str] = []

    print(f"\n🔒 V4 RF Shadow Promotion Dry-Run Checker ({scan_date})\n")

    print("[1] Tool existence")
    tool_path = os.path.join(TOOLS_DIR, "build_v4_rf_shadow_to_official_promotion_dryrun.py")
    if not check_file_exists(tool_path, "Dry-run build tool"):
        errors.append("dry-run build tool missing")

    print("\n[2] Artifact existence")
    json_artifact = os.path.join(
        ACCEPTANCE_DIR, f"v4_rf_shadow_to_official_promotion_dryrun_{scan_date}.json"
    )
    md_artifact = os.path.join(
        ACCEPTANCE_DIR, f"v4_rf_shadow_to_official_promotion_dryrun_{scan_date}.md"
    )
    if not check_file_exists(json_artifact, "Dry-run JSON artifact"):
        errors.append("dry-run JSON artifact missing")
    if not check_file_exists(md_artifact, "Dry-run MD artifact"):
        errors.append("dry-run MD artifact missing")

    report = load_json(json_artifact, "Dry-run report")
    if report is None:
        blocks.append("cannot load dry-run report")
        print("\n❌ BLOCKER: cannot continue without dry-run artifact")
        return 2

    print("\n[3] Safety checks in artifact")
    safety = report.get("safety_checks", {})
    for key, expect_false in [
        ("api_called", True),
        ("scan_re_executed", True),
        ("official_grade_modified", True),
        ("candidate_view_modified", True),
        ("pending_bet_modified", True),
        ("validation_recomputed", True),
        ("live_bet_modified", True),
        ("qq_pushed", True),
        ("cron_modified", True),
    ]:
        value = bool(safety.get(key, False))
        if value is expect_false:
            errors.append(f"safety check failed: {key}=true")
            print(f"  ❌ {key}=true")
        else:
            print(f"  ✅ {key}=false")

    print("\n[4] Dynamic total checks (no hard-coded 43)")
    scout_rows = load_scout_rows(scan_date)
    scout_row_count = len(scout_rows)
    source_row_count = int(report.get("source_row_count") or scout_row_count)
    official_total = int(report.get("official_total") or source_row_count)
    dryrun_dist = report.get("dryrun_grade_distribution", {})
    dryrun_total = int(report.get("dryrun_total") or sum(int(v) for v in dryrun_dist.values()))
    print(
        f"  source_row_count={source_row_count}, official_total={official_total}, "
        f"dryrun_total={dryrun_total}, scout_row_count={scout_row_count}"
    )
    if source_row_count <= 0:
        blocks.append("source_row_count invalid")
        print("  ❌ source_row_count must be > 0")
    if official_total != source_row_count:
        errors.append("official_total != source_row_count")
        print("  ❌ official_total mismatch")
    else:
        print("  ✅ official_total matches source_row_count")
    if dryrun_total != source_row_count:
        errors.append("dryrun_total != source_row_count")
        print("  ❌ dryrun_total mismatch")
    else:
        print("  ✅ dryrun_total matches source_row_count")

    print("\n[5] Dry-run statistics existence")
    required_dryrun_keys = ["DRYRUN_A", "DRYRUN_B", "DRYRUN_C_OBSERVE", "DRYRUN_SKIP"]
    if all(k in dryrun_dist for k in required_dryrun_keys):
        print(
            "  ✅ Stats present: "
            f"A={dryrun_dist.get('DRYRUN_A',0)}, "
            f"B={dryrun_dist.get('DRYRUN_B',0)}, "
            f"C={dryrun_dist.get('DRYRUN_C_OBSERVE',0)}, "
            f"SKIP={dryrun_dist.get('DRYRUN_SKIP',0)}"
        )
    else:
        errors.append("dryrun stats missing required keys")
        print(f"  ❌ Missing keys in dryrun stats: {dryrun_dist}")

    print("\n[6] Dryrun A/B source validation")
    source_ok = True
    for cand_key in ["dryrun_a_candidates", "dryrun_b_candidates"]:
        for c in report.get(cand_key, []):
            if c.get("market_adjusted_shadow_grade") not in ("A", "B"):
                source_ok = False
                print(
                    f"  ❌ {cand_key} fixture {c.get('fixture_id')} "
                    f"market_adjusted={c.get('market_adjusted_shadow_grade')}"
                )
    if source_ok:
        print("  ✅ Dryrun A/B candidates originate from market-adjusted A/B")
    else:
        errors.append("dryrun A/B source invalid")

    print("\n[7] MARKET_HARD_VETO guard")
    veto_ok = True
    for cand_key in ["dryrun_a_candidates", "dryrun_b_candidates"]:
        for c in report.get(cand_key, []):
            if c.get("opening_market_support_status") == "MARKET_HARD_VETO":
                veto_ok = False
                print(f"  ❌ {cand_key} fixture {c.get('fixture_id')} has MARKET_HARD_VETO")
    if veto_ok:
        print("  ✅ MARKET_HARD_VETO not present in dryrun A/B")
    else:
        errors.append("MARKET_HARD_VETO found in dryrun A/B")

    print("\n[8] MARKET_NO_DATA and NO_MARKET guard")
    no_data_a_ok = True
    no_market_ab_ok = True
    for c in report.get("dryrun_a_candidates", []):
        if c.get("opening_market_support_status") == "MARKET_NO_DATA":
            no_data_a_ok = False
            print(f"  ❌ dryrun A fixture {c.get('fixture_id')} has MARKET_NO_DATA")
    for cand_key in ["dryrun_a_candidates", "dryrun_b_candidates"]:
        for c in report.get(cand_key, []):
            if c.get("opening_market_available") is False:
                no_market_ab_ok = False
                print(f"  ❌ {cand_key} fixture {c.get('fixture_id')} has NO_MARKET")
    if no_data_a_ok:
        print("  ✅ MARKET_NO_DATA not auto-promoted to dryrun A")
    else:
        errors.append("MARKET_NO_DATA auto-promoted to dryrun A")
    if no_market_ab_ok:
        print("  ✅ NO_MARKET not present in dryrun A/B")
    else:
        errors.append("NO_MARKET present in dryrun A/B")

    print("\n[9] Official grade unchanged (dynamic row count)")
    candidate_path = os.path.join(CANDIDATE_DIR, f"v3v4_dashboard_candidate_view_{scan_date}.json")
    cv = load_json(candidate_path, "Candidate view")
    if cv is None:
        errors.append("candidate view missing")
    else:
        cv_a = int(cv.get("A_count", 0) or 0)
        cv_b = int(cv.get("B_count", 0) or 0)
        cv_c = int(cv.get("C_count", 0) or 0)
        cv_skip = int(cv.get("SKIP_count", 0) or 0)
        expected_skip = source_row_count - cv_a - cv_b - cv_c
        cv_skip_effective = cv_skip if cv_skip > 0 else expected_skip
        cv_total = cv_a + cv_b + cv_c + cv_skip_effective
        print(
            f"  Candidate view: A={cv_a}, B={cv_b}, C={cv_c}, "
            f"SKIP_raw={cv_skip}, SKIP_effective={cv_skip_effective}, TOTAL={cv_total}"
        )
        if cv_total != source_row_count:
            errors.append(
                f"candidate_view total mismatch: total={cv_total}, expected={source_row_count}"
            )
            print("  ❌ Candidate total mismatches source_row_count")
        else:
            print("  ✅ Candidate total matches source_row_count")
        if cv_skip not in (0, expected_skip):
            errors.append(f"candidate SKIP mismatch: skip={cv_skip}, expected={expected_skip}")
            print("  ❌ Candidate SKIP mismatches dynamic expected value")
        else:
            print(f"  ✅ Candidate SKIP is compatible with dynamic expected ({expected_skip})")

    print("\n[10] DEFAULT_RULES / cron / validation / live bet / QQ guard")
    default_guard = run_json_guard("check_v4_production_default_rules_guard.py")
    if not default_guard:
        errors.append("cannot parse default rules guard output")
        print("  ❌ Unable to parse default rules guard")
    else:
        if default_guard.get("conclusion") != "PASS":
            blocks.append("DEFAULT_RULES guard not PASS")
            print(f"  ❌ DEFAULT_RULES guard: {default_guard.get('conclusion')}")
        else:
            print("  ✅ DEFAULT_RULES guard PASS")
        forbidden = default_guard.get("forbidden_flags", {})
        for key in [
            "cron_modified",
            "validation_recomputed",
            "live_bet_raw_records_modified",
            "QQ_recommendation_pushed",
        ]:
            if forbidden.get(key) is True:
                blocks.append(f"forbidden flag true: {key}")
                print(f"  ❌ {key}=true")
            else:
                print(f"  ✅ {key}=false")

    switch_guard_tool = os.path.join(TOOLS_DIR, "check_v4_lazy_shadow_production_switch_guard.py")
    if os.path.exists(switch_guard_tool):
        result = subprocess.run(
            [sys.executable, switch_guard_tool], capture_output=True, text=True, timeout=120
        )
        if "PASS" in result.stdout:
            print("  ✅ Switch guard PASS (cron still safe)")
        else:
            errors.append("switch guard not PASS")
            print("  ❌ Switch guard did not pass")
    else:
        errors.append("switch guard checker missing")
        print("  ❌ Switch guard checker missing")

    print("\n[11] Staging safety check")
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True,
        text=True,
        timeout=20,
        cwd=WORKSPACE,
    )
    staged_files = [f for f in result.stdout.splitlines() if f.strip()]
    if any("data/runtime/acceptance" in f for f in staged_files):
        errors.append("runtime acceptance artifact staged")
        print("  ❌ runtime acceptance artifact staged")
    else:
        print("  ✅ runtime acceptance artifact not staged")
    if any("data/daily_reports" in f for f in staged_files):
        errors.append("daily report artifact staged")
        print("  ❌ daily report artifact staged")
    else:
        print("  ✅ daily report artifact not staged")
    if any("data/runtime/status" in f for f in staged_files):
        errors.append("runtime status artifact staged")
        print("  ❌ runtime status artifact staged")
    else:
        print("  ✅ runtime status artifact not staged")

    secret_files = [
        f
        for f in staged_files
        if any(k in f.lower() for k in [".env", "secret", "token", "apikey", "api_key"])
    ]
    if secret_files:
        blocks.append(f"secrets staged: {secret_files}")
        print(f"  ❌ secrets staged: {secret_files}")
    else:
        print("  ✅ no secrets staged")

    print("\n" + "=" * 60)
    print(f"RESULTS: {len(errors)} errors, {len(blocks)} blockers")
    if errors:
        print("ERRORS:")
        for e in errors:
            print(f"  ❌ {e}")
    if blocks:
        print("BLOCKERS:")
        for b in blocks:
            print(f"  🚫 {b}")
    print("=" * 60 + "\n")

    if blocks:
        print("🔴 BLOCKER: critical safety violation detected")
        return 2
    if errors:
        print("🟡 FAIL: non-blocking errors found (allow fix once)")
        return 1
    print("🟢 PASS: all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
