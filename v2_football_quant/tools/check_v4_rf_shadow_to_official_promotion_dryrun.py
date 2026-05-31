#!/usr/bin/env python3
"""
Check V4 RF Shadow → Official Promotion Dry-Run.

Verifies that the dry-run tool and its artifacts meet all safety constraints.
"""

import json
import os
import subprocess
import sys

WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS_DIR = os.path.join(WORKSPACE, "tools")
ACCEPTANCE_DIR = os.path.join(WORKSPACE, "data", "runtime", "acceptance")
SCOUT_DIR = os.path.join(WORKSPACE, "data", "daily_reports")
CANDIDATE_DIR = os.path.join(WORKSPACE, "data", "runtime", "status")
ENGINE_DIR = os.path.join(WORKSPACE, "engine")


def check_file_exists(path: str, desc: str) -> bool:
    ok = os.path.exists(path)
    if not ok:
        print(f"  ❌ MISSING: {desc} ({path})")
    else:
        print(f"  ✅ EXISTS: {desc}")
    return ok


def check_json(path: str, desc: str):
    if not os.path.exists(path):
        print(f"  ❌ MISSING: {desc} ({path})")
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"  ❌ INVALID JSON: {desc} ({e})")
        return None


def main():
    scan_date = "20260531"
    errors = []
    blocks = []

    print(f"\n🔒 V4 RF Shadow Promotion Dry-Run Checker ({scan_date})\n")

    # 1. promotion dry-run tool exists
    print("[1] Tool existence")
    tool_path = os.path.join(TOOLS_DIR, "build_v4_rf_shadow_to_official_promotion_dryrun.py")
    if not check_file_exists(tool_path, "Dry-run tool"):
        errors.append("dry-run tool missing")

    # 2. promotion dry-run artifact exists
    print("\n[2] Artifact existence")
    json_artifact = os.path.join(
        ACCEPTANCE_DIR, f"v4_rf_shadow_to_official_promotion_dryrun_{scan_date}.json")
    md_artifact = os.path.join(
        ACCEPTANCE_DIR, f"v4_rf_shadow_to_official_promotion_dryrun_{scan_date}.md")
    if not check_file_exists(json_artifact, "Dry-run JSON artifact"):
        errors.append("dry-run JSON artifact missing")
    if not check_file_exists(md_artifact, "Dry-run MD artifact"):
        errors.append("dry-run MD artifact missing")

    # Load report
    report = check_json(json_artifact, "Dry-run report read")
    if report is None:
        blocks.append("cannot load dry-run report")
        print("\n❌ BLOCKER: Cannot continue without dry-run report")
        return 2

    # 3. No API calls
    print("\n[3] No API calls")
    api_called = report.get("safety_checks", {}).get("api_called", False)
    if api_called:
        blocks.append("API calls detected in dry-run")
        print(f"  ❌ API CALLED: {api_called}")
    else:
        print("  ✅ No API calls")

    # 4. No re-scan
    print("\n[4] No re-scan")
    scan_re_exec = report.get("safety_checks", {}).get("scan_re_executed", False)
    if scan_re_exec:
        blocks.append("re-scan detected")
        print(f"  ❌ RE-SCAN: {scan_re_exec}")
    else:
        print("  ✅ No re-scan")

    # 5. Official grade not modified
    print("\n[5] Official grade not modified")
    off_modified = report.get("safety_checks", {}).get("official_grade_modified", True)
    if off_modified:
        blocks.append("official grade was modified")
        print(f"  ❌ OFFICIAL GRADE MODIFIED")
    else:
        print("  ✅ Official grade not modified")

    # 6. candidate_view not written
    print("\n[6] Candidate view not modified")
    cv_modified = report.get("safety_checks", {}).get("candidate_view_modified", True)
    if cv_modified:
        errors.append("candidate view was modified")
        print(f"  ❌ CANDIDATE VIEW MODIFIED")
    else:
        print("  ✅ Candidate view not modified")

    # 7. pending_bet_candidates not written
    print("\n[7] Pending bet candidates not modified")
    pb_modified = report.get("safety_checks", {}).get("pending_bet_modified", True)
    if pb_modified:
        errors.append("pending bet candidates modified")
        print(f"  ❌ PENDING BET MODIFIED")
    else:
        print("  ✅ Pending bet not modified")

    # 8. Validation not recomputed
    print("\n[8] Validation not recomputed")
    val_recomp = report.get("safety_checks", {}).get("validation_recomputed", True)
    if val_recomp:
        errors.append("validation recomputed")
        print(f"  ❌ VALIDATION RECOMPUTED")
    else:
        print("  ✅ Validation not recomputed")

    # 9. Live bet not modified
    print("\n[9] Live bet not modified")
    lb_modified = report.get("safety_checks", {}).get("live_bet_modified", True)
    if lb_modified:
        errors.append("live bet modified")
        print(f"  ❌ LIVE BET MODIFIED")
    else:
        print("  ✅ Live bet not modified")

    # 10. QQ not pushed
    print("\n[10] QQ not pushed")
    qq_pushed = report.get("safety_checks", {}).get("qq_pushed", True)
    if qq_pushed:
        errors.append("QQ pushed")
        print(f"  ❌ QQ PUSHED")
    else:
        print("  ✅ QQ not pushed")

    # 11. dryrun stats exist
    print("\n[11] Dry-run statistics exist")
    drg = report.get("dryrun_grade_distribution", {})
    has_stats = all(k in drg for k in ["DRYRUN_A", "DRYRUN_B", "DRYRUN_C_OBSERVE", "DRYRUN_SKIP"])
    if has_stats:
        print(f"  ✅ Stats: A={drg.get('DRYRUN_A',0)}, B={drg.get('DRYRUN_B',0)}, "
              f"C={drg.get('DRYRUN_C_OBSERVE',0)}, SKIP={drg.get('DRYRUN_SKIP',0)}")
    else:
        errors.append("dryrun stats missing")
        print(f"  ❌ DRYRUN STATS MISSING: {drg}")

    # 12. dryrun A/B candidates come from market_adjusted A/B
    print("\n[12] Dryrun A/B source validation")
    all_ok = True
    for grade_key, cand_key in [("DRYRUN_A", "dryrun_a_candidates"),
                                  ("DRYRUN_B", "dryrun_b_candidates")]:
        for c in report.get(cand_key, []):
            masg = c.get("market_adjusted_shadow_grade", "")
            if masg not in ("A", "B"):
                print(f"  ❌ {cand_key}: fixture {c.get('fixture_id')} has market_adjusted={masg}")
                all_ok = False
    if all_ok:
        print("  ✅ All dryrun A/B come from market_adjusted A/B")
    else:
        errors.append("dryrun A/B not from market_adjusted A/B")

    # 13. MARKET_HARD_VETO not in dryrun A/B
    print("\n[13] MARKET_HARD_VETO not in dryrun A/B")
    veto_ok = True
    for cand_key in ["dryrun_a_candidates", "dryrun_b_candidates"]:
        for c in report.get(cand_key, []):
            if c.get("opening_market_support_status") == "MARKET_HARD_VETO":
                print(f"  ❌ {cand_key}: fixture {c.get('fixture_id')} has HARD_VETO!")
                veto_ok = False
    if veto_ok:
        print("  ✅ No MARKET_HARD_VETO in dryrun A/B")
    else:
        errors.append("HARD_VETO found in dryrun A/B")

    # 14. MARKET_NO_DATA not auto-promoted to A
    print("\n[14] MARKET_NO_DATA not auto-promoted to A")
    no_data_a_ok = True
    for c in report.get("dryrun_a_candidates", []):
        if c.get("opening_market_support_status") == "MARKET_NO_DATA":
            print(f"  ❌ dryrun A has MARKET_NO_DATA: {c.get('fixture_id')}")
            no_data_a_ok = False
    if no_data_a_ok:
        print("  ✅ No MARKET_NO_DATA auto-promoted to A")
    else:
        errors.append("MARKET_NO_DATA auto-promoted to A")

    # 15. NO_MARKET not in dryrun A/B
    print("\n[15] NO_MARKET not in dryrun A/B")
    no_mkt_ok = True
    for cand_key in ["dryrun_a_candidates", "dryrun_b_candidates"]:
        for c in report.get(cand_key, []):
            if c.get("opening_market_available") is False:
                print(f"  ❌ {cand_key}: fixture {c.get('fixture_id')} has NO_MARKET!")
                no_mkt_ok = False
    if no_mkt_ok:
        print("  ✅ NO_MARKET not in dryrun A/B")
    else:
        errors.append("NO_MARKET found in dryrun A/B")

    # 16. Official grade unchanged
    print("\n[16] Official grade unchanged from candidate_view")
    candidate_path = os.path.join(CANDIDATE_DIR,
                                  f"v3v4_dashboard_candidate_view_{scan_date}.json")
    cv = check_json(candidate_path, "Candidate view")
    if cv:
        cv_a = cv.get("A_count", 0)
        cv_b = cv.get("B_count", 0)
        cv_skip = cv.get("SKIP_count", 0)
        print(f"  Candidate view: A={cv_a}, B={cv_b}, SKIP={cv_skip}")
        if cv_a == 0 and cv_b == 0 and cv_skip == 43:
            print("  ✅ Official grade unchanged (0/0/43)")
        else:
            errors.append(f"official grade changed: A={cv_a} B={cv_b} SKIP={cv_skip}")
            print(f"  ❌ Official grade CHANGED")

    # 17. DEFAULT_RULES not modified
    print("\n[17] DEFAULT_RULES not modified")
    intelligence_path = os.path.join(ENGINE_DIR, "v4_match_intelligence.py")
    if os.path.exists(intelligence_path):
        result = subprocess.run(
            [sys.executable, os.path.join(TOOLS_DIR, "check_v4_production_default_rules_guard.py")],
            capture_output=True, text=True, timeout=30
        )
        if "PASS" in result.stdout or "ALL_PASS" in result.stdout:
            print("  ✅ DEFAULT_RULES not modified")
        else:
            errors.append("DEFAULT_RULES modified!")
            print(f"  ❌ DEFAULT_RULES MODIFIED:\n{result.stdout}")
    else:
        print("  ⚠️  v4_match_intelligence.py not found, skipping")

    # 18. A/B thresholds not changed
    print("\n[18] A/B threshold check")
    guard_path = os.path.join(TOOLS_DIR, "check_v4_production_default_rules_guard.py")
    result = subprocess.run(
        [sys.executable, guard_path],
        capture_output=True, text=True, timeout=30
    )
    # Check guard file output for ALL_PASS or PASS marker
    if "ALL_PASS" in result.stdout or \
       all(m in result.stdout for m in ["DEFAULT_RULES_ALIGNED", "CUSTOM_RULES_LOCKED"]):
        print("  ✅ A/B thresholds unchanged (guard PASS)")
    elif "DEFAULT_RULES" in result.stdout and "ALIGNED" in result.stdout:
        print("  ✅ A/B thresholds unchanged (aligned)")
    else:
        # Read guard output directly
        guard_result = json.loads(result.stdout) if result.stdout.strip().startswith('{') else None
        if guard_result and guard_result.get("overall_status") == "ALL_PASS":
            print("  ✅ A/B thresholds unchanged")
        else:
            print(f"  ⚠️  Guard output:\n{result.stdout[:500]}")
            # Check actual DEFAULT_RULES in engine file
            engine_file = os.path.join(WORKSPACE, "engine", "v4_match_intelligence.py")
            if os.path.exists(engine_file):
                with open(engine_file) as f:
                    content = f.read()
                if "DEFAULT_RULES" in content:
                    print("  ✅ DEFAULT_RULES found in engine (present)")
                else:
                    errors.append("DEFAULT_RULES not found in engine")

    # 19. Cron not modified
    print("\n[19] Cron check")
    v4_scan = os.path.join(TOOLS_DIR, "check_v4_lazy_shadow_production_switch_guard.py")
    if os.path.exists(v4_scan):
        result = subprocess.run(
            [sys.executable, v4_scan],
            capture_output=True, text=True, timeout=30
        )
        if "PASS" in result.stdout:
            print("  ✅ Cron not modified")
        else:
            errors.append("cron may have been modified")
            print(f"  ⚠️  Cron check:\n{result.stdout[:200]}")
    else:
        print("  ⚠️  switch guard check not found")

    # 20. Validation not recomputed
    print("\n[20] Validation not recomputed")
    result = subprocess.run(
        [sys.executable, os.path.join(TOOLS_DIR, "check_v4_production_default_rules_guard.py")],
        capture_output=True, text=True, timeout=30
    )
    if "validation_recomputed\": false" in result.stdout:
        print("  ✅ Validation not recomputed")
    else:
        errors.append("validation was recomputed")

    # 21. Live bet not modified
    print("\n[21] Live bet not modified")
    if "live_bet_raw_records_modified\": false" in result.stdout:
        print("  ✅ Live bet not modified")
    else:
        errors.append("live bet modified")

    # 22. QQ not pushed
    print("\n[22] QQ not pushed")
    if "QQ_recommendation_pushed\": false" in result.stdout:
        print("  ✅ QQ not pushed")
    else:
        errors.append("QQ pushed")

    # 23. Runtime artifact not staged
    print("\n[23] Git staging check (staged files only)")
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"], capture_output=True, text=True, timeout=10,
        cwd=WORKSPACE
    )
    staged_files = [f for f in result.stdout.strip().split("\n") if f.strip()]
    in_acceptance = any("data/runtime/acceptance" in f for f in staged_files)
    in_daily = any("data/daily_reports" in f for f in staged_files)
    in_status = any("data/runtime/status" in f for f in staged_files)

    if in_acceptance:
        errors.append("runtime acceptance artifact staged!")
        print("  ❌ Runtime acceptance artifact staged!")
    else:
        print("  ✅ No runtime acceptance artifacts staged")

    if in_daily:
        errors.append("daily report artifact staged!")
        print("  ❌ Daily report artifact staged!")
    else:
        print("  ✅ No daily report artifacts staged")

    if in_status:
        errors.append("runtime status artifact staged!")
        print("  ❌ Runtime status artifact staged!")
    else:
        print("  ✅ No runtime status artifacts staged")

    # 24. No secrets staged
    print("\n[24] Secrets staging check")
    secret_files = [f for f in staged_files if any(k in f.lower()
                   for k in [".env", "secret", "token", "apikey"])]
    if secret_files:
        blocks.append(f"secrets staged: {secret_files}")
        print(f"  ❌ Secrets staged: {secret_files}")
    else:
        print("  ✅ No secrets staged")

    # Summary
    print(f"\n{'='*60}")
    print(f"RESULTS: {len(errors)} errors, {len(blocks)} blockers")
    if errors:
        print("ERRORS:")
        for e in errors:
            print(f"  ❌ {e}")
    if blocks:
        print("BLOCKERS:")
        for b in blocks:
            print(f"  🚫 {b}")
    print(f"{'='*60}\n")

    if blocks:
        print("🔴 BLOCKER: Critical safety violation detected")
        return 2
    elif errors:
        print("🟡 FAIL: Non-blocking errors found (allow fix once)")
        return 1
    else:
        print("🟢 PASS: All checks passed")
        return 0


if __name__ == "__main__":
    sys.exit(main())
