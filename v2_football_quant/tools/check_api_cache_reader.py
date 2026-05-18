#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
STATUS_DIR = BASE_DIR / "data" / "runtime" / "status"
CN_TZ = timezone(timedelta(hours=8))

DRYRUN_SCHEMA = "api_cache_reader_dryrun.v1"

SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"(?i)x-apisports-key\\s*[:=]\\s*['\"]?[A-Za-z0-9_\\-]{8,}"),
    re.compile(r"(?i)apifootball[_-]?key\\s*[:=]\\s*['\"]?[A-Za-z0-9_\\-]{8,}"),
    re.compile(r"(?i)token\\s*[:=]\\s*['\"]?[A-Za-z0-9_\\-]{16,}"),
    re.compile(r"(?i)secret\\s*[:=]\\s*['\"]?[A-Za-z0-9_\\-]{10,}"),
]


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _scan_secret(text: str) -> list[str]:
    out: list[str] = []
    for idx, pat in enumerate(SECRET_PATTERNS):
        if pat.search(text):
            out.append(f"pattern_{idx}")
    return out


def _source_code_checks() -> tuple[bool, list[str]]:
    reader_path = BASE_DIR / "engine" / "api_cache_reader.py"
    if not reader_path.exists():
        return False, ["reader_source_missing"]
    text = reader_path.read_text(encoding="utf-8", errors="replace")
    findings: list[str] = []
    banned_net = ["requests.", "httpx.", "urllib.request", "urlopen(", "socket."]
    for token in banned_net:
        if token in text:
            findings.append(f"network_call_token:{token}")
    banned_key = ["APIFOOTBALL_KEY", "OPENCLAW_APIFOOTBALL_KEY", "os.environ"]
    for token in banned_key:
        if token in text:
            findings.append(f"key_read_token:{token}")
    return (len(findings) == 0), findings


def main() -> None:
    parser = argparse.ArgumentParser(description="Check read-only API cache reader dry-run marker")
    parser.add_argument("--date", required=True, help="YYYYMMDD")
    args = parser.parse_args()

    date_key = args.date.strip().replace("-", "")
    dryrun_path = STATUS_DIR / f"api_cache_reader_dryrun_{date_key}.json"
    out_path = STATUS_DIR / f"api_cache_reader_check_{date_key}.json"

    warnings: list[str] = []
    errors: list[str] = []

    if not dryrun_path.exists():
        result = {
            "status": "BLOCKER",
            "schema_valid": False,
            "boundary_valid": False,
            "secret_safe": False,
            "no_api": True,
            "no_key_read": True,
            "production_dependency": False,
            "production_verified": False,
            "warnings": warnings,
            "errors": ["reader_dryrun_marker_missing"],
            "date": date_key,
            "generated_at": datetime.now(CN_TZ).isoformat(),
        }
        out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        raise SystemExit(2)

    marker = _load_json(dryrun_path, {})
    schema_valid = str(marker.get("schema_version", "")) == DRYRUN_SCHEMA

    boundary_valid = True
    if str(marker.get("mode", "")).lower() != "read_only":
        boundary_valid = False
        errors.append("mode_invalid")
    for k in ["no_api", "no_key_read", "no_push", "no_strategy_recompute", "no_cron"]:
        if not bool(marker.get(k, False)):
            boundary_valid = False
            errors.append(f"{k}_false")
    if bool(marker.get("production_dependency", True)):
        boundary_valid = False
        errors.append("production_dependency_not_false")
    if bool(marker.get("production_verified", True)):
        boundary_valid = False
        errors.append("production_verified_not_false")

    summary = marker.get("summary", {}) if isinstance(marker.get("summary", {}), dict) else {}
    snap_rows = summary.get("snapshots", []) if isinstance(summary.get("snapshots", []), list) else []
    snapshot_count = int(marker.get("snapshot_count", 0) or 0)
    if snapshot_count != len(snap_rows):
        boundary_valid = False
        errors.append("snapshot_count_mismatch")

    secret_safe = bool(marker.get("secret_safe", False))
    secret_findings: list[str] = []
    secret_findings.extend(_scan_secret(json.dumps(marker, ensure_ascii=False)))
    for row in snap_rows:
        p = Path(str((row if isinstance(row, dict) else {}).get("path", "")))
        if p.exists() and p.is_file():
            s = p.read_text(encoding="utf-8", errors="replace")
            f = _scan_secret(s)
            if f:
                secret_findings.extend([f"snapshot:{p.name}:{x}" for x in f])
    if secret_findings:
        secret_safe = False
        errors.append("secret_pattern_detected")

    source_ok, source_findings = _source_code_checks()
    if not source_ok:
        boundary_valid = False
        errors.extend(source_findings)

    if not schema_valid:
        errors.append("schema_invalid")

    status = "PASS"
    if not schema_valid or not boundary_valid or not secret_safe:
        status = "FAIL"
    elif marker.get("warnings") or warnings:
        status = "WARN"

    result = {
        "status": status,
        "schema_valid": schema_valid,
        "boundary_valid": boundary_valid,
        "secret_safe": secret_safe,
        "no_api": True,
        "no_key_read": True,
        "production_dependency": False,
        "production_verified": False,
        "warnings": warnings + (marker.get("warnings", []) if isinstance(marker.get("warnings", []), list) else []),
        "errors": errors,
        "secret_findings": sorted(set(secret_findings)),
        "date": date_key,
        "generated_at": datetime.now(CN_TZ).isoformat(),
    }
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
