#!/usr/bin/env python3
"""Phase V4-C checker: QQ brief guard + route/sent contract validation."""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

CN = timezone(timedelta(hours=8))
BASE_DIR = Path(__file__).resolve().parent.parent
STATUS_DIR = BASE_DIR / "data" / "runtime" / "status"
OUT_PATH = STATUS_DIR / "v4_qq_guard_check.json"

QQ_GUARD_DOC = BASE_DIR / "docs" / "V4_QQ_BRIEF_GUARD.md"
ROUTE_SENT_DOC = BASE_DIR / "docs" / "V4_QQ_ROUTE_SENT_MARKER_CONTRACT.md"
QQ_TEMPLATE = BASE_DIR / "templates" / "v4_daily_review_qq_template.md"
QQ_BRIEF_TEMPLATE = BASE_DIR / "templates" / "v4_daily_review_qq_brief.md"

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


def _scan_text(text: str) -> dict[str, bool]:
    active_v33 = bool(re.search(r"\bV33\b", text, flags=re.IGNORECASE))
    active_v38 = bool(re.search(r"\bV38\b", text, flags=re.IGNORECASE))
    non_standard = any(p.search(text) for p in NON_STANDARD_PATTERNS)
    skip_recommendation = bool(
        re.search(r"SKIP.{0,12}(推荐|主推|投注)|(推荐|主推|投注).{0,12}SKIP", text)
    )
    c_main = bool(
        re.search(r"C级?.{0,12}(主推|强推|重注|必选)|(主推|强推|重注|必选).{0,12}C级?", text)
    )
    return {
        "active_v33": active_v33,
        "active_v38": active_v38,
        "non_standard": non_standard,
        "skip_recommendation": skip_recommendation,
        "c_main": c_main,
    }


def main() -> None:
    STATUS_DIR.mkdir(parents=True, exist_ok=True)

    blockers: list[str] = []
    warnings: list[str] = []

    qq_guard_doc_exists = QQ_GUARD_DOC.exists()
    route_sent_contract_exists = ROUTE_SENT_DOC.exists()

    qq_template_text = _read(QQ_TEMPLATE)
    qq_brief_text = _read(QQ_BRIEF_TEMPLATE)
    all_qq_text = qq_template_text + "\n" + qq_brief_text

    qq_template_schema_guard_found = "{{schema_guard_status}}" in all_qq_text
    qq_template_guard_status_found = ("{{guard_status}}" in all_qq_text) or ("{{qq_guard_status}}" in all_qq_text)
    qq_template_no_push_found = ("{{no_push_status}}" in all_qq_text) or ("OPENCLAW_NO_PUSH" in all_qq_text)

    scan = _scan_text(all_qq_text)
    active_v33_reference_found = scan["active_v33"]
    active_v38_reference_found = scan["active_v38"]
    non_standard_grade_output_found = scan["non_standard"]
    skip_recommendation_found = scan["skip_recommendation"]
    c_main_recommendation_found = scan["c_main"]

    contract_text = _read(ROUTE_SENT_DOC)
    route_sent_distinction_found = bool(
        re.search(r"route.*not.*sent", contract_text, flags=re.IGNORECASE | re.DOTALL)
    ) and ("sent_marker_written=false" in contract_text)

    for doc_ok, code in [
        (qq_guard_doc_exists, "qq_guard_doc_missing"),
        (route_sent_contract_exists, "route_sent_contract_missing"),
        (qq_template_schema_guard_found, "qq_template_schema_guard_missing"),
        (qq_template_guard_status_found, "qq_template_guard_status_missing"),
        (qq_template_no_push_found, "qq_template_no_push_missing"),
        (route_sent_distinction_found, "route_sent_distinction_missing"),
    ]:
        if not doc_ok:
            blockers.append(code)

    if active_v33_reference_found:
        blockers.append("active_v33_reference_found")
    if active_v38_reference_found:
        blockers.append("active_v38_reference_found")
    if non_standard_grade_output_found:
        blockers.append("non_standard_grade_output_found")
    if skip_recommendation_found:
        blockers.append("skip_recommendation_found")
    if c_main_recommendation_found:
        blockers.append("c_main_recommendation_found")

    # Phase constants in this stage
    production_verified = False
    phase_e_allowed = False
    qq_push_allowed = False
    v4_d_allowed_to_generate = True
    v4_d_allowed_to_execute = False

    if blockers:
        check_status = "BLOCKER"
    elif warnings:
        check_status = "WARN"
    else:
        check_status = "PASS"

    out: dict[str, Any] = {
        "schema_version": "v4_qq_guard_check.v1",
        "generated_at": datetime.now(CN).isoformat(),
        "check_status": check_status,
        "qq_guard_doc_exists": qq_guard_doc_exists,
        "route_sent_contract_exists": route_sent_contract_exists,
        "qq_template_schema_guard_found": qq_template_schema_guard_found,
        "qq_template_guard_status_found": qq_template_guard_status_found,
        "qq_template_no_push_found": qq_template_no_push_found,
        "active_v33_reference_found": active_v33_reference_found,
        "active_v38_reference_found": active_v38_reference_found,
        "non_standard_grade_output_found": non_standard_grade_output_found,
        "skip_recommendation_found": skip_recommendation_found,
        "c_main_recommendation_found": c_main_recommendation_found,
        "route_sent_distinction_found": route_sent_distinction_found,
        "production_verified": production_verified,
        "phase_e_allowed": phase_e_allowed,
        "qq_push_allowed": qq_push_allowed,
        "v4_d_allowed_to_generate": v4_d_allowed_to_generate,
        "v4_d_allowed_to_execute": v4_d_allowed_to_execute,
        "blockers": blockers,
        "warnings": warnings,
    }

    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))

    if check_status == "BLOCKER":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
