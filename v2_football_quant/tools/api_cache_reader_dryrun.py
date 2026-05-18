#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

try:
    from engine.api_cache_reader import read_cache_summary, validate_cache_read_boundary
except Exception:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from engine.api_cache_reader import read_cache_summary, validate_cache_read_boundary  # type: ignore

BASE_DIR = Path(__file__).resolve().parent.parent
STATUS_DIR = BASE_DIR / "data" / "runtime" / "status"
CN_TZ = timezone(timedelta(hours=8))

SCHEMA_VERSION = "api_cache_reader_dryrun.v1"


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only API cache reader dry-run")
    parser.add_argument("--date", required=True, help="YYYYMMDD")
    args = parser.parse_args()

    date_key = args.date.strip().replace("-", "")
    summary = read_cache_summary(date_key)
    boundary = validate_cache_read_boundary(summary)
    status = boundary.get("status", "FAIL")
    if status == "PASS" and (summary.get("warnings") or boundary.get("warnings")):
        status = "WARN"

    marker = {
        "status": status,
        "schema_version": SCHEMA_VERSION,
        "date": date_key,
        "mode": "read_only",
        "no_api": True,
        "no_key_read": True,
        "no_push": True,
        "no_strategy_recompute": True,
        "no_cron": True,
        "production_dependency": False,
        "production_verified": False,
        "bundle_found": bool((summary.get("available", {}) if isinstance(summary.get("available", {}), dict) else {}).get("bundle", False)),
        "real_ingest_marker_found": bool((summary.get("available", {}) if isinstance(summary.get("available", {}), dict) else {}).get("real_ingest_marker", False)),
        "real_ingest_snapshot_found": bool((summary.get("available", {}) if isinstance(summary.get("available", {}), dict) else {}).get("real_ingest_snapshot", False)),
        "snapshot_count": int(summary.get("snapshot_count", 0) or 0),
        "secret_safe": bool(summary.get("secret_safe", False)),
        "warnings": boundary.get("warnings", []),
        "errors": boundary.get("errors", []),
        "summary": summary,
        "generated_at": datetime.now(CN_TZ).isoformat(),
    }

    out = STATUS_DIR / f"api_cache_reader_dryrun_{date_key}.json"
    out.write_text(json.dumps(marker, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": status, "marker": str(out), "snapshot_count": marker["snapshot_count"]}, ensure_ascii=False, indent=2))

    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()

