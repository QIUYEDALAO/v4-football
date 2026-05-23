#!/usr/bin/env python3
"""Repair V4 scout date fields so date/match_date come from kickoff.

This script never deletes files. In apply mode it creates real file backups before
writing repaired JSON. It only changes date-schema fields.
"""
from __future__ import annotations

import argparse
import copy
import glob as glob_mod
import hashlib
import json
import re
import shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "data/runtime/status"
BACKUP_ROOT = ROOT / "data/runtime/backups/v4_scout_date_repair_20260523"
DATE_FIELDS = {
    "date",
    "match_date",
    "scan_date",
    "scout_file_date",
    "kickoff_local",
    "timezone_unknown",
    "date_schema_version",
    "date_repaired",
}
LOCAL_TZ_DEFAULT = timezone(timedelta(hours=8))
FORMAL_RE = re.compile(r"^scout_v4_(\d{8})\.json$")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def tz_from_name(name: str) -> timezone:
    # Asia/Singapore and Asia/Shanghai are both UTC+8 for this project scope.
    if name not in {"Asia/Singapore", "Asia/Shanghai", "UTC+8"}:
        return LOCAL_TZ_DEFAULT
    return LOCAL_TZ_DEFAULT


def normalize_date(raw: Any) -> str | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    if len(text) == 8 and text.isdigit():
        return datetime.strptime(text, "%Y%m%d").date().isoformat()
    return text[:10]


def parse_kickoff(kickoff: Any, tz: timezone) -> tuple[str | None, str | None, bool, str | None]:
    raw = str(kickoff or "").strip()
    if not raw:
        return None, None, False, "missing_kickoff"
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except Exception as exc:
        return None, None, False, f"parse_error:{exc}"
    timezone_unknown = dt.tzinfo is None
    if timezone_unknown:
        dt = dt.replace(tzinfo=tz)
    local = dt.astimezone(tz)
    return local.date().isoformat(), local.isoformat(), timezone_unknown, None


def strip_date_fields(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: strip_date_fields(v) for k, v in obj.items() if k not in DATE_FIELDS}
    if isinstance(obj, list):
        return [strip_date_fields(x) for x in obj]
    return obj


def row_container(data: Any) -> tuple[list[dict], str]:
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)], "list"
    if isinstance(data, dict) and isinstance(data.get("results"), list):
        return [x for x in data["results"] if isinstance(x, dict)], "dict.results"
    return [], "unsupported"


def backup_file(path: Path) -> Path:
    rel = path.relative_to(ROOT)
    target = BACKUP_ROOT / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        shutil.copy2(path, target)
    if target.is_symlink():
        raise RuntimeError(f"backup is symlink: {target}")
    return target


