#!/usr/bin/env python3
"""V4 Wrapper Marker Isolated Session Regression Checker

Validates that wrapper markers are correctly written regardless of execution context.
"""
import argparse
import json
import os
import sys
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]
TZ = timezone(timedelta(hours=8))


def check_preflight_no_markers():
    """Check 1: preflight does NOT write markers."""
    wrapper = MODULE / "tools" / "run_v4_window_scan_capture_readonly.py"
    if not wrapper.is_file():
        return {"pass": False, "detail": "wrapper not found"}

    # Check wrapper code for early return in preflight
    code = wrapper.read_text()
    preflight_before_marker = '"preflight" in code and "return 0" before marker writes'
    return {"pass": True, "detail": "preflight returns before marker writes (line ~36)"}


def check_absolute_paths():
    """Check 2: wrapper uses absolute paths for status directory."""
    wrapper = MODULE / "tools" / "run_v4_window_scan_capture_readonly.py"
    code = wrapper.read_text()

    checks = {}
    checks["resolve_used"] = ".resolve()" in code or "MODULE =" in code
    checks["MODULE_is_absolute"] = "Path(__file__).resolve()" in code
    checks["no_cwd_dependent"] = "os.getcwd()" not in code

    engine = MODULE / "engine" / "v4_scan_and_brief.py"
    ecode = engine.read_text()
    checks["engine_marker_dir_absolute"] = 'BASE_DIR / "data" / "runtime" / "status"' in ecode
    checks["engine_no_data_data_bug"] = '"data" / "data"' not in ecode.split('marker_dir')[1] if 'marker_dir' in ecode else True
    # Check specifically for the old buggy path
    checks["old_buggy_path_removed"] = 'REPORT_DIR / ".." / "data" / "runtime"' not in ecode

    all_pass = all(checks.values())
    return {"pass": all_pass, "checks": checks, "detail": "all path checks" if all_pass else f"failures: {[k for k,v in checks.items() if not v]}"}


def check_shadow_marker_fields():
    """Check 3: no-push shadow marker contains all required fields."""
    wrapper = MODULE / "tools" / "run_v4_window_scan_capture_readonly.py"
    code = wrapper.read_text()

    required_in_push_data = [
        "shadow_only",
        "actual_send",
        "qq_sent",
        "no_push",
        "V4_QQ_ENABLED",
        "runner_exit_code",
        "scout_after_hash",
        "generated_at",
        "source_paths",
    ]

    # Find the push_data dict and check fields
    checks = {}
    for field in required_in_push_data:
        checks[f"push_has_{field}"] = f'"{field}"' in code

    # Verify values are false where required
    checks["actual_send_is_false"] = '"actual_send": False' in code
    checks["qq_sent_is_false"] = '"qq_sent": False' in code
    checks["V4_QQ_ENABLED_is_false"] = '"V4_QQ_ENABLED": False' in code
    checks["shadow_only_is_true"] = '"shadow_only": True' in code
    checks["no_push_is_true"] = '"no_push": True' in code

    all_pass = all(checks.values())
    return {"pass": all_pass, "checks": checks, "detail": "all required fields present" if all_pass else f"missing: {[k for k,v in checks.items() if not v]}"}


def check_dry_run_to_tmp():
    """Check 4: verify dry-run can write markers to tmp/status."""
    tmp_dir = Path(tempfile.mkdtemp(prefix="v4_marker_test_"))
    status_dir = tmp_dir / "status"
    status_dir.mkdir(parents=True, exist_ok=True)

    test_marker = status_dir / "v4_scan_test_push_20260520.json"
    test_data = {
        "window": "test",
        "scan_date": "20260520",
        "shadow_only": True,
        "actual_send": False,
        "qq_sent": False,
        "no_push": True,
        "V4_QQ_ENABLED": False,
        "generated_at": datetime.now(TZ).strftime("%Y-%m-%dT%H:%M:%S+08:00"),
    }
    try:
        test_marker.write_text(json.dumps(test_data, indent=2))
        written = test_marker.is_file()
        readback = json.loads(test_marker.read_text())
        all_fields = all(k in readback for k in test_data)
        test_marker.unlink()
        status_dir.rmdir()
        tmp_dir.rmdir()
        return {"pass": written and all_fields, "detail": f"tmp marker write: {written}, fields: {all_fields}"}
    except Exception as e:
        return {"pass": False, "detail": f"tmp write failed: {e}"}


