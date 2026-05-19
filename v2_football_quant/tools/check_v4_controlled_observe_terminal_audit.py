#!/usr/bin/env python3
"""
V4-I.3: Controlled Observe Terminal Audit Checker

Fail-closed checker for terminal audit package generation.
This checker does NOT execute real observe; it only validates review artifacts
and replays no-exec checkers.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = MODULE_ROOT / "docs"
TOOLS_DIR = MODULE_ROOT / "tools"
STATUS_DIR = MODULE_ROOT / "data" / "runtime" / "status"

TERMINAL_AUDIT_DOC = DOCS_DIR / "V4_CONTROLLED_OBSERVE_TERMINAL_AUDIT.md"
V4_J_GATE_DOC = DOCS_DIR / "V4_J_GATE_PACKAGE.md"
CLASSIFICATION_DOC = DOCS_DIR / "V4_TERMINAL_TRUE_PERMISSION_GREP_CLASSIFICATION.md"

REQUIRED_CHECKER_FILES = [
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
]

REPLAY_CHECKERS = [
    "check_v4_production_readiness.py",
    "check_v4_controlled_observe_runner.py",
    "check_v4_controlled_observe_execution_review.py",
    "check_v4_active_contamination.py",
]

MARKERS = {
    "production_readiness": STATUS_DIR / "v4_production_readiness_check.json",
    "runner": STATUS_DIR / "v4_controlled_observe_runner_check.json",
    "execution_review": STATUS_DIR / "v4_controlled_observe_execution_review_check.json",
    "active_contamination": STATUS_DIR / "v4_active_contamination_check.json",
}

FORBIDDEN_STAGE_PATTERNS = [
    "data/runtime",
    "data/state",
    "data/paper_trading",
    "engine/net_utils.py",
    "secret",
    ".env",
    "token",
    "key",
    ".xlsx",
    ".xls",
]


def _parse_status(stdout: str) -> str:
    match = re.search(r"Status:\s*([A-Z]+)", stdout)
    return match.group(1).strip() if match else "UNKNOWN"


def _run_checker(script_name: str) -> dict:
    script_path = TOOLS_DIR / script_name
    if not script_path.is_file():
        return {
            "script": script_name,
            "exists": False,
            "returncode": 127,
            "status": "MISSING",
            "stderr": "checker file missing",
        }
    proc = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=MODULE_ROOT,
        capture_output=True,
        text=True,
    )
    return {
        "script": script_name,
        "exists": True,
        "returncode": proc.returncode,
        "status": _parse_status(proc.stdout),
        "stderr": proc.stderr.strip(),
    }


def _load_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _parse_count(doc_text: str, key: str) -> int | None:
    match = re.search(rf"\b{re.escape(key)}\s*=\s*(\d+)\b", doc_text)
    if not match:
        return None
    return int(match.group(1))


def _scan_legacy_wrong_phase_hits() -> list[str]:
    legacy_token = "v4_" + "12"
    hits = []
    for rel_root in ("engine", "docs", "tools"):
        root = MODULE_ROOT / rel_root
        if not root.is_dir():
            continue
        for p in root.rglob("*"):
            if not p.is_file():
                continue
            if "__pycache__" in p.parts:
                continue
            try:
                text = p.read_text(encoding="utf-8")
            except Exception:
                continue
            if legacy_token in text:
                for ln, line in enumerate(text.splitlines(), start=1):
                    if legacy_token in line:
                        hits.append(f"{p.relative_to(MODULE_ROOT)}:{ln}:{line.strip()}")
    return hits


def _staged_forbidden_hits() -> list[str]:
    proc = subprocess.run(
        ["git", "diff", "--name-only", "--cached"],
        cwd=MODULE_ROOT,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return [f"git_diff_cached_failed:{proc.returncode}"]
    staged = [x.strip() for x in proc.stdout.splitlines() if x.strip()]
    out = []
    for path in staged:
        path_lower = path.lower()
        if any(token in path_lower for token in FORBIDDEN_STAGE_PATTERNS):
            out.append(path)
    return out


def main() -> int:
    results = {
        "schema_version": "v4_controlled_observe_terminal_audit_check.v1",
        "generated_at": datetime.now().astimezone().isoformat(),
        "check_status": "PASS",
        "terminal_audit_doc_exists": TERMINAL_AUDIT_DOC.is_file(),
        "v4_j_gate_package_exists": V4_J_GATE_DOC.is_file(),
        "true_permission_classification_doc_exists": CLASSIFICATION_DOC.is_file(),
        "all_required_v4_checker_files_present": True,
        "required_checker_files_missing": [],
        "replayed_checker_status": {},
        "no_active_permission_leak": True,
        "active_leak_count": None,
        "unclassified_count": None,
        "legacy_wrong_phase_hits_zero": True,
        "legacy_wrong_phase_hits": [],
        "no_active_forbidden_terms": True,
        "active_contamination_count": None,
        "four_window_execution_review_status": "UNKNOWN",
        "runner_checker_status": "UNKNOWN",
        "production_readiness_checker_status": "UNKNOWN",
        "route_marker_written": False,
        "sent_marker_written": False,
        "qq_sent": False,
        "state_written": False,
        "verified_written": False,
        "production_verified": False,
        "phase_e_allowed": False,
        "v4_j_allowed_to_generate": True,
        "v4_j_allowed_to_execute": False,
        "forbidden_staged_files_found": [],
        "blockers": [],
        "warnings": [],
    }

    # Required docs
    if not results["terminal_audit_doc_exists"]:
        results["blockers"].append("missing_doc:docs/V4_CONTROLLED_OBSERVE_TERMINAL_AUDIT.md")
    if not results["v4_j_gate_package_exists"]:
        results["blockers"].append("missing_doc:docs/V4_J_GATE_PACKAGE.md")
    if not results["true_permission_classification_doc_exists"]:
        results["blockers"].append("missing_doc:docs/V4_TERMINAL_TRUE_PERMISSION_GREP_CLASSIFICATION.md")

    # Required checker files
    for script in REQUIRED_CHECKER_FILES:
        if not (TOOLS_DIR / script).is_file():
            results["required_checker_files_missing"].append(script)
    if results["required_checker_files_missing"]:
        results["all_required_v4_checker_files_present"] = False
        results["blockers"].append(
            f"missing_required_checkers:{results['required_checker_files_missing']}"
        )

    # Replay core checkers
    for script in REPLAY_CHECKERS:
        run = _run_checker(script)
        results["replayed_checker_status"][script] = {
            "status": run["status"],
            "returncode": run["returncode"],
        }
        if not run["exists"]:
            results["blockers"].append(f"replay_missing:{script}")
            continue
        if run["returncode"] != 0 or run["status"] == "BLOCKER":
            results["blockers"].append(
                f"replay_blocker:{script}:status={run['status']}:rc={run['returncode']}"
            )

    results["production_readiness_checker_status"] = results["replayed_checker_status"].get(
        "check_v4_production_readiness.py", {}
    ).get("status", "UNKNOWN")
    results["runner_checker_status"] = results["replayed_checker_status"].get(
        "check_v4_controlled_observe_runner.py", {}
    ).get("status", "UNKNOWN")
    results["four_window_execution_review_status"] = results["replayed_checker_status"].get(
        "check_v4_controlled_observe_execution_review.py", {}
    ).get("status", "UNKNOWN")

    # Marker checks
    readiness = _load_json(MARKERS["production_readiness"])
    runner = _load_json(MARKERS["runner"])
    exec_review = _load_json(MARKERS["execution_review"])
    contamination = _load_json(MARKERS["active_contamination"])

    if not readiness:
        results["warnings"].append("missing_or_invalid_marker:v4_production_readiness_check.json")
    if not runner:
        results["blockers"].append("missing_or_invalid_marker:v4_controlled_observe_runner_check.json")
    if not exec_review:
        results["blockers"].append("missing_or_invalid_marker:v4_controlled_observe_execution_review_check.json")
    if not contamination:
        results["blockers"].append("missing_or_invalid_marker:v4_active_contamination_check.json")

    if contamination:
        acc = contamination.get("active_contamination_count")
        results["active_contamination_count"] = acc
        if acc != 0:
            results["no_active_forbidden_terms"] = False
            results["blockers"].append(f"active_contamination_count_not_zero:{acc}")
        for key in (
            "active_v33_reference_found",
            "active_v38_reference_found",
            "active_non_standard_grade_found",
            "renderer_output_pollution_found",
            "qq_brief_pollution_found",
            "report_template_pollution_found",
        ):
            if contamination.get(key) is True:
                results["no_active_forbidden_terms"] = False
                results["blockers"].append(f"active_forbidden_term_flag_true:{key}")

    # Execution review marker hard checks
    if exec_review:
        must_false_keys = [
            "route_marker_written",
            "sent_marker_written",
            "qq_sent",
            "state_written",
            "verified_written",
            "production_verified",
            "phase_e_allowed",
            "v4_i2_allowed_to_execute",
            "v4_j_allowed_to_execute",
        ]
        for key in must_false_keys:
            value = bool(exec_review.get(key, True))
            results[key] = value
            if value:
                results["blockers"].append(f"execution_review_flag_true:{key}")

        # no-exec expectations
        if exec_review.get("windows_tested") != 4:
            results["blockers"].append(
                f"windows_tested_not_4:{exec_review.get('windows_tested')}"
            )
        if exec_review.get("windows_passed") != 4:
            results["blockers"].append(
                f"windows_passed_not_4:{exec_review.get('windows_passed')}"
            )
        for key in (
            "all_windows_no_exec",
            "all_windows_no_push",
            "all_windows_no_state",
            "all_windows_no_verified",
            "all_windows_no_api",
            "all_windows_no_key_read",
        ):
            if exec_review.get(key) is not True:
                results["blockers"].append(f"execution_review_expect_true_failed:{key}")

        results["v4_j_allowed_to_generate"] = bool(
            exec_review.get("v4_j_allowed_to_generate", True)
        )
        results["v4_j_allowed_to_execute"] = bool(
            exec_review.get("v4_j_allowed_to_execute", False)
        )

    # Runner marker constraints
    if runner:
        if runner.get("negative_missing_date_test") != "PASS":
            results["blockers"].append("runner_negative_missing_date_not_pass")
        if runner.get("negative_missing_window_test") != "PASS":
            results["blockers"].append("runner_negative_missing_window_not_pass")
        if runner.get("negative_invalid_window_test") != "PASS":
            results["blockers"].append("runner_negative_invalid_window_not_pass")
        if runner.get("allowed_windows") != ["early", "midday", "evening", "night"]:
            results["blockers"].append(
                f"runner_allowed_windows_mismatch:{runner.get('allowed_windows')}"
            )
        if bool(runner.get("observe_execution_allowed", True)):
            results["blockers"].append("runner_observe_execution_allowed_true")
        if bool(runner.get("v4_j_allowed_to_execute", True)):
            results["blockers"].append("runner_v4_j_allowed_to_execute_true")

    # Classification checks
    if results["true_permission_classification_doc_exists"]:
        doc_text = CLASSIFICATION_DOC.read_text(encoding="utf-8")
        results["active_leak_count"] = _parse_count(doc_text, "active_leak_count")
        results["unclassified_count"] = _parse_count(doc_text, "unclassified_count")
        if results["active_leak_count"] is None:
            results["warnings"].append("classification_missing:active_leak_count")
        elif results["active_leak_count"] != 0:
            results["no_active_permission_leak"] = False
            results["blockers"].append(
                f"classification_active_leak_count_not_zero:{results['active_leak_count']}"
            )
        if results["unclassified_count"] is None:
            results["warnings"].append("classification_missing:unclassified_count")
        elif results["unclassified_count"] != 0:
            results["no_active_permission_leak"] = False
            results["blockers"].append(
                f"classification_unclassified_count_not_zero:{results['unclassified_count']}"
            )

    # Legacy wrong-phase token residue
    legacy_hits = _scan_legacy_wrong_phase_hits()
    results["legacy_wrong_phase_hits"] = legacy_hits
    if legacy_hits:
        results["legacy_wrong_phase_hits_zero"] = False
        results["blockers"].append(f"legacy_wrong_phase_token_found:{len(legacy_hits)}")

    # Staged forbidden file check
    forbidden_staged = _staged_forbidden_hits()
    results["forbidden_staged_files_found"] = forbidden_staged
    if forbidden_staged:
        results["blockers"].append(f"forbidden_staged_files:{forbidden_staged}")

    if results["v4_j_allowed_to_execute"]:
        results["blockers"].append("v4_j_allowed_to_execute_true")
    if results["production_verified"]:
        results["blockers"].append("production_verified_true")
    if results["phase_e_allowed"]:
        results["blockers"].append("phase_e_allowed_true")

    if results["blockers"]:
        results["check_status"] = "BLOCKER"
    elif results["warnings"]:
        results["check_status"] = "WARN"

    print("=" * 72)
    print("V4 CONTROLLED OBSERVE TERMINAL AUDIT CHECKER")
    print("=" * 72)
    print(f"Status: {results['check_status']}")
    for key in (
        "terminal_audit_doc_exists",
        "v4_j_gate_package_exists",
        "true_permission_classification_doc_exists",
        "all_required_v4_checker_files_present",
        "no_active_permission_leak",
        "active_leak_count",
        "unclassified_count",
        "legacy_wrong_phase_hits_zero",
        "no_active_forbidden_terms",
        "active_contamination_count",
        "production_readiness_checker_status",
        "runner_checker_status",
        "four_window_execution_review_status",
        "route_marker_written",
        "sent_marker_written",
        "qq_sent",
        "state_written",
        "verified_written",
        "production_verified",
        "phase_e_allowed",
        "v4_j_allowed_to_generate",
        "v4_j_allowed_to_execute",
    ):
        print(f"  {key}: {results.get(key)}")

    if results["blockers"]:
        print(f"\nBLOCKERS ({len(results['blockers'])}):")
        for b in results["blockers"]:
            print(f"  ! {b}")
    elif results["warnings"]:
        print(f"\nWARNINGS ({len(results['warnings'])}):")
        for w in results["warnings"]:
            print(f"  ? {w}")

    STATUS_DIR.mkdir(parents=True, exist_ok=True)
    marker = STATUS_DIR / "v4_controlled_observe_terminal_audit_check.json"
    marker.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nMarker: {marker} (NOT committed)")

    return 1 if results["check_status"] == "BLOCKER" else 0


if __name__ == "__main__":
    raise SystemExit(main())
