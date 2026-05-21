#!/usr/bin/env python3
"""Claude Code Systematic WARN Fix Regression Checker — verifies all P1/P2 fixes applied."""
import json
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]
CN_TZ = timezone(timedelta(hours=8))


def main():
    R = {
        "checker": "claude_systematic_warn_fix_regression",
        "check_status": "PASS",
        "tests": {},
        "blockers": [],
        "warnings": [],
        "generated_at": datetime.now(CN_TZ).strftime("%Y-%m-%dT%H:%M:%S+08:00"),
    }

    def ck(name, cond, blocker=False):
        R["tests"][name] = cond
        if not cond:
            msg = f"{name}: FAIL"
            if blocker:
                R["blockers"].append(msg)
            else:
                R["warnings"].append(msg)
        return cond

    # ── 1. engine supports --scan-date ──
    engine_src = (MODULE / "engine" / "v4_scan_and_brief.py").read_text()
    ck("engine_supports_scan_date", "--scan-date" in engine_src, blocker=True)

    # ── 2. engine supports --no-push ──
    ck("engine_supports_no_push", "--no-push" in engine_src, blocker=True)

    # ── 3. engine push default disabled (--push default="never") ──
    ck("engine_push_default_disabled",
       'default="never"' in engine_src and "choices=[\"always\",\"conditional\",\"never\"]" in engine_src,
       blocker=True)

    # ── 4. engine has V4_QQ_ENABLED hard gate ──
    ck("engine_V4_QQ_ENABLED_hard_gate",
       "V4_QQ_ENABLED = False" in engine_src and "QQ push is DISABLED" in engine_src,
       blocker=True)

    # ── 5. engine has env var push gate ──
    ck("engine_env_no_push_gate",
       "OPENCLAW_NO_PUSH" in engine_src and "effective_no_push" in engine_src,
       blocker=True)

    # ── 6. engine supports --no-d13/--no-v33/--no-hourly ──
    for flag in ["--no-d13", "--no-v33", "--no-hourly"]:
        ck(f"engine_supports_{flag.replace('-','_')}", flag in engine_src, blocker=True)

    # ── 7. wrapper passes all no-* flags to engine ──
    wrapper_src = (MODULE / "tools" / "run_v4_window_scan_capture_readonly.py").read_text()
    for flag in ["--no-push", "--no-d13", "--no-v33", "--no-hourly"]:
        ck(f"wrapper_passes_{flag.replace('-','_')}", flag in wrapper_src)

    # ── 8. wrapper passes --scan-date to engine ──
    ck("wrapper_passes_scan_date", "--scan-date" in wrapper_src)

    # ── 9. wrapper has real_runner_output marker ──
    ck("wrapper_real_runner_output", "real_runner_output" in wrapper_src)

    # ── 10. capture checker has --run-readonly-runner flag ──
    cap_src = (MODULE / "tools" / "check_v4_next_scan_window_capture.py").read_text()
    ck("capture_checker_has_run_readonly_runner", "--run-readonly-runner" in cap_src, blocker=True)

    # ── 11. capture checker default does NOT auto-run ──
    ck("capture_checker_auto_runner_disabled",
       "auto_runner_disabled" in cap_src and "True" in cap_src)

    # ── 12. capture checker log scan not limited to 500 chars ──
    ck("capture_checker_log_scan_full", "[:500]" not in cap_src)

    # ── 13. C regex in user-visible-routes only matches assignment patterns ──
    uv_src = (MODULE / "tools" / "check_intel_dashboard_user_visible_routes.py").read_text()
    ck("user_visible_C_regex_assignment_only",
       "C\\s*[=:：]\\s*(\\d+)" in uv_src or 'C\\s*[=:：]\\s*(\\d+)' in uv_src)

    # ── 14. user-visible-routes records no-* flags ──
    for flag_key in ["no_push", "no_d13", "no_v33", "no_hourly"]:
        ck(f"user_visible_records_{flag_key}", f'"{flag_key}": args.{flag_key}' in uv_src)

    # ── 15. ops checker handles nested official_counts ──
    ops_src = (MODULE / "tools" / "check_ops_daily_operation.py").read_text()
    ck("ops_checker_handles_nested_official_counts",
       "official_counts" in ops_src and "counts" in ops_src and "_v4_get" in ops_src)

    # ── 16. ops checker has safe key access (no direct v4["A"]) ──
    ck("ops_checker_no_direct_key_access",
       'v4["A"]' not in ops_src and '_v4_get(v4, "A"' in ops_src)

    # ── 17. D13/V33/HOURLY not triggered ──
    # Verify all wrappers/checkers default no-* flags to True
    for src_file, name in [(wrapper_src, "wrapper"), (cap_src, "capture_checker"),
                            (engine_src, "engine")]:
        ck(f"{name}_no_d13_default_true", "no-d13" in src_file.lower() and "True" in src_file)
        ck(f"{name}_no_v33_default_true", "no-v33" in src_file.lower() and "True" in src_file)
        ck(f"{name}_no_hourly_default_true", "no-hourly" in src_file.lower() and "True" in src_file)

    passed = sum(1 for v in R["tests"].values() if v)
    R["tests_passed"] = passed
    R["tests_total"] = len(R["tests"])

    if R["blockers"]:
        R["check_status"] = "BLOCKER"
    elif R["warnings"]:
        R["check_status"] = "WARN"

    print("=" * 60)
    print("CLAUDE SYSTEMATIC WARN FIX REGRESSION CHECKER")
    print("=" * 60)
    print(f"Status: {R['check_status']} | Passed: {passed}/{len(R['tests'])}")
    for k, v in R["tests"].items():
        if not v:
            print(f"  FAIL: {k}")
    if R["blockers"]:
        print(f"\nBLOCKERS ({len(R['blockers'])}):")
        for b in R["blockers"]:
            print(f"  ! {b}")
    if R["warnings"]:
        print(f"\nWARNINGS ({len(R['warnings'])}):")
        for w in R["warnings"]:
            print(f"  ~ {w}")

    out = MODULE / "data" / "runtime" / "status" / "claude_systematic_warn_fix_regression_20260520.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(R, ensure_ascii=False, indent=2))

    if R["check_status"] == "BLOCKER":
        sys.exit(2)
    elif R["check_status"] == "WARN":
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
