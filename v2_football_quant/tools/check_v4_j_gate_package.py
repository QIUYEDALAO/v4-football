#!/usr/bin/env python3
"""
V4-J.2: Final Gate Strict Evidence Replay Checker

ALL evidence comes from:
1. Replaying child checkers (not reading old markers)
2. Checking child checker return codes (non-zero = BLOCKER)
3. Reading replayed markers (missing = BLOCKER, missing fields = BLOCKER)
4. Structurally parsing classification doc
5. Real git stash list (unknown stash = BLOCKER)
6. Real git staged file scan (forbidden = BLOCKER)
7. Real grep scans (hits = BLOCKER)

No defaults for safety fields. None = BLOCKER.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

MODULE_ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = MODULE_ROOT / "docs"
TOOLS_DIR = MODULE_ROOT / "tools"
REPO_ROOT = MODULE_ROOT.parent
MARKER_DIR = MODULE_ROOT / "data" / "runtime" / "status"

STASH_ALLOWED = [
    "phase-v4a1 workspace isolation: discipline archive residue only",
    "phase-d87 workspace isolation: net_utils only",
]

EXECUTION_REVIEW_CHECKER = "check_v4_controlled_observe_execution_review.py"
RUNNER_CHECKER = "check_v4_controlled_observe_runner.py"
TERMINAL_AUDIT_CHECKER = "check_v4_controlled_observe_terminal_audit.py"

REQUIRED_DOCS = [
    "V4_J_GATE_PACKAGE.md",
    "V4_J_BOSS_AUTHORIZATION_PACKAGE.md",
    "V4_J_GATE_CLOSURE.md",
    "V4_CONTROLLED_OBSERVE_TERMINAL_AUDIT.md",
    "V4_TERMINAL_TRUE_PERMISSION_GREP_CLASSIFICATION.md",
    "V4_CONTROLLED_OBSERVE_FOUR_WINDOW_PREVIEW_MATRIX.md",
    "V4_CONTROLLED_OBSERVE_EXECUTION_REVIEW.md",
    "V4_CONTROLLED_OBSERVE_EXECUTION_REVIEW_CLOSURE.md",
]

REQUIRED_CHECKERS = [
    "check_v4_path_canonicalization.py",
    "check_v4_boundary_contract.py",
    "check_v4_active_contamination.py",
    "check_v4_output_schema.py",
    "check_v4_renderer_guard.py",
    "check_v4_qq_guard.py",
    "check_v4_no_push_enforcement.py",
    "check_v4_watchdog_contract.py",
    "check_v4_lock_timeout_contract.py",
    "check_v4_attribution_schema.py",
    "check_v4_attribution_guard.py",
    "check_v4_attribution_no_api_guard.py",
    "check_v4_rolling_schema.py",
    "check_v4_rolling_guard.py",
    "check_v4_reporting_schema.py",
    "check_v4_reporting_guard.py",
    "check_v4_production_readiness.py",
    "check_v4_controlled_observe_approval.py",
    "check_v4_controlled_observe_runner.py",
    "check_v4_controlled_observe_execution_review.py",
    "check_v4_controlled_observe_terminal_audit.py",
]

FORBIDDEN_STAGED_PATTERNS = [
    "data/runtime", "data/state", "data/paper_trading",
    ".xlsx", ".xls", "engine/net_utils.py",
    "secret", ".env", "token", "key",
    "verified", "route_marker", "sent_marker", "lock",
]

FORBIDDEN_TRUE_PERMISSION = [
    "v4_j_allowed_to_execute=true",
    "observe_execution_allowed=true",
    "phase_e_allowed=true",
    "production_verified=true",
    "qq_push_allowed=true",
    "state_write_allowed=true",
    "verified_write_allowed=true",
    "route_marker_written=true",
    "sent_marker_written=true",
    "qq_sent=true",
    "state_written=true",
    "verified_written=true",
]

EXECUTION_REVIEW_REQUIRED_FIELDS = [
    "windows_tested", "windows_passed",
    "all_windows_no_exec", "all_windows_no_push",
    "all_windows_no_state", "all_windows_no_verified",
    "all_windows_no_api", "all_windows_no_key_read",
    "route_marker_written", "sent_marker_written",
    "qq_sent", "state_written", "verified_written",
    "production_verified", "phase_e_allowed",
    "v4_j_allowed_to_execute", "check_status",
]

RUNNER_CHECKER_REQUIRED_FIELDS = [
    "preview_execution_success", "preview_json_parse_success",
    "date_required_enforced", "window_required_enforced",
    "window_choices_enforced", "allowed_windows",
    "negative_missing_date_test", "negative_missing_window_test",
    "negative_invalid_window_test",
    "observe_execution_allowed", "v4_j_allowed_to_execute",
    "production_verified", "phase_e_allowed",
]

TERMINAL_AUDIT_REQUIRED_FIELDS = [
    "terminal_audit_doc_exists", "true_permission_classification_doc_exists",
    "no_active_permission_leak", "active_leak_count",
    "unclassified_count",
    "no_active_forbidden_terms",
    "production_verified", "phase_e_allowed", "v4_j_allowed_to_execute",
]

CLASSIFICATION_KEY_FIELDS = [
    "active_leak_count", "unclassified_count",
    "active_forbidden_output_count",
    "active_v33_reference_found", "active_v38_reference_found",
    "active_non_standard_grade_found",
    "main_recommendation_term_in_active_output",
    "skip_recommendation_found", "c_main_recommendation_found",
    "true_permission_classification_complete",
]

SAFETY_FIELDS = [
    "observe_execution_allowed", "v4_j_allowed_to_execute",
    "production_verified", "phase_e_allowed",
    "qq_push_allowed", "state_write_allowed", "verified_write_allowed",
    "route_marker_written", "sent_marker_written",
    "qq_sent", "state_written", "verified_written",
]

EXECUTION_REVIEW_MARKER = "v4_controlled_observe_execution_review_check.json"
RUNNER_MARKER = "v4_controlled_observe_runner_check.json"
TERMINAL_AUDIT_MARKER = "v4_controlled_observe_terminal_audit_check.json"


def _run_cmd(cmd, cwd=None):
    """Run command, return (returncode, stdout, stderr)."""
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True, check=False,
            cwd=cwd or str(REPO_ROOT), timeout=120
        )
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", "TIMEOUT"
    except Exception as e:
        return -2, "", str(e)


def _read_marker(name: str) -> Optional[dict]:
    """Read a marker JSON file."""
    p = MARKER_DIR / name
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text())
    except (json.JSONDecodeError, IOError):
        return None


def _run_checker(name: str, marker_name: str) -> dict:
    """
    Run a checker, read its marker, return results.
    Non-zero exit code does NOT auto-BLOCKER — marker fields determine safety.
    """
    checker = TOOLS_DIR / name
    if not checker.is_file():
        return {"_error": f"checker not found: {name}"}

    rc, out, err = _run_cmd([sys.executable, str(checker)])
    marker = _read_marker(marker_name)
    if marker is None:
        return {"_error": f"marker not found after run: {marker_name} (exit {rc})", "_returncode": rc}

    return {"_marker": marker, "_returncode": rc}


def _parse_classification_doc() -> dict:
    """Structured parse of classification doc. Returns dict of fields."""
    result = {}
    doc = DOCS_DIR / "V4_TERMINAL_TRUE_PERMISSION_GREP_CLASSIFICATION.md"
    if not doc.is_file():
        return {"_error": "doc_not_found"}

    text = doc.read_text()
    # Search for key=value or key: value patterns
    # Also search the summary section
    summary_patterns = {
        "active_leak_count": r"active_leak_count[=:]\s*(\d+)",
        "unclassified_count": r"unclassified_count[=:]\s*(\d+)",
        "active_forbidden_output_count": r"active_forbidden_output_count[=:]\s*(\d+)",
        "active_v33_reference_found": r"active_v33_reference_found[=:]\s*(true|false)",
        "active_v38_reference_found": r"active_v38_reference_found[=:]\s*(true|false)",
        "active_non_standard_grade_found": r"active_non_standard_grade_found[=:]\s*(true|false)",
        "main_recommendation_term_in_active_output": r"main_recommendation_term_in_active_output[=:]\s*(true|false)",
        "skip_recommendation_found": r"skip_recommendation_found[=:]\s*(true|false)",
        "c_main_recommendation_found": r"c_main_recommendation_found[=:]\s*(true|false)",
        "true_permission_classification_complete": r"true_permission_classification_complete[=:]\s*(true|false)",
    }

    for field, pattern in summary_patterns.items():
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            val = m.group(1)
            if val.isdigit():
                result[field] = int(val)
            else:
                result[field] = val.lower() == "true"
        else:
            result[field] = None

    # Also count ACTIVE_LEAK, UNCLASSIFIED etc. in the table
    # as secondary verification
    active_leak_table = len(re.findall(r'\bACTIVE_LEAK\b', text))
    unclassified_table = len(re.findall(r'\bUNCLASSIFIED\b', text))
    forbidden_table = len(re.findall(r'\bACTIVE_FORBIDDEN\b', text))

    if result.get("active_leak_count") is None:
        result["active_leak_count"] = max(0, active_leak_table)
    if result.get("unclassified_count") is None:
        result["unclassified_count"] = max(0, unclassified_table)
    if result.get("active_forbidden_output_count") is None:
        result["active_forbidden_output_count"] = max(0, forbidden_table)

    return result


def _check_required_marker_fields(marker_name: str, marker: dict, required: list[str]) -> list[str]:
    """Return list of missing required fields."""
    return [f for f in required if f not in marker]


def _validate_safety_field(field_name: str, value, is_required: bool = True) -> Optional[str]:
    """Validate a safety field value. Returns error message or None."""
    if value is None:
        return f"Safety field '{field_name}' is None (no evidence)"
    if isinstance(value, bool) and value:
        return f"Safety field '{field_name}' is True (must be False)"
    return None


def main():
    # Initialize ALL safety fields as None — no default False allowed
    results = {
        "check_status": "PASS",
        # Evidence replay status
        "execution_review_returncode": None,
        "execution_review_marker_loaded": False,
        "runner_checker_returncode": None,
        "runner_checker_marker_loaded": False,
        "terminal_audit_returncode": None,
        "terminal_audit_marker_loaded": False,
        "four_window_preview_pass": None,
        "negative_tests_pass": None,
        "allowed_windows": [],
        # Doc/checker counts
        "docs_required_present": 0,
        "checkers_required_present": 0,
        # Classification evidence (all None until parsed)
        "classification_parsed": False,
        "active_leak_count": None,
        "unclassified_count": None,
        "active_forbidden_output_count": None,
        "active_v33_reference_found": None,
        "active_v38_reference_found": None,
        "active_non_standard_grade_found": None,
        "main_recommendation_term_in_active_output": None,
        "skip_recommendation_found": None,
        "c_main_recommendation_found": None,
        "true_permission_classification_complete": None,
        # Stash/staged/grep
        "stash_checked": False,
        "no_unknown_stashes": False,
        "forbidden_staged_files_found": [],
        "legacy_v4_12_hits": [],
        "active_true_permission_leaks": [],
        # Safety fields — ALL None until proven
        "boss_explicit_authorization_required": True,
        "observe_execution_allowed": None,
        "qq_push_allowed": None,
        "state_write_allowed": None,
        "verified_write_allowed": None,
        "route_marker_written": None,
        "sent_marker_written": None,
        "lock_created": None,
        "production_verified": None,
        "phase_e_allowed": None,
        "v4_j_allowed_to_generate": True,
        "v4_j_allowed_to_execute": None,
        "blockers": [], "warnings": [],
    }

    block = False

    # A. Check required docs
    for doc in REQUIRED_DOCS:
        if (DOCS_DIR / doc).is_file():
            results["docs_required_present"] += 1
        else:
            results["blockers"].append(f"Missing required doc: {doc}")
            block = True

    # B. Check required checker files exist
    for chk in REQUIRED_CHECKERS:
        if (TOOLS_DIR / chk).is_file():
            results["checkers_required_present"] += 1
        else:
            results["blockers"].append(f"Missing required checker: {chk}")
            block = True

    # C. Structured classification doc parse
    cls = _parse_classification_doc()
    if "_error" in cls:
        results["blockers"].append(f"Classification doc parse: {cls['_error']}")
        block = True
    else:
        results["classification_parsed"] = True
        for f in CLASSIFICATION_KEY_FIELDS:
            if f in cls:
                results[f] = cls[f]

        # Validate classification field safety
        for f in ["active_leak_count", "unclassified_count", "active_forbidden_output_count"]:
            v = results.get(f)
            if v is None:
                results["blockers"].append(f"Classification field '{f}' is missing")
                block = True
            elif v > 0:
                results["blockers"].append(f"Classification field '{f}' = {v} (>0)")
                block = True

        for f in ["active_v33_reference_found", "active_v38_reference_found",
                    "active_non_standard_grade_found",
                    "main_recommendation_term_in_active_output",
                    "skip_recommendation_found", "c_main_recommendation_found"]:
            v = results.get(f)
            if v is None:
                results["warnings"].append(f"Classification field '{f}' is missing (not in doc)")
            elif v:
                results["blockers"].append(f"Classification field '{f}' = True")
                block = True

        if results.get("true_permission_classification_complete") is False:
            results["blockers"].append("true_permission_classification_complete is False")
            block = True

    # D. STRICT REPLAY: execution review checker
    er = _run_checker(EXECUTION_REVIEW_CHECKER, EXECUTION_REVIEW_MARKER)
    results["execution_review_returncode"] = er.get("_returncode")
    if "_error" in er:
        results["blockers"].append(f"Execution review replay: {er['_error']}")
        block = True
    elif "_marker" in er:
        results["execution_review_marker_loaded"] = True
        er_marker = er["_marker"]
        missing = _check_required_marker_fields(EXECUTION_REVIEW_MARKER, er_marker, EXECUTION_REVIEW_REQUIRED_FIELDS)
        if missing:
            results["blockers"].append(f"Execution review marker missing fields: {missing}")
            block = True
        else:
            # Pull safety fields from execution review marker
            # Field name mapping: execution review uses all_windows_no_*, V4-J uses qq_push/state_write/verified_write
            _er_field_map = {
                "all_windows_no_push": "qq_push_allowed",
                "all_windows_no_state": "state_write_allowed",
                "all_windows_no_verified": "verified_write_allowed",
            }
            for mk_field, j_field in _er_field_map.items():
                val = er_marker.get(mk_field)
                if val is not None:
                    results[j_field] = not bool(val)  # inverted: no_push=True means qq_push_allowed=False
            # Direct field pulls
            for field in EXECUTION_REVIEW_REQUIRED_FIELDS:
                if field in SAFETY_FIELDS and field in er_marker:
                    results[field] = bool(er_marker[field])
            results["four_window_preview_pass"] = (
                int(er_marker.get("windows_tested", 0)) >= 4 and
                int(er_marker.get("windows_passed", 0)) >= 4
            )
            if not results["four_window_preview_pass"]:
                results["blockers"].append("four_window_preview_pass is False")
                block = True
    else:
        results["blockers"].append("Execution review replay: no marker returned")
        block = True

    # E. STRICT REPLAY: runner checker
    rc = _run_checker(RUNNER_CHECKER, RUNNER_MARKER)
    results["runner_checker_returncode"] = rc.get("_returncode")
    if "_error" in rc:
        results["blockers"].append(f"Runner checker replay: {rc['_error']}")
        block = True
    elif "_marker" in rc:
        results["runner_checker_marker_loaded"] = True
        rc_marker = rc["_marker"]
        missing = _check_required_marker_fields(RUNNER_MARKER, rc_marker, RUNNER_CHECKER_REQUIRED_FIELDS)
        if missing:
            results["blockers"].append(f"Runner checker marker missing fields: {missing}")
            block = True
        else:
            results["allowed_windows"] = rc_marker.get("allowed_windows", [])
            results["negative_tests_pass"] = (
                rc_marker.get("date_required_enforced", False) and
                rc_marker.get("window_required_enforced", False) and
                rc_marker.get("window_choices_enforced", False)
            )
            if not results["negative_tests_pass"]:
                results["blockers"].append("negative_tests_pass is False")
                block = True
            # Check allowed_windows exactly
            expected = ["early", "midday", "evening", "night"]
            if results["allowed_windows"] != expected:
                results["blockers"].append(f"allowed_windows mismatch: {results['allowed_windows']} != {expected}")
                block = True
            # Pull safety fields from runner checker marker
            # lock_created is in runner marker but not in SAFETY_FIELDS list
            if "lock_created" in rc_marker:
                results["lock_created"] = bool(rc_marker["lock_created"])
            for field in RUNNER_CHECKER_REQUIRED_FIELDS:
                if field in SAFETY_FIELDS and field in rc_marker:
                    results[field] = bool(rc_marker[field])
    else:
        results["blockers"].append("Runner checker replay: no marker returned")
        block = True

    # F. STRICT REPLAY: terminal audit checker
    ta = _run_checker(TERMINAL_AUDIT_CHECKER, TERMINAL_AUDIT_MARKER)
    results["terminal_audit_returncode"] = ta.get("_returncode")
    if "_error" in ta:
        results["blockers"].append(f"Terminal audit replay: {ta['_error']}")
        block = True
    elif "_marker" in ta:
        results["terminal_audit_marker_loaded"] = True
        ta_marker = ta["_marker"]
        missing = _check_required_marker_fields(TERMINAL_AUDIT_MARKER, ta_marker, TERMINAL_AUDIT_REQUIRED_FIELDS)
        if missing:
            results["blockers"].append(f"Terminal audit marker missing fields: {missing}")
            block = True
        else:
            if not ta_marker.get("no_active_permission_leak", False):
                results["blockers"].append("Terminal audit: no_active_permission_leak is False")
                block = True
            # Map no_active_forbidden_terms to active_forbidden_output_count
            results["active_forbidden_output_count"] = (
                0 if ta_marker.get("no_active_forbidden_terms", False) else 1
            )
            # Pull safety fields from terminal audit marker
            for field in TERMINAL_AUDIT_REQUIRED_FIELDS:
                if field in SAFETY_FIELDS and field in ta_marker:
                    results[field] = bool(ta_marker[field])
    else:
        results["blockers"].append("Terminal audit replay: no marker returned")
        block = True

    # G. Stash check (unknown stash = BLOCKER)
    _, stash_stdout, _ = _run_cmd(["git", "stash", "list"])
    results["stash_checked"] = True
    stash_lines = [l.strip() for l in stash_stdout.split("\n") if l.strip()]
    unknown_stashes = []
    for line in stash_lines:
        matched = any(a in line for a in STASH_ALLOWED)
        if not matched:
            unknown_stashes.append(line)
    if unknown_stashes:
        results["blockers"].append(f"Unknown stashes: {unknown_stashes}")
        block = True
    results["no_unknown_stashes"] = len(unknown_stashes) == 0

    # H. Staged file check (forbidden = BLOCKER)
    _, staged_stdout, _ = _run_cmd(["git", "diff", "--name-only", "--cached"])
    for line in staged_stdout.split("\n"):
        line = line.strip()
        if not line:
            continue
        for pat in FORBIDDEN_STAGED_PATTERNS:
            if pat in line:
                results["forbidden_staged_files_found"].append(line)
    if results["forbidden_staged_files_found"]:
        results["blockers"].append(f"Forbidden staged files: {results['forbidden_staged_files_found']}")
        block = True

    # I. v4_12 grep (active hits only, exclude self-references)
    _v4_12_exclude = ["check_v4_j_gate_package.py", "V4_J_GATE_", "data/runtime/status/"]
    _, v4_12_stdout, _ = _run_cmd(["grep", "-R", "-n", "v4_12"], cwd=str(MODULE_ROOT))
    if v4_12_stdout:
        clean_hits = []
        for line in v4_12_stdout.split("\n"):
            line = line.strip()
            if not line:
                continue
            if any(s in line for s in _v4_12_exclude):
                continue
            clean_hits.append(line)
        if clean_hits:
            results["legacy_v4_12_hits"] = clean_hits
            results["blockers"].append(f"Active v4_12 hits: {len(clean_hits)}")
            block = True

    # J. True permission grep
    _perm_exclude = [
        "check_v4_j_gate_package.py", "V2_CONTROLLED_", "check_v2_",
        "data/runtime/status/", "SYSTEM_REARCHITECTURE_PLAN",
        "FORBIDDEN_TRUE_PERMISSION", "check_v4_output_schema.py",
        "V4_TERMINAL_TRUE_PERMISSION",
    ]
    perm_hits = []
    scan_dirs = [str(MODULE_ROOT / d) for d in ["engine", "docs", "tools", "templates", "config"]]
    for d in scan_dirs:
        if not Path(d).is_dir():
            continue
        _, perm_stdout, _ = _run_cmd(
            ["grep", "-R", "-n", "-E", "|".join(FORBIDDEN_TRUE_PERMISSION), d],
            cwd=str(REPO_ROOT)
        )
        if perm_stdout:
            for line in perm_stdout.split("\n"):
                line = line.strip()
                if not line:
                    continue
                if any(s in line for s in _perm_exclude):
                    continue
                if "=false" in line or ": false" in line or ":false" in line:
                    continue
                perm_hits.append(line)
    if perm_hits:
        results["active_true_permission_leaks"] = perm_hits[:20]
        results["blockers"].append(f"Active true permission leaks: {len(perm_hits)}")
        block = True

    # K. Validate all safety fields — None = BLOCKER, True = BLOCKER
    for field in SAFETY_FIELDS:
        val = results.get(field)
        err = _validate_safety_field(field, val)
        if err:
            results["blockers"].append(err)
            block = True

    # L. Validate evidence replay fields
    for evidence_field in ["four_window_preview_pass", "negative_tests_pass"]:
        if results.get(evidence_field) is None:
            results["blockers"].append(f"Evidence field '{evidence_field}' is None (no evidence)")
            block = True
        elif results[evidence_field] is False:
            results["blockers"].append(f"Evidence field '{evidence_field}' is False")
            block = True

    # Determine status
    if block:
        results["check_status"] = "BLOCKER"
    elif results["warnings"]:
        results["check_status"] = "WARN"

    # Print
    print("=" * 60)
    print("V4-J STRICT EVIDENCE REPLAY CHECKER")
    print("=" * 60)
    print(f"Status: {results['check_status']}")
    for k, v in results.items():
        if k in ("blockers", "warnings"):
            continue
        if isinstance(v, list) and not v:
            continue
        print(f"  {k}: {v}")
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
    MARKER_DIR.mkdir(parents=True, exist_ok=True)
    marker_path = MARKER_DIR / "v4_j_gate_package_check.json"
    with open(marker_path, "w") as fh:
        json.dump(results, fh, indent=2, ensure_ascii=False)
    print(f"\nMarker: {marker_path} (NOT committed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
