#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

try:
    from engine.api_aux_display import build_aux_display_report, validate_aux_display_boundary
except Exception:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from engine.api_aux_display import build_aux_display_report, validate_aux_display_boundary  # type: ignore

BASE_DIR = Path(__file__).resolve().parent.parent
STATUS_DIR = BASE_DIR / "data" / "runtime" / "status"
CN_TZ = timezone(timedelta(hours=8))
SCHEMA_VERSION = "api_aux_display_dryrun.v1"


def _compute_status(report: dict, boundary: dict) -> str:
    if boundary.get("errors"):
        return "FAIL"
    card_statuses = []
    cards = report.get("cards", []) if isinstance(report.get("cards", []), list) else []
    for c in cards:
        if isinstance(c, dict):
            card_statuses.append(str(c.get("status", "MISSING")).upper())
    if any(s == "FAIL" for s in card_statuses):
        return "FAIL"
    if any(s in {"WARN", "MISSING", "BLOCKER"} for s in card_statuses):
        return "WARN"
    if boundary.get("warnings") or report.get("warnings"):
        return "WARN"
    return "PASS"


def main() -> None:
    parser = argparse.ArgumentParser(description="API auxiliary display dry-run")
    parser.add_argument("--date", required=True, help="YYYYMMDD")
    args = parser.parse_args()

    date_key = args.date.strip().replace("-", "")
    report = build_aux_display_report(date_key)
    boundary = validate_aux_display_boundary(report)
    status = _compute_status(report, boundary)

    scope = report.get("display_scope", {}) if isinstance(report.get("display_scope", {}), dict) else {}
    cards = report.get("cards", []) if isinstance(report.get("cards", []), list) else []

    marker = {
        "status": status,
        "schema_version": SCHEMA_VERSION,
        "date": date_key,
        "mode": "auxiliary_display",
        "no_api": True,
        "no_key_read": True,
        "no_push": True,
        "no_strategy_recompute": True,
        "no_cron": True,
        "production_dependency": False,
        "production_verified": False,
        "production_path_untouched": True,
        "fallback_to_original_source": True,
        "dashboard_aux_enabled": bool(scope.get("dashboard_aux_enabled", False)),
        "replay_aux_visible": bool(scope.get("replay_aux_visible", False)),
        "audit_aux_visible": bool(scope.get("audit_aux_visible", False)),
        "v2_formal_cards_use_cache": bool(scope.get("v2_formal_cards_use_cache", False)),
        "v4_formal_cards_use_cache": bool(scope.get("v4_formal_cards_use_cache", False)),
        "qq_uses_cache": bool(scope.get("qq_uses_cache", False)),
        "cards_count": len(cards),
        "warnings": list(boundary.get("warnings", [])),
        "errors": list(boundary.get("errors", [])),
        "report": report,
        "generated_at": datetime.now(CN_TZ).isoformat(),
    }

    out = STATUS_DIR / f"api_aux_display_dryrun_{date_key}.json"
    out.write_text(json.dumps(marker, ensure_ascii=False, indent=2), encoding="utf-8")

    print(
        json.dumps(
            {
                "status": status,
                "out": str(out),
                "cards_count": len(cards),
                "dashboard_aux_enabled": marker["dashboard_aux_enabled"],
                "replay_aux_visible": marker["replay_aux_visible"],
                "audit_aux_visible": marker["audit_aux_visible"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
