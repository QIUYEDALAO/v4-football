#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

try:
    from engine.api_shadow_consumer import (
        build_shadow_consumer_report,
        summarize_shadow_status,
        validate_shadow_consumer_boundary,
    )
except Exception:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from engine.api_shadow_consumer import (  # type: ignore
        build_shadow_consumer_report,
        summarize_shadow_status,
        validate_shadow_consumer_boundary,
    )

BASE_DIR = Path(__file__).resolve().parent.parent
STATUS_DIR = BASE_DIR / "data" / "runtime" / "status"
CN_TZ = timezone(timedelta(hours=8))
SCHEMA_VERSION = "api_shadow_consumer_dryrun.v1"


def main() -> None:
    parser = argparse.ArgumentParser(description="Non-critical API cache shadow consumer dry-run")
    parser.add_argument("--date", required=True, help="YYYYMMDD")
    args = parser.parse_args()
    date_key = args.date.strip().replace("-", "")

    report = build_shadow_consumer_report(date_key)
    boundary = validate_shadow_consumer_boundary(report)
    consistency_status = summarize_shadow_status(report)

    status = "PASS"
    if boundary.get("errors"):
        status = "FAIL"
    elif consistency_status == "FAIL":
        status = "FAIL"
    elif consistency_status == "WARN" or boundary.get("warnings") or report.get("warnings"):
        status = "WARN"

    consistency = report.get("consistency", {}) if isinstance(report.get("consistency", {}), dict) else {}

    marker = {
        "status": status,
        "schema_version": SCHEMA_VERSION,
        "date": date_key,
        "mode": "non_critical_shadow",
        "no_api": True,
        "no_key_read": True,
        "no_push": True,
        "no_strategy_recompute": True,
        "no_cron": True,
        "production_dependency": False,
        "production_verified": False,
        "production_path_untouched": True,
        "allowed_consumers": report.get("allowed_consumers", []),
        "blocked_consumers": report.get("blocked_consumers", []),
        "fallback_to_original_source": bool((report.get("boundaries", {}) if isinstance(report.get("boundaries", {}), dict) else {}).get("fallback_to_original_source", False)),
        "threshold": consistency.get("threshold", 1.0),
        "matched": int(consistency.get("matched", 0) or 0),
        "mismatch": int(consistency.get("mismatch", 0) or 0),
        "missing": int(consistency.get("missing", 0) or 0),
        "not_comparable": int(consistency.get("not_comparable", 0) or 0),
        "warnings": list(boundary.get("warnings", [])) + (list(report.get("warnings", [])) if isinstance(report.get("warnings", []), list) else []),
        "errors": list(boundary.get("errors", [])) + (list(report.get("errors", [])) if isinstance(report.get("errors", []), list) else []),
        "report": report,
        "generated_at": datetime.now(CN_TZ).isoformat(),
    }

    out_path = STATUS_DIR / f"api_shadow_consumer_dryrun_{date_key}.json"
    out_path.write_text(json.dumps(marker, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": status,
                "marker": str(out_path),
                "allowed_consumers": marker["allowed_consumers"],
                "blocked_consumers": marker["blocked_consumers"],
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