def process_file(path: Path, *, mode: str, tz: timezone) -> dict[str, Any]:
    rel = path.relative_to(ROOT)
    if str(rel).startswith("data/runtime/backups/"):
        return {
            "path": str(rel),
            "formal_scout": False,
            "skipped": True,
            "skip_reason": "backup_not_active_source",
            "rows": 0,
            "bad_date_rows": 0,
            "would_repair_count": 0,
        }
    m = FORMAL_RE.match(path.name)
    if not m:
        return {
            "path": str(rel),
            "formal_scout": False,
            "skipped": True,
            "skip_reason": "non_formal_scout_filename",
            "rows": 0,
            "bad_date_rows": 0,
            "would_repair_count": 0,
        }
    scout_file_date = m.group(1)
    scout_file_date_iso = datetime.strptime(scout_file_date, "%Y%m%d").date().isoformat()
    archive = "data/runtime/archive/" in str(rel)
    before_sha = sha256(path)
    data = load_json(path)
    before_no_date = strip_date_fields(data)
    rows, container = row_container(data)
    bad_rows = 0
    metadata_updates = 0
    ambiguous = []
    timezone_unknown_rows = []
    sample_bad_rows = []
    for idx, rec in enumerate(rows):
        kickoff_date, kickoff_local, tz_unknown, err = parse_kickoff(rec.get("kickoff") or rec.get("kickoff_time"), tz)
        if err or not kickoff_date:
            ambiguous.append({"index": idx, "fixture_id": rec.get("fixture_id"), "error": err})
            continue
        if tz_unknown:
            timezone_unknown_rows.append({"index": idx, "fixture_id": rec.get("fixture_id"), "kickoff": rec.get("kickoff")})
        current_date = normalize_date(rec.get("date"))
        current_match_date = normalize_date(rec.get("match_date"))
        bad = current_date != kickoff_date
        missing_metadata = (
            current_match_date != kickoff_date
            or not rec.get("scan_date")
            or not rec.get("scout_file_date")
            or not rec.get("kickoff_local")
        )
        if bad:
            bad_rows += 1
            if len(sample_bad_rows) < 10:
                sample_bad_rows.append({
                    "path": str(rel),
                    "index": idx,
                    "fixture_id": rec.get("fixture_id"),
                    "date": rec.get("date"),
                    "match_date": rec.get("match_date"),
                    "kickoff": rec.get("kickoff"),
                    "kickoff_date": kickoff_date,
                })
        if bad or missing_metadata:
            metadata_updates += 1
        if mode == "apply" and (bad or missing_metadata):
            original_date = normalize_date(rec.get("date"))
            if rec.get("scan_date"):
                scan_date = normalize_date(rec.get("scan_date"))
            elif original_date and original_date != kickoff_date:
                scan_date = original_date
            else:
                scan_date = scout_file_date_iso
            rec["date"] = kickoff_date
            rec["match_date"] = kickoff_date
            rec["scan_date"] = scan_date
            rec["scout_file_date"] = scout_file_date
            rec["kickoff_local"] = kickoff_local
            rec["timezone_unknown"] = tz_unknown
            rec["date_schema_version"] = "v4_scout_date.v1"
            rec["date_repaired"] = bool(bad)
    after_sha = before_sha
    backup_path = None
    non_date_changed = False
    if mode == "apply" and metadata_updates:
        backup_path = backup_file(path)
        after_no_date = strip_date_fields(data)
        non_date_changed = before_no_date != after_no_date
        if non_date_changed:
            raise RuntimeError(f"non-date field changed before write: {rel}")
        write_json(path, data)
        after_sha = sha256(path)
    return {
        "path": str(rel),
        "formal_scout": True,
        "archive": archive,
        "container": container,
        "rows": len(rows),
        "bad_date_rows": bad_rows,
        "bad_date_rate": round(bad_rows / len(rows) * 100, 1) if rows else 0.0,
        "would_repair_count": bad_rows,
        "metadata_update_rows": metadata_updates,
        "ambiguous_rows": len(ambiguous),
        "timezone_unknown_rows": len(timezone_unknown_rows),
        "ambiguous_samples": ambiguous[:10],
        "timezone_unknown_samples": timezone_unknown_rows[:10],
        "sample_bad_rows": sample_bad_rows,
        "sha256_before": before_sha,
        "sha256_after": after_sha,
        "backup_path": str(backup_path.relative_to(ROOT)) if backup_path else None,
        "non_date_field_changed": non_date_changed,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--glob", required=True)
    parser.add_argument("--mode", choices=["dry-run", "apply"], required=True)
    parser.add_argument("--timezone", default="Asia/Singapore")
    parser.add_argument("--backup", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    if args.mode == "apply" and not args.backup:
        raise SystemExit("BLOCKER: apply requires --backup")
    tz = tz_from_name(args.timezone)
    paths = sorted(Path(p).resolve() for p in glob_mod.glob(str(ROOT / args.glob), recursive=True))
    results = [process_file(p, mode=args.mode, tz=tz) for p in paths if p.is_file()]
    active = [r for r in results if r.get("formal_scout") and not r.get("archive")]
    archive = [r for r in results if r.get("formal_scout") and r.get("archive")]
    skipped = [r for r in results if r.get("skipped")]
    total_rows = sum(int(r.get("rows", 0)) for r in active)
    bad_date_rows = sum(int(r.get("bad_date_rows", 0)) for r in active)
    archive_rows = sum(int(r.get("rows", 0)) for r in archive)
    archive_bad = sum(int(r.get("bad_date_rows", 0)) for r in archive)
    ambiguous_rows = sum(int(r.get("ambiguous_rows", 0)) for r in active + archive)
    timezone_unknown_rows = sum(int(r.get("timezone_unknown_rows", 0)) for r in active + archive)
    non_date_changed = any(bool(r.get("non_date_field_changed")) for r in results)
    out = {
        "phase": "V4-SCOUT-DATE-INTEGRITY-REPAIR-AND-VALIDATION-REBASE-20260523",
        "mode": args.mode,
        "timezone": args.timezone,
        "backup_requested": bool(args.backup),
        "backup_root": str(BACKUP_ROOT.relative_to(ROOT)) if args.mode == "apply" else None,
        "total_files": len(active),
        "archive_files": len(archive),
        "skipped_non_formal_files": skipped,
        "total_rows": total_rows,
        "bad_date_rows": bad_date_rows,
        "bad_date_rate": round(bad_date_rows / total_rows * 100, 1) if total_rows else 0.0,
        "archive_total_rows": archive_rows,
        "archive_bad_date_rows": archive_bad,
        "would_repair_count": bad_date_rows,
        "archive_would_repair_count": archive_bad,
        "ambiguous_rows": ambiguous_rows,
        "timezone_unknown_rows": timezone_unknown_rows,
        "sample_bad_rows": [s for r in active for s in r.get("sample_bad_rows", [])][:10],
        "by_file": results,
        "repaired_files": [r["path"] for r in results if args.mode == "apply" and r.get("metadata_update_rows")],
        "repaired_rows": bad_date_rows if args.mode == "apply" else 0,
        "archive_repaired_rows": archive_bad if args.mode == "apply" else 0,
        "changed_rows": sum(int(r.get("metadata_update_rows", 0)) for r in results) if args.mode == "apply" else 0,
        "non_date_field_changed": non_date_changed,
        "capture_ran": False,
        "QQ_push": False,
        "cloud_publish": False,
        "blockers": [],
    }
    if ambiguous_rows:
        out["blockers"].append("ambiguous_rows_present")
    if timezone_unknown_rows:
        out["blockers"].append("timezone_unknown_rows_present")
    if non_date_changed:
        out["blockers"].append("non_date_field_changed")
    STATUS.mkdir(parents=True, exist_ok=True)
    marker = STATUS / f"v4_scout_date_repair_{args.mode.replace('-', '_')}_20260523.json"
    marker.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    if args.strict and out["blockers"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
