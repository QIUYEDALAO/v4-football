#!/usr/bin/env python3
"""Fail-closed checker for V4 scout date integrity."""
from __future__ import annotations

import glob
import hashlib
import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "data/runtime/status"
FORMAL_RE = re.compile(r"^scout_v4_(\d{8})\.json$")
LOCAL_TZ = timezone(timedelta(hours=8))


def load(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def normalize_date(raw: Any) -> str | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    if len(text) == 8 and text.isdigit():
        return datetime.strptime(text, "%Y%m%d").date().isoformat()
    return text[:10]


def kickoff_date(row: dict) -> tuple[str | None, bool]:
    # Repaired rows carry kickoff_local in the match-local timezone. Historical
    # rows without timezone_source keep the older CST interpretation until a
    # scoped repair phase rewrites them, so this checker remains non-destructive.
    if row.get("timezone_source") and row.get("kickoff_local"):
        local_date = normalize_date(row.get("kickoff_local"))
        return local_date, bool(row.get("timezone_unknown"))
    raw = str(row.get("kickoff") or row.get("kickoff_time") or "").strip()
    if not raw:
        return None, False
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except Exception:
        return None, False
    unknown = dt.tzinfo is None
    if unknown:
        dt = dt.replace(tzinfo=LOCAL_TZ)
    return dt.astimezone(LOCAL_TZ).date().isoformat(), unknown


def rows_for(path: Path) -> list[dict]:
    data = load(path, [])
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict) and isinstance(data.get("results"), list):
        return [x for x in data["results"] if isinstance(x, dict)]
    return []


def main() -> int:
    blockers: list[str] = []
    warnings: list[str] = []
    files = []
    for p in sorted(Path(x).resolve() for x in glob.glob(str(ROOT / "data/**/scout_v4_*.json"), recursive=True)):
        rel = p.relative_to(ROOT)
        if str(rel).startswith("data/runtime/backups/"):
            warnings.append(f"skipped_backup:{rel}")
            continue
        if not FORMAL_RE.match(p.name):
            warnings.append(f"skipped_non_formal:{rel}")
            continue
        files.append(p)
    contaminated = []
    missing_match_date = 0
    missing_scan_date = 0
    missing_scout_file_date = 0
    ambiguous = []
    timezone_unknown = []
    total_rows = 0
    for path in files:
        rel = path.relative_to(ROOT)
        for idx, row in enumerate(rows_for(path)):
            total_rows += 1
            ko_date, tz_unknown = kickoff_date(row)
            if not ko_date:
                ambiguous.append({"path": str(rel), "index": idx, "fixture_id": row.get("fixture_id")})
                continue
            if tz_unknown:
                timezone_unknown.append({"path": str(rel), "index": idx, "fixture_id": row.get("fixture_id")})
            date = normalize_date(row.get("date"))
            match_date = normalize_date(row.get("match_date"))
            if date != ko_date or match_date != ko_date:
                contaminated.append({
                    "path": str(rel),
                    "index": idx,
                    "fixture_id": row.get("fixture_id"),
                    "date": row.get("date"),
                    "match_date": row.get("match_date"),
                    "kickoff": row.get("kickoff"),
                    "kickoff_date": ko_date,
                })
            if not row.get("match_date"):
                missing_match_date += 1
            if not row.get("scan_date"):
                missing_scan_date += 1
            if not row.get("scout_file_date"):
                missing_scout_file_date += 1
    if contaminated:
        blockers.append("contaminated_rows_present")
    if ambiguous:
        blockers.append("ambiguous_rows_present")
    if timezone_unknown:
        blockers.append("timezone_unknown_formal_rows_present")
    if missing_match_date or missing_scan_date or missing_scout_file_date:
        blockers.append("date_schema_fields_missing")

    runner = (ROOT / "engine/v4_runner.py").read_text(encoding="utf-8", errors="replace")
    validator = (ROOT / "engine/v4_ht_result_validator.py").read_text(encoding="utf-8", errors="replace")
    attribution = (ROOT / "engine/v4_result_attribution.py").read_text(encoding="utf-8", errors="replace")
    dashboard_resolver = (ROOT / "tools/v3v4_dashboard_validation_resolver.py").read_text(encoding="utf-8", errors="replace")
    today_resolver = (ROOT / "tools/v4_today_source_resolver.py").read_text(encoding="utf-8", errors="replace")
    scanner_date_uses_kickoff = "_scout_date_fields(fx[\"kickoff\"]" in runner and "match_date" in runner
    validator_uses_match_date = "date_filter_field" in validator and "match_date" in validator and "target_match_date" in validator
    attribution_uses_match_date = "date_filter_field" in attribution and "match_date" in attribution and "target_match_date" in attribution
    dashboard_uses_match_date = "date_filter_field" in dashboard_resolver and "match_date" in dashboard_resolver
    today_resolver_uses_match_date = "m.get(\"match_date\") or m.get(\"date\")" in today_resolver
    for name, ok in {
        "scanner_date_uses_kickoff": scanner_date_uses_kickoff,
        "validator_uses_match_date": validator_uses_match_date,
        "attribution_uses_match_date": attribution_uses_match_date,
        "dashboard_uses_match_date": dashboard_uses_match_date,
        "today_resolver_uses_match_date": today_resolver_uses_match_date,
    }.items():
        if not ok:
            blockers.append(name)

    latest_validation = sorted(STATUS.glob("v3v4_validation_summary_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    validation = load(latest_validation[0], {}) if latest_validation else {}
    c_active = validation.get("c_observation_active") is True
    if c_active:
        blockers.append("c_observation_active_true")
    status = "BLOCKER" if blockers else ("WARN_ONLY" if warnings else "PASS")
    out = {
        "checker": "tools/check_v4_scout_date_integrity.py",
        "phase": "V3V4-DASHBOARD-DYNAMIC-DATE-MARKER-AND-MATCHDATE-TZ-HOTFIX",
        "check_status": status,
        "files_scanned": len(files),
        "total_rows": total_rows,
        "contaminated_rows": len(contaminated),
        "contaminated_row_samples": contaminated[:10],
        "ambiguous_rows": len(ambiguous),
        "timezone_unknown_formal_rows": len(timezone_unknown),
        "missing_match_date": missing_match_date,
        "missing_scan_date": missing_scan_date,
        "missing_scout_file_date": missing_scout_file_date,
        "scanner_date_uses_kickoff": scanner_date_uses_kickoff,
        "validator_uses_match_date": validator_uses_match_date,
        "attribution_uses_match_date": attribution_uses_match_date,
        "dashboard_uses_match_date": dashboard_uses_match_date,
        "today_resolver_uses_match_date": today_resolver_uses_match_date,
        "C_active": c_active,
        "capture_ran": False,
        "QQ_push": False,
        "cloud_publish": False,
        "blockers": blockers,
        "warnings": warnings,
    }
    STATUS.mkdir(parents=True, exist_ok=True)
    marker_date = datetime.now(LOCAL_TZ).strftime("%Y%m%d")
    (STATUS / f"check_v4_scout_date_integrity_result_{marker_date}.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 1 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
