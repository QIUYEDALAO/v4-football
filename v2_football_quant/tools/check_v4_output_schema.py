#!/usr/bin/env python3
"""Phase V4-B checker: validate V4 output schema contract document."""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

CN = timezone(timedelta(hours=8))
BASE_DIR = Path(__file__).resolve().parent.parent
STATUS_DIR = BASE_DIR / "data" / "runtime" / "status"
DOC_PATH = BASE_DIR / "docs" / "V4_OUTPUT_SCHEMA.md"
OUT_PATH = STATUS_DIR / "v4_output_schema_check.json"

ALLOWED_GRADES = ["A", "B", "C", "SKIP"]
NON_STANDARD_PATTERNS = [
    re.compile(r"\bWATCH\b"),
    re.compile(r"\bCANDIDATE\b"),
    re.compile(r"\bS\+\b"),
    re.compile(r"\bS级\b"),
    re.compile(r"\bD级\b"),
    re.compile(r"\bBET\b"),
    re.compile(r"\bSTRONG\b"),
    re.compile(r"主推"),
]


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def main() -> None:
    STATUS_DIR.mkdir(parents=True, exist_ok=True)

    blockers: list[str] = []
    warnings: list[str] = []

    schema_doc_exists = DOC_PATH.exists()
    text = _read(DOC_PATH)

    if not schema_doc_exists:
        blockers.append("schema_doc_missing")

    # Strict allowed-grade declaration
    allowed_declared = (
        "Allowed grades exactly" in text
        and "A" in text
        and "B" in text
        and "C" in text
        and "SKIP" in text
    )

    # Non-standard as allowed grade check: inspect "Allowed grades" lines only
    candidate_lines = [
        ln for ln in text.splitlines()
        if "Allowed grades" in ln or "grade must" in ln
    ]
    non_standard_grade_found = False
    for ln in candidate_lines:
        for pat in NON_STANDARD_PATTERNS:
            if pat.search(ln):
                non_standard_grade_found = True

    skip_not_recommendation = "SKIP is not recommendation" in text
    c_not_main_recommendation = "C is not main recommendation" in text

    production_verified = "production_verified=true" in text
    phase_e_allowed = "phase_e_allowed=true" in text
    qq_push_allowed = "qq_push_allowed=true" in text

    v4_c_allowed_to_generate = "v4_c_allowed_to_generate=true" in text
    v4_c_allowed_to_execute = "v4_c_allowed_to_execute=true" in text

    if not schema_doc_exists:
        blockers.append("schema_doc_exists=false")
    if not allowed_declared:
        blockers.append("allowed_grades_not_declared_as_abcskip")
    if non_standard_grade_found:
        blockers.append("non_standard_grade_declared_in_allowed_context")
    if not skip_not_recommendation:
        blockers.append("skip_not_recommendation_missing")
    if not c_not_main_recommendation:
        blockers.append("c_not_main_recommendation_missing")
    if production_verified:
        blockers.append("production_verified_true_in_schema_doc")
    if phase_e_allowed:
        blockers.append("phase_e_allowed_true_in_schema_doc")
    if qq_push_allowed:
        blockers.append("qq_push_allowed_true_in_schema_doc")
    if not v4_c_allowed_to_generate:
        warnings.append("v4_c_allowed_to_generate_not_explicit")
    if v4_c_allowed_to_execute:
        blockers.append("v4_c_allowed_to_execute_true")

    check_status = "BLOCKER" if blockers else ("WARN" if warnings else "PASS")

    out: dict[str, Any] = {
        "schema_version": "v4_output_schema_check.v1",
        "generated_at": datetime.now(CN).isoformat(),
        "check_status": check_status,
        "schema_doc_exists": schema_doc_exists,
        "allowed_grades": ALLOWED_GRADES,
        "non_standard_grade_found": non_standard_grade_found,
        "skip_not_recommendation": skip_not_recommendation,
        "c_not_main_recommendation": c_not_main_recommendation,
        "production_verified": False,
        "phase_e_allowed": False,
        "qq_push_allowed": False,
        "v4_c_allowed_to_generate": True,
        "v4_c_allowed_to_execute": False,
        "blockers": blockers,
        "warnings": warnings,
    }

    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))

    if check_status == "BLOCKER":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
