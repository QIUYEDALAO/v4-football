#!/usr/bin/env python3
"""Phase V4-A checker: V4 boundary & A/B/C/SKIP contract."""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

CN = timezone(timedelta(hours=8))
BASE_DIR = Path(__file__).resolve().parent.parent
STATUS_DIR = BASE_DIR / "data" / "runtime" / "status"
DOC_PATH = BASE_DIR / "docs" / "V4_BOUNDARY_AND_CONTRACT.md"
OUT_PATH = STATUS_DIR / "v4_boundary_contract_check.json"

ALLOWED_GRADES = ["A", "B", "C", "SKIP"]
NON_STANDARD_GRADE_PATTERNS = [
    r"\bS\+\b",
    r"\bS\b",
    r"\bD\b",
    r"\bWATCH\b",
    r"\bCANDIDATE\b",
    r"\bBET\b",
    r"\bSTRONG\b",
    r"主推",
]

REQUIRED_DOC_PHRASES = {
    "skip_not_recommendation": "SKIP is not recommendation",
    "c_not_main_recommendation": "C is not main recommendation",
    "no_ai_recalculation": "no AI recalculation",
    "qq_guard_required": "guard required before QQ",
    "watchdog_required": "watchdog required",
    "route_sent_required": "route/sent marker required",
}

SCAN_DIRS = ["engine", "docs", "templates", "config"]
TEXT_SUFFIXES = {".py", ".md", ".yaml", ".yml", ".json", ".txt", ".html"}


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def _iter_v4_related_files() -> list[Path]:
    results: list[Path] = []
    for root in SCAN_DIRS:
        root_path = BASE_DIR / root
        if not root_path.exists():
            continue
        for p in root_path.rglob("*"):
            if not p.is_file():
                continue
            if p.suffix.lower() not in TEXT_SUFFIXES:
                continue
            rel = str(p.relative_to(BASE_DIR)).lower()
            if "v4" in rel or "上半场" in rel or "qq" in rel or "watchdog" in rel or "attribution" in rel or "rolling" in rel or "skip" in rel:
                results.append(p)
    return sorted(set(results))


def main() -> None:
    STATUS_DIR.mkdir(parents=True, exist_ok=True)

    blockers: list[str] = []
    warnings: list[str] = []

    doc_exists = DOC_PATH.exists()
    doc_text = _read_text(DOC_PATH) if doc_exists else ""

    if not doc_exists:
        blockers.append("v4_contract_doc_missing")

    grades_locked = all(g in doc_text for g in ALLOWED_GRADES) if doc_exists else False
    if not grades_locked:
        blockers.append("allowed_grades_not_fully_declared")

    phrase_checks: dict[str, bool] = {
        key: (phrase in doc_text) for key, phrase in REQUIRED_DOC_PHRASES.items()
    }
    for key, ok in phrase_checks.items():
        if not ok:
            blockers.append(f"missing_contract_phrase:{key}")

    v4_files = _iter_v4_related_files()
    v4_file_list = [str(p.relative_to(BASE_DIR)) for p in v4_files]

    v33_hits: list[str] = []
    non_std_hits: list[str] = []

    for p in v4_files:
        txt = _read_text(p)
        rel = str(p.relative_to(BASE_DIR))

        if re.search(r"\bV33\b", txt, flags=re.IGNORECASE):
            v33_hits.append(rel)

        for pat in NON_STANDARD_GRADE_PATTERNS:
            if re.search(pat, txt, flags=re.IGNORECASE):
                non_std_hits.append(f"{rel}:{pat}")
                break

    v33_reference_found = len(v33_hits) > 0
    non_standard_grade_found = len(non_std_hits) > 0

    if v33_reference_found:
        warnings.append("v33_reference_found")
    if non_standard_grade_found:
        warnings.append("non_standard_grade_found")

    # heuristics for module completeness expectation (inventory only)
    expected_keywords = {
        "renderer": any("renderer" in p.lower() for p in v4_file_list),
        "guard": any("guard" in p.lower() for p in v4_file_list),
        "watchdog": any("watchdog" in p.lower() for p in v4_file_list),
        "report": any("report" in p.lower() for p in v4_file_list),
        "attribution": any("attribution" in p.lower() for p in v4_file_list),
        "rolling": any("rolling" in p.lower() for p in v4_file_list),
        "qq": any("qq" in p.lower() for p in v4_file_list),
    }
    missing_modules = [k for k, ok in expected_keywords.items() if not ok]

    if blockers:
        check_status = "BLOCKER"
    elif warnings:
        check_status = "WARN"
    else:
        check_status = "PASS"

    out: dict[str, Any] = {
        "schema_version": "v4_boundary_contract_check.v1",
        "generated_at": datetime.now(CN).isoformat(),
        "check_status": check_status,
        "v4_contract_doc_exists": doc_exists,
        "allowed_grades": ALLOWED_GRADES,
        "grades_locked": grades_locked,
        "skip_not_recommendation": phrase_checks.get("skip_not_recommendation", False),
        "c_not_main_recommendation": phrase_checks.get("c_not_main_recommendation", False),
        "no_ai_recalculation": phrase_checks.get("no_ai_recalculation", False),
        "qq_guard_required": phrase_checks.get("qq_guard_required", False),
        "watchdog_required": phrase_checks.get("watchdog_required", False),
        "route_marker_required": phrase_checks.get("route_sent_required", False),
        "sent_marker_required": phrase_checks.get("route_sent_required", False),
        "v33_reference_found": v33_reference_found,
        "v33_hit_files": sorted(v33_hits),
        "non_standard_grade_found": non_standard_grade_found,
        "non_standard_grade_hits": sorted(non_std_hits),
        "v4_files_found_count": len(v4_file_list),
        "v4_files_found": v4_file_list,
        "v4_missing_modules": missing_modules,
        "production_verified": False,
        "warnings": warnings,
        "blockers": blockers,
    }

    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))

    if check_status == "BLOCKER":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
