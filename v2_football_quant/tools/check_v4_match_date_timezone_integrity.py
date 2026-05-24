#!/usr/bin/env python3
"""Check V4 match_date uses match-local timezone semantics for current scout."""
from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "data/runtime/status"
REPORTS = ROOT / "data/daily_reports"
TZ = timezone(timedelta(hours=8))
DATE = datetime.now(TZ).strftime("%Y%m%d")


def load(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def norm(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    return text[:10]


def main() -> int:
    blockers: list[str] = []
    warnings: list[str] = []
    path = REPORTS / f"scout_v4_{DATE}.json"
    rows = load(path, [])
    if not isinstance(rows, list):
        rows = []
    timezone_unknown_rows = []
    ambiguous_rows = []
    cst_truncation_risk_rows = []
    checked = 0
    for idx, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        checked += 1
        match_date = norm(row.get("match_date") or row.get("date"))
        kickoff_local_date = norm(row.get("kickoff_local"))
        tz_source = row.get("timezone_source")
        if not match_date or not kickoff_local_date:
            ambiguous_rows.append({"index": idx, "fixture_id": row.get("fixture_id"), "reason": "missing match_date or kickoff_local"})
            continue
        if row.get("timezone_unknown") is True:
            timezone_unknown_rows.append({"index": idx, "fixture_id": row.get("fixture_id"), "timezone_source": tz_source})
        if match_date != kickoff_local_date:
            cst_truncation_risk_rows.append({"index": idx, "fixture_id": row.get("fixture_id"), "match_date": match_date, "kickoff_local": row.get("kickoff_local"), "timezone_source": tz_source})
        if not tz_source:
            timezone_unknown_rows.append({"index": idx, "fixture_id": row.get("fixture_id"), "timezone_source": None})
    if ambiguous_rows:
        blockers.append("ambiguous_match_date_rows")
    if timezone_unknown_rows:
        blockers.append("timezone_unknown_rows_present")
    if cst_truncation_risk_rows:
        blockers.append("match_date_not_equal_match_local_date")
    runner = (ROOT / "engine/v4_runner.py").read_text(encoding="utf-8", errors="replace")
    if "operator_timezone_fallback" not in runner or "timezone_source" not in runner:
        blockers.append("runner_timezone_source_guard_missing")
    out = {
        "checker":"tools/check_v4_match_date_timezone_integrity.py",
        "phase":"V3V4-DASHBOARD-DYNAMIC-DATE-MARKER-AND-MATCHDATE-TZ-HOTFIX",
        "generated_at":datetime.now(TZ).isoformat(),
        "date":DATE,
        "check_status":"BLOCKER" if blockers else ("WARN_ONLY" if warnings else "PASS"),
        "match_date_definition":"match-local calendar date from kickoff_local/timezone_source",
        "scan_date_role":"audit_only",
        "rows_checked":checked,
        "timezone_unknown_rows":len(timezone_unknown_rows),
        "ambiguous_rows":len(ambiguous_rows),
        "cst_truncation_risk_rows":len(cst_truncation_risk_rows),
        "timezone_unknown_samples":timezone_unknown_rows[:10],
        "ambiguous_samples":ambiguous_rows[:10],
        "cst_truncation_samples":cst_truncation_risk_rows[:10],
        "scan_date_used_for_validation":False,
        "blockers":blockers,
        "warnings":warnings,
    }
    STATUS.mkdir(parents=True, exist_ok=True)
    (STATUS / f"check_v4_match_date_timezone_integrity_result_{DATE}.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 1 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
