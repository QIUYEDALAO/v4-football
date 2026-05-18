#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

try:
    from engine.api_aux_detail import build_aux_detail_report, validate_aux_detail_boundary
except Exception:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from engine.api_aux_detail import build_aux_detail_report, validate_aux_detail_boundary  # type: ignore

BASE_DIR = Path(__file__).resolve().parent.parent
STATUS_DIR = BASE_DIR / "data" / "runtime" / "status"
CN_TZ = timezone(timedelta(hours=8))
SCHEMA_VERSION = "api_aux_detail_dryrun.v1"


def _compute_status(report: dict, boundary: dict) -> str:
    if boundary.get("errors"):
        return "FAIL"

    cards = report.get("detail_cards", []) if isinstance(report.get("detail_cards", []), list) else []
    statuses = [str((c if isinstance(c, dict) else {}).get("status", "MISSING")).upper() for c in cards]
    if any(s == "FAIL" for s in statuses):
        return "FAIL"
    if any(s in {"WARN", "MISSING", "BLOCKER"} for s in statuses):
        return "WARN"
    if boundary.get("warnings") or report.get("warnings"):
        return "WARN"
    return "PASS"


def main() -> None:
    parser = argparse.ArgumentParser(description="API auxiliary detail dry-run")
    parser.add_argument("--date", required=True, help="YYYYMMDD")
    args = parser.parse_args()

    date_key = args.date.strip().replace("-", "")
    report = build_aux_detail_report(date_key)
    boundary = validate_aux_detail_boundary(report)
    status = _compute_status(report, boundary)

    scope = report.get("display_scope", {}) if isinstance(report.get("display_scope", {}), dict) else {}
    cards = report.get("detail_cards", []) if isinstance(report.get("detail_cards", []), list) else []

    marker = {
        "status": status,
        "schema_version": SCHEMA_VERSION,
        "date": date_key,
        "mode": "auxiliary_detail_display",
        "no_api": True,
        "no_key_read": True,
        "no_push": True,
        "no_strategy_recompute": True,
        "no_cron": True,
        "production_dependency": False,
        "production_verified": False,
        "production_path_untouched": True,
        "fallback_to_original_source": True,
        "raw_response_hidden": True,
        "raw_response_visible": False,
        "dashboard_aux_detail_enabled": bool(scope.get("dashboard_aux_detail_enabled", False)),
        "v2_formal_cards_use_cache": bool(scope.get("v2_formal_cards_use_cache", False)),
        "v4_formal_cards_use_cache": bool(scope.get("v4_formal_cards_use_cache", False)),
        "qq_uses_cache": bool(scope.get("qq_uses_cache", False)),
        "detail_cards_count": len(cards),
        "warnings": list(boundary.get("warnings", [])),
        "errors": list(boundary.get("errors", [])),
        "report": report,
        "generated_at": datetime.now(CN_TZ).isoformat(),
    }

    out = STATUS_DIR / f"api_aux_detail_dryrun_{date_key}.json"
    out.write_text(json.dumps(marker, ensure_ascii=False, indent=2), encoding="utf-8")

    print(
        json.dumps(
            {
                "status": status,
                "out": str(out),
                "detail_cards_count": len(cards),
                "raw_response_hidden": marker["raw_response_hidden"],
                "raw_response_visible": marker["raw_response_visible"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
