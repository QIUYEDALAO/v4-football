#!/usr/bin/env python3
"""Phase V4-B checker: validate renderer/template guard contract in formal output path."""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

CN = timezone(timedelta(hours=8))
BASE_DIR = Path(__file__).resolve().parent.parent
STATUS_DIR = BASE_DIR / "data" / "runtime" / "status"
OUT_PATH = STATUS_DIR / "v4_renderer_guard_check.json"

FORMAL_OUTPUT_FILES = [
    "engine/v4_review_renderer.py",
    "engine/v4_qq_formatter.py",
    "engine/v4_openclaw_brief.py",
    "engine/v4_daily_recommendation_brief.py",
    "engine/v4_review_report.py",
    "templates/v4_daily_review_full_template.md",
    "templates/v4_daily_review_qq_template.md",
    "templates/v4_daily_review_qq_brief.md",
]

NON_STANDARD_PATTERNS = [
    ("WATCH", re.compile(r"\bWATCH\b")),
    ("CANDIDATE", re.compile(r"\bCANDIDATE\b")),
    ("S_PLUS", re.compile(r"(?<!\\)\bS\+\b")),
    ("S_GRADE", re.compile(r"\bS级\b")),
    ("D_GRADE", re.compile(r"\bD级\b")),
    ("BET", re.compile(r"\bBET\b")),
    ("STRONG", re.compile(r"\bSTRONG\b")),
    ("MAIN_PUSH", re.compile(r"主推(?!荐)")),
]

V33 = re.compile(r"\bV33\b", flags=re.IGNORECASE)
V38 = re.compile(r"\bV38\b", flags=re.IGNORECASE)

QQ_SEND_PATTERNS = [
    re.compile(r"openclaw\.message\.send", flags=re.IGNORECASE),
    re.compile(r"systemEvent", flags=re.IGNORECASE),
    re.compile(r"qqbot_safe_send", flags=re.IGNORECASE),
    re.compile(r"safe_outbound_sender", flags=re.IGNORECASE),
    re.compile(r"announce\(", flags=re.IGNORECASE),
]


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def _scan_file(rel: str) -> list[dict[str, Any]]:
    path = BASE_DIR / rel
    if not path.exists():
        return [{"path": rel, "line": 0, "token": "FILE_MISSING", "line_text": ""}]

    hits: list[dict[str, Any]] = []
    lines = _read(path).splitlines()

    for idx, line in enumerate(lines, 1):
        if V33.search(line):
            hits.append({"path": rel, "line": idx, "token": "V33", "line_text": line.strip()})
        if V38.search(line):
            hits.append({"path": rel, "line": idx, "token": "V38", "line_text": line.strip()})

        for token, pat in NON_STANDARD_PATTERNS:
            if path.suffix == ".py" and ("re.search(" in line or "_parse_matches(" in line or "NON_STANDARD_PATTERNS" in line):
                continue
            if pat.search(line):
                hits.append({"path": rel, "line": idx, "token": token, "line_text": line.strip()})

        if re.search(r"SKIP.{0,12}(推荐|主推|强推|投注)|(推荐|主推|强推|投注).{0,12}SKIP", line, flags=re.IGNORECASE):
            if "SKIP is not recommendation" not in line and "不得" not in line:
                hits.append({"path": rel, "line": idx, "token": "SKIP_RECOMMENDATION", "line_text": line.strip()})

        if re.search(r"C级.{0,12}(主推|强推|重注|必选)|(主推|强推|重注|必选).{0,12}C级", line):
            if "不得" not in line:
                hits.append({"path": rel, "line": idx, "token": "C_MAIN_RECOMMENDATION", "line_text": line.strip()})

        for pat in QQ_SEND_PATTERNS:
            if pat.search(line):
                hits.append({"path": rel, "line": idx, "token": "QQ_SEND_CALL", "line_text": line.strip()})

    return hits


def main() -> None:
    STATUS_DIR.mkdir(parents=True, exist_ok=True)

    blockers: list[str] = []
    warnings: list[str] = []

    all_hits: list[dict[str, Any]] = []
    for rel in FORMAL_OUTPUT_FILES:
        all_hits.extend(_scan_file(rel))

    active_v33_reference_found = any(h["token"] == "V33" for h in all_hits)
    active_v38_reference_found = any(h["token"] == "V38" for h in all_hits)
    non_standard_grade_output_found = any(
        h["token"] in {"WATCH", "CANDIDATE", "S_PLUS", "S_GRADE", "D_GRADE", "BET", "STRONG", "MAIN_PUSH"}
        for h in all_hits
    )
    skip_recommendation_found = any(h["token"] == "SKIP_RECOMMENDATION" for h in all_hits)
    c_main_recommendation_found = any(h["token"] == "C_MAIN_RECOMMENDATION" for h in all_hits)
    qq_send_call_found = any(h["token"] == "QQ_SEND_CALL" for h in all_hits)

    renderer_text = _read(BASE_DIR / "engine/v4_review_renderer.py")
    renderer_grade_guard_found = (
        "ALLOWED_GRADES" in renderer_text
        and "_validate_structured_payload" in renderer_text
    )

    template_schema_guard_found = True
    for rel in (
        "templates/v4_daily_review_full_template.md",
        "templates/v4_daily_review_qq_template.md",
        "templates/v4_daily_review_qq_brief.md",
    ):
        text = _read(BASE_DIR / rel)
        if "{{schema_guard_status}}" not in text:
            template_schema_guard_found = False
            warnings.append(f"template_schema_guard_missing:{rel}")

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
    if qq_send_call_found:
        blockers.append("qq_send_call_found")
    if not renderer_grade_guard_found:
        blockers.append("renderer_grade_guard_missing")
    if not template_schema_guard_found:
        blockers.append("template_schema_guard_missing")

    check_status = "BLOCKER" if blockers else ("WARN" if warnings else "PASS")

    out: dict[str, Any] = {
        "schema_version": "v4_renderer_guard_check.v1",
        "generated_at": datetime.now(CN).isoformat(),
        "check_status": check_status,
        "formal_output_files_scanned": FORMAL_OUTPUT_FILES,
        "active_v33_reference_found": active_v33_reference_found,
        "active_v38_reference_found": active_v38_reference_found,
        "non_standard_grade_output_found": non_standard_grade_output_found,
        "skip_recommendation_found": skip_recommendation_found,
        "c_main_recommendation_found": c_main_recommendation_found,
        "renderer_grade_guard_found": renderer_grade_guard_found,
        "template_schema_guard_found": template_schema_guard_found,
        "qq_send_call_found": qq_send_call_found,
        "production_verified": False,
        "phase_e_allowed": False,
        "qq_push_allowed": False,
        "v4_c_allowed_to_generate": True,
        "v4_c_allowed_to_execute": False,
        "hits": all_hits,
        "blockers": blockers,
        "warnings": warnings,
    }

    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))

    if check_status == "BLOCKER":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