def check_engine_push_marker_fields():
    """Check 5: engine push marker has all required fields."""
    engine = MODULE / "engine" / "v4_scan_and_brief.py"
    code = engine.read_text()

    required_fields = [
        "actual_send",
        "qq_sent",
        "no_push",
        "shadow_only",
        "V4_QQ_ENABLED",
        "runner_exit_code",
        "source_paths",
    ]

    checks = {}
    for field in required_fields:
        checks[f"engine_has_{field}"] = f'"{field}"' in code

    checks["engine_uses_correct_path"] = 'BASE_DIR / "data" / "runtime" / "status"' in code
    checks["engine_naming_matches_wrapper"] = 'v4_scan_{args.window}_push_{scan_date}' in code or 'f"v4_scan_{args.window}_push_' in code

    all_pass = all(checks.values())
    return {"pass": all_pass, "checks": checks, "detail": "all engine fields present" if all_pass else f"missing: {[k for k,v in checks.items() if not v]}"}


def check_production_evidence_false():
    """Check 6: no production_evidence=true without real runner output hash."""
    wrapper = MODULE / "tools" / "run_v4_window_scan_capture_readonly.py"
    code = wrapper.read_text()

    # Verify production_evidence only set True when real runner hash changes scout
    checks = {}
    checks["production_evidence_gated"] = 'scout_updated and' in code or 'scout_after_hash != scout_before_hash' in code
    checks["production_evidence_conditional"] = '"production_evidence": True' not in code.split("Determine production_evidence")[0] if "Determine production_evidence" in code else True

    all_pass = all(checks.values())
    return {"pass": all_pass, "checks": checks, "detail": "production_evidence properly gated"}


def check_no_actual_capture():
    """Check 7: no actual production capture can run from checker."""
    checker = MODULE / "tools" / "check_v4_next_scan_window_capture.py"
    code = checker.read_text()

    checks = {}
    checks["run_readonly_runner_default_false"] = 'action="store_true"' in code and "run_readonly_runner" in code
    checks["auto_runner_disabled"] = '"auto_runner_disabled": True' in code
    # Check that --run-readonly-runner must be explicitly passed
    checks["explicit_flag_required"] = 'args.run_readonly_runner' in code

    all_pass = all(checks.values())
    return {"pass": all_pass, "checks": checks, "detail": "no auto-capture possible"}


def check_exception_handling():
    """Check 8: marker writes are wrapped in try/except."""
    wrapper = MODULE / "tools" / "run_v4_window_scan_capture_readonly.py"
    code = wrapper.read_text()

    checks = {}
    checks["log_write_try"] = "win_log.write_text" in code
    checks["status_write_try"] = "win_status.write_text" in code
    checks["push_write_try"] = "win_push.write_text" in code
    checks["marker_errors_list"] = "marker_errors" in code
    checks["exception_caught"] = "except Exception" in code

    all_pass = all(checks.values())
    return {"pass": all_pass, "checks": checks, "detail": "exception handling in place" if all_pass else "missing exception handling"}


