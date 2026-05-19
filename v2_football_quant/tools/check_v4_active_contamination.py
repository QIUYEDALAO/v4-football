#!/usr/bin/env python3
"""Phase V4-A.1 checker: detect active legacy contamination in V4 formal output paths.

This checker separates:
1) active contamination (must be zero)
2) allowed denylist hits
3) deprecated documentation hits
4) explicit false positives
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

CN = timezone(timedelta(hours=8))
BASE_DIR = Path(__file__).resolve().parent.parent
STATUS_DIR = BASE_DIR / "data" / "runtime" / "status"
OUT_PATH = STATUS_DIR / "v4_active_contamination_check.json"

ALLOWED_GRADES = ["A", "B", "C", "SKIP"]

# Formal output chain files (must be contamination free)
ACTIVE_OUTPUT_FILES = [
    "engine/v4_openclaw_brief.py",
    "engine/v4_review_renderer.py",
    "engine/v4_qq_formatter.py",
    "engine/v4_daily_recommendation_brief.py",
    "engine/v4_review_report.py",
    "templates/v4_daily_review_full_template.md",
    "templates/v4_daily_review_qq_template.md",
    "templates/v4_daily_review_qq_brief.md",
]

RENDERER_OUTPUT_FILES = {
    "engine/v4_review_renderer.py",
    "templates/v4_daily_review_full_template.md",
    "templates/v4_daily_review_qq_template.md",
    "templates/v4_daily_review_qq_brief.md",
}
QQ_BRIEF_FILES = {
    "engine/v4_openclaw_brief.py",
    "engine/v4_qq_formatter.py",
    "templates/v4_daily_review_qq_template.md",
    "templates/v4_daily_review_qq_brief.md",
}
REPORT_TEMPLATE_FILES = {
    "templates/v4_daily_review_full_template.md",
    "templates/v4_daily_review_qq_template.md",
    "templates/v4_daily_review_qq_brief.md",
}

# Allowed contexts
DENYLIST_ALLOWED_FILES = [
    "engine/v4_review_guard.py",
    "engine/v4_scan_and_brief.py",
    "tools/check_v4_boundary_contract.py",
]
DEPRECATED_DOC_FILES = [
    "docs/V4_BOUNDARY_AND_CONTRACT.md",
    "docs/V4_REFACTOR_ROADMAP.md",
    "docs/V4_ACTIVE_CONTAMINATION_INVENTORY.md",
    "docs/V4_ACTIVE_CONTAMINATION_CLOSURE.md",
]
FALSE_POSITIVE_FILES = [
    "config/v4_candidate_rules.yaml",  # STRONG here is pullback enum, not output grade
    "engine/v4_match_intelligence.py",  # STRONG here is internal fit enum, not final grade
    "engine/v4_dashboard.py",  # legacy dashboard tiers are non-formal output in this phase
]

V33_PATTERN = re.compile(r"\bV33\b", flags=re.IGNORECASE)
V38_PATTERN = re.compile(r"\bV38\b", flags=re.IGNORECASE)

NON_STANDARD_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("WATCH", re.compile(r"\bWATCH\b")),
    ("CANDIDATE", re.compile(r"\bCANDIDATE\b")),
    ("S_PLUS", re.compile(r"(?<!\\)\bS\+\b")),
    ("S_GRADE", re.compile(r"\bS级\b")),
    ("D_GRADE", re.compile(r"\bD级\b")),
    ("BET", re.compile(r"\bBET\b")),
    ("STRONG", re.compile(r"\bSTRONG\b")),
    ("MAIN_PUSH", re.compile(r"主推(?!荐)")),
]


@dataclass
class Hit:
    path: str
    line: int
    token: str
    line_text: str


def _read_lines(path: Path) -> list[str]:
    try:
        return path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return []


def _scan_patterns(path: Path, rel: str) -> list[Hit]:
    hits: list[Hit] = []
    lines = _read_lines(path)
    for idx, line in enumerate(lines, 1):
        if V33_PATTERN.search(line):
            hits.append(Hit(rel, idx, "V33", line.strip()))
        if V38_PATTERN.search(line):
            hits.append(Hit(rel, idx, "V38", line.strip()))
        for token, pat in NON_STANDARD_PATTERNS:
            # Ignore checker/regex implementation lines in code files.
            if path.suffix == ".py" and ("re.search(" in line or "NON_STANDARD_PATTERNS" in line):
                continue
            if pat.search(line):
                hits.append(Hit(rel, idx, token, line.strip()))
    return hits


def _scan_files(rel_paths: list[str]) -> tuple[list[Hit], list[str]]:
    out_hits: list[Hit] = []
    missing: list[str] = []
    for rel in rel_paths:
        path = BASE_DIR / rel
        if not path.exists():
            missing.append(rel)
            continue
        out_hits.extend(_scan_patterns(path, rel))
    return out_hits, missing


def _to_dict(hit: Hit) -> dict[str, Any]:
    return {
        "path": hit.path,
        "line": hit.line,
        "token": hit.token,
        "line_text": hit.line_text,
    }


def main() -> None:
    STATUS_DIR.mkdir(parents=True, exist_ok=True)

    blockers: list[str] = []
    warnings: list[str] = []

    active_hits, active_missing = _scan_files(ACTIVE_OUTPUT_FILES)
    denylist_hits, denylist_missing = _scan_files(DENYLIST_ALLOWED_FILES)
    deprecated_hits, deprecated_missing = _scan_files(DEPRECATED_DOC_FILES)
    false_positive_hits, false_positive_missing = _scan_files(FALSE_POSITIVE_FILES)

    # Active contamination classification
    active_v33_hits = [h for h in active_hits if h.token == "V33"]
    active_v38_hits = [h for h in active_hits if h.token == "V38"]
    active_non_standard_hits = [h for h in active_hits if h.token not in {"V33", "V38"}]

    renderer_hits = [h for h in active_hits if h.path in RENDERER_OUTPUT_FILES]
    qq_hits = [h for h in active_hits if h.path in QQ_BRIEF_FILES]
    report_template_hits = [h for h in active_hits if h.path in REPORT_TEMPLATE_FILES]

    active_v33_reference_found = bool(active_v33_hits)
    active_v38_reference_found = bool(active_v38_hits)
    active_non_standard_grade_found = bool(active_non_standard_hits)
    renderer_output_pollution_found = bool(renderer_hits)
    qq_brief_pollution_found = bool(qq_hits)
    report_template_pollution_found = bool(report_template_hits)

    active_contamination_count = len(active_hits)

    if active_missing:
        blockers.append(f"active_files_missing:{len(active_missing)}")

    if active_contamination_count > 0:
        blockers.append("active_contamination_found")

    if active_v33_reference_found:
        blockers.append("active_v33_reference_found")
    if active_v38_reference_found:
        blockers.append("active_v38_reference_found")
    if renderer_output_pollution_found:
        blockers.append("renderer_output_pollution_found")
    if qq_brief_pollution_found:
        blockers.append("qq_brief_pollution_found")
    if report_template_pollution_found:
        blockers.append("report_template_pollution_found")

    # Allowed context reporting only
    if denylist_hits:
        warnings.append("denylist_hits_present")
    if deprecated_hits:
        warnings.append("deprecated_doc_hits_present")
    if false_positive_hits:
        warnings.append("false_positive_hits_present")

    if denylist_missing:
        warnings.append(f"denylist_files_missing:{len(denylist_missing)}")
    if deprecated_missing:
        warnings.append(f"deprecated_doc_files_missing:{len(deprecated_missing)}")
    if false_positive_missing:
        warnings.append(f"false_positive_files_missing:{len(false_positive_missing)}")

    if blockers:
        check_status = "BLOCKER"
    elif warnings:
        check_status = "WARN"
    else:
        check_status = "PASS"

    out: dict[str, Any] = {
        "schema_version": "v4_active_contamination_check.v1",
        "generated_at": datetime.now(CN).isoformat(),
        "check_status": check_status,
        "active_v33_reference_found": active_v33_reference_found,
        "active_v38_reference_found": active_v38_reference_found,
        "active_non_standard_grade_found": active_non_standard_grade_found,
        "renderer_output_pollution_found": renderer_output_pollution_found,
        "qq_brief_pollution_found": qq_brief_pollution_found,
        "report_template_pollution_found": report_template_pollution_found,
        "allowed_denylist_hits": [_to_dict(h) for h in denylist_hits],
        "deprecated_doc_hits": [_to_dict(h) for h in deprecated_hits],
        "false_positive_hits": [_to_dict(h) for h in false_positive_hits],
        "active_contamination_count": active_contamination_count,
        "active_hits": [_to_dict(h) for h in active_hits],
        "allowed_grades": ALLOWED_GRADES,
        "production_verified": False,
        "phase_e_allowed": False,
        "v4_b_allowed_to_generate": True,
        "v4_b_allowed_to_execute": False,
        "active_files_missing": active_missing,
        "warnings": warnings,
        "blockers": blockers,
    }

    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))

    if check_status == "BLOCKER":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
