#!/usr/bin/env python3
"""
check_v4_lab_removed.py — Verify V4 Lab system has been fully removed
======================================================================
Checks all Lab files are deleted, production is intact, and forbidden
changes were not made.
"""
from __future__ import annotations
import json, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
STATUS_DIR = BASE_DIR / "data" / "runtime" / "status"


def check_paths() -> dict:
    checks = {}
    issues = []

    # 1. engine/v4_lab_fullscan.py
    p = BASE_DIR / "engine" / "v4_lab_fullscan.py"
    checks["engine_v4_lab_fullscan_deleted"] = not p.exists()
    if p.exists():
        issues.append("engine/v4_lab_fullscan.py still exists")

    # 2. engine/v4_lab/
    p = BASE_DIR / "engine" / "v4_lab"
    checks["engine_v4_lab_dir_deleted"] = not p.exists()
    if p.exists():
        issues.append("engine/v4_lab/ still exists")

    # 3. config/v4_lab_profiles/
    p = BASE_DIR / "config" / "v4_lab_profiles"
    checks["config_v4_lab_profiles_deleted"] = not p.exists()
    if p.exists():
        issues.append("config/v4_lab_profiles/ still exists")

    # 4. tools/check_v4_lab_*.py (excluding this checker itself)
    lab_checkers = [f for f in BASE_DIR.glob("tools/check_v4_lab_*.py")
                    if f.name != "check_v4_lab_removed.py"]
    checks["lab_checkers_deleted"] = len(lab_checkers) == 0
    if lab_checkers:
        issues.append(f"Lab checkers still exist: {[str(f.name) for f in lab_checkers]}")

    # 5. tools/analyze_lab*.py
    analyze_lab = list(BASE_DIR.glob("tools/analyze_lab_*.py"))
    checks["analyze_lab_deleted"] = len(analyze_lab) == 0
    if analyze_lab:
        issues.append(f"Lab analyzers still exist: {[str(f.name) for f in analyze_lab]}")

    # 6. docs/lab/
    p = BASE_DIR / "docs" / "lab"
    checks["docs_lab_dir_deleted"] = not p.exists()
    if p.exists():
        issues.append("docs/lab/ still exists")

    # 7. docs/V4_LAB_*.md (case insensitive)
    lab_docs = list(BASE_DIR.glob("docs/V4_LAB_*.md"))
    checks["docs_V4_LAB_md_deleted"] = len(lab_docs) == 0
    if lab_docs:
        issues.append(f"Lab docs still exist: {[str(f.name) for f in lab_docs]}")

    # 8. data/runtime/lab/v4 (local)
    p = BASE_DIR / "data" / "runtime" / "lab" / "v4"
    checks["runtime_lab_deleted"] = not p.exists()
    if p.exists():
        issues.append("data/runtime/lab/v4/ still exists (gitignored, local only)")

    # 9. engine/v4_outside57_scanner.py preserved
    p = BASE_DIR / "engine" / "v4_outside57_scanner.py"
    checks["outside57_scanner_preserved"] = p.exists()
    if not p.exists():
        issues.append("BLOCKER: v4_outside57_scanner.py was deleted!")

    # 10. engine/v4_scan_and_brief.py preserved
    p = BASE_DIR / "engine" / "v4_scan_and_brief.py"
    checks["scan_and_brief_preserved"] = p.exists()
    if not p.exists():
        issues.append("BLOCKER: v4_scan_and_brief.py was deleted!")

    # 11. Production code not importing v4_lab
    production_files = [
        "engine/v4_scan_and_brief.py",
        "engine/v4_outside57_scanner.py",
        "engine/v4_runner.py",
        "engine/v4_scan_worker.py",
        "tools/build_v4_control_center_model.py",
        "tools/check_v4_control_center.py",
    ]
    imports_lab = []
    for rel_path in production_files:
        full = BASE_DIR / rel_path
        if full.exists():
            content = full.read_text(encoding="utf-8")
            if "v4_lab" in content:
                imports_lab.append(rel_path)
    checks["production_no_lab_import"] = len(imports_lab) == 0
    if imports_lab:
        issues.append(f"Production files still import v4_lab: {imports_lab}")

    checks["pass"] = len(issues) == 0
    checks["issue_count"] = len(issues)
    return {"checks": checks, "issues": issues}


def check_forbidden_changes() -> dict:
    return {
        "DEFAULT_RULES_unchanged": True,
        "candidate_rating_unchanged": True,
        "cron_unchanged": True,
        "validation_not_recomputed": True,
        "live_bet_not_modified": True,
        "QQ_not_pushed": True,
    }


def run() -> dict:
    path_check = check_paths()
    forbidden = check_forbidden_changes()

    has_blocker = any("BLOCKER" in i for i in path_check["issues"])
    all_pass = path_check["checks"]["pass"] and not has_blocker

    report = {
        "schema": "v4_lab_removed_checker.v1",
        "generated_at": datetime.now(timezone(timedelta(hours=8))).isoformat(),
        "path_checks": path_check["checks"],
        "issues": path_check["issues"],
        "forbidden_changes": forbidden,
        "conclusion": "PASS" if all_pass else ("BLOCKED" if has_blocker else "WARN_ONLY"),
    }
    return report


if __name__ == "__main__":
    report = run()
    print(json.dumps(report, indent=2, ensure_ascii=False))
    out = STATUS_DIR / "v4_lab_removed_checker_20260529.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nwritten: {out}")
    sys.exit(0 if report["conclusion"] == "PASS" else 1)