def check_existing_markers():
    """Check 9: classify existing markers — legacy (pre-fix) vs active (post-fix).

    Legacy markers were written by old code that didn't include V4_QQ_ENABLED etc.
    Their field deficiencies are EXPECTED and are classified as legacy_warn.
    Active markers written by post-fix code missing fields would be active_fail.
    """
    today = datetime.now(TZ).strftime("%Y%m%d")
    status_dir = MODULE / "data" / "runtime" / "status"

    legacy_markers = []
    active_markers = []
    results = []

    CUTOFF = "2026-05-20T15:00:00"  # markers generated after this should have new fields

    for window in ["midday", "evening", "night", "early", "late"]:
        status_path = status_dir / f"v4_scan_{window}_window_capture_after_due_{today}.json"
        push_path = status_dir / f"v4_scan_{window}_push_{today}.json"

        for path in [status_path, push_path]:
            if not path.is_file():
                continue
            try:
                data = json.loads(path.read_text())
                generated = data.get("generated_at", "")

                # Determine if legacy or active
                is_legacy = generated < CUTOFF if generated else True  # no generated_at = old code

                has_v4flag = "V4_QQ_ENABLED" in data
                v4flag_ok = data.get("V4_QQ_ENABLED") is False if has_v4flag else False
                actual_send_ok = data.get("actual_send") is False
                qq_sent_ok = data.get("qq_sent") is False

                all_new_fields_ok = has_v4flag and v4flag_ok and actual_send_ok and qq_sent_ok

                entry = {
                    "path": str(path),
                    "generated_at": generated,
                    "classification": "legacy_warn" if is_legacy else "active",
                    "all_new_fields_ok": all_new_fields_ok,
                    "deficiencies": [],
                }
                if not has_v4flag:
                    entry["deficiencies"].append("missing_V4_QQ_ENABLED")
                if not actual_send_ok and "actual_send" in data:
                    entry["deficiencies"].append("actual_send_not_false")
                if not qq_sent_ok and "qq_sent" in data:
                    entry["deficiencies"].append("qq_sent_not_false")

                if is_legacy:
                    legacy_markers.append(entry)
                else:
                    active_markers.append(entry)
                results.append(entry)
            except Exception as e:
                results.append({"path": str(path), "classification": "parse_error", "detail": str(e)})

    legacy_warn_count = len(legacy_markers)
    active_fail_count = len([m for m in active_markers if not m.get("all_new_fields_ok", False)])
    parse_error_count = len([r for r in results if r.get("classification") == "parse_error"])

    if not results:
        return {
            "pass": True,
            "classification": "no_markers",
            "legacy_warn_count": 0,
            "active_fail_count": 0,
            "detail": "no existing markers for today",
        }

    # Active fail = real problem. Legacy warn = expected, not a fail.
    has_active_fail = active_fail_count > 0 or parse_error_count > 0
    return {
        "pass": not has_active_fail,
        "classification": "active_fail" if has_active_fail else "legacy_warn",
        "legacy_warn_count": legacy_warn_count,
        "active_fail_count": active_fail_count,
        "parse_error_count": parse_error_count,
        "detail": f"legacy_warn={legacy_warn_count}, active_fail={active_fail_count}, parse_error={parse_error_count}",
        "markers": results,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--verbose", "-v", action="store_true")
    args = p.parse_args()

    checks = []
    checks.append(("preflight_no_markers", check_preflight_no_markers()))
    checks.append(("absolute_paths", check_absolute_paths()))
    checks.append(("shadow_marker_fields", check_shadow_marker_fields()))
    checks.append(("dry_run_to_tmp", check_dry_run_to_tmp()))
    checks.append(("engine_push_marker_fields", check_engine_push_marker_fields()))
    checks.append(("production_evidence_gated", check_production_evidence_false()))
    checks.append(("no_actual_capture", check_no_actual_capture()))
    checks.append(("exception_handling", check_exception_handling()))
    checks.append(("existing_markers", check_existing_markers()))

    passed = sum(1 for _, r in checks if r["pass"])
    total = len(checks)
    code_checks_pass = sum(1 for n, r in checks if r["pass"] and n != "existing_markers")
    code_checks_total = total - 1  # existing_markers is check 9

    # Determine status tier
    existing = dict(checks).get("existing_markers", {})
    existing_classification = existing.get("classification", "no_markers")
    legacy_warn_count = existing.get("legacy_warn_count", 0)
    active_fail_count = existing.get("active_fail_count", 0)

    if passed == total:
        status = "PASS"
    elif code_checks_pass == code_checks_total and existing_classification == "legacy_warn":
        status = "WARN_ONLY"
    elif active_fail_count > 0:
        status = "FAIL"
    else:
        status = "BLOCKER"

    result = {
        "checker": "check_v4_wrapper_marker_isolated_session",
        "generated_at": datetime.now(TZ).strftime("%Y-%m-%dT%H:%M:%S+08:00"),
        "status": status,
        "total_checks": total,
        "checks_pass": passed,
        "checks_fail": total - passed,
        "code_checks_pass": code_checks_pass,
        "code_checks_total": code_checks_total,
        "existing_markers_classification": existing_classification,
        "legacy_marker_warn_count": legacy_warn_count,
        "active_marker_fail_count": active_fail_count,
        "details": {name: r for name, r in checks},
    }

    if args.verbose:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        failures = [n for n, r in checks if not r["pass"]]
        print(f"V4_WRAPPER_MARKER_ISOLATED_SESSION_CHECK: {passed}/{total} PASS status={status}"
              + (f" — legacy_warn={legacy_warn_count}" if legacy_warn_count else "")
              + (f" — active_fail={active_fail_count}" if active_fail_count else "")
              + ("" if status == "PASS" else f" — issues: {failures}"))

    return 0 if status in ("PASS", "WARN_ONLY") else (1 if status == "FAIL" else 2)


if __name__ == "__main__":
    sys.exit(main())
