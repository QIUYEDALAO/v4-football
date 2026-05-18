#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

try:
    from engine.api_shadow_read import build_shadow_read_report, validate_shadow_boundary
except Exception:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from engine.api_shadow_read import build_shadow_read_report, validate_shadow_boundary  # type: ignore

BASE_DIR = Path(__file__).resolve().parent.parent
STATUS_DIR = BASE_DIR / "data" / "runtime" / "status"
CN_TZ = timezone(timedelta(hours=8))
SCHEMA_VERSION = "api_shadow_read_dryrun.v1"


def main() -> None:
    parser = argparse.ArgumentParser(description="API cache shadow read dry-run")
    parser.add_argument("--date", required=True, help="YYYYMMDD")
    args = parser.parse_args()
    date_key = args.date.strip().replace("-", "")

    report = build_shadow_read_report(date_key)
    boundary = validate_shadow_boundary(report)
    summary = report.get("summary", {}) if isinstance(report.get("summary", {}), dict) else {}
    comparisons = report.get("comparisons", []) if isinstance(report.get("comparisons", []), list) else []
    inputs = report.get("inputs", {}) if isinstance(report.get("inputs", {}), dict) else {}

    status = "PASS"
    if boundary.get("errors"):
        status = "FAIL"
    elif int(summary.get("mismatch", 0) or 0) > 0:
        status = "WARN"
    elif int(summary.get("not_comparable", 0) or 0) > 0:
        status = "WARN"

    marker = {
        "status": status,
        "schema_version": SCHEMA_VERSION,
        "date": date_key,
        "mode": "shadow_read",
        "no_api": True,
        "no_key_read": True,
        "no_push": True,
        "no_strategy_recompute": True,
        "no_cron": True,
        "production_dependency": False,
        "production_verified": False,
        "production_path_untouched": True,
        "reader_summary_found": bool(inputs.get("reader_summary_found", False)),
        "comparison_count": len(comparisons),
        "matched": int(summary.get("matched", 0) or 0),
        "mismatch": int(summary.get("mismatch", 0) or 0),
        "missing": int(summary.get("missing", 0) or 0),
        "not_comparable": int(summary.get("not_comparable", 0) or 0),
        "business_scope": report.get("business_scope", {}),
        "warnings": list(boundary.get("warnings", [])) + (list(report.get("warnings", [])) if isinstance(report.get("warnings", []), list) else []),
        "errors": list(boundary.get("errors", [])) + (list(report.get("errors", [])) if isinstance(report.get("errors", []), list) else []),
        "report": report,
        "generated_at": datetime.now(CN_TZ).isoformat(),
    }

    out_path = STATUS_DIR / f"api_shadow_read_dryrun_{date_key}.json"
    out_path.write_text(json.dumps(marker, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": status,
                "marker": str(out_path),
                "comparison_count": marker["comparison_count"],
                "matched": marker["matched"],
                "mismatch": marker["mismatch"],
                "missing": marker["missing"],
                "not_comparable": marker["not_comparable"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()

