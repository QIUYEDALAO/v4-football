#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

try:
    from engine.api_cache_health import build_api_cache_health_summary, validate_api_cache_health_boundary
except Exception:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from engine.api_cache_health import build_api_cache_health_summary, validate_api_cache_health_boundary  # type: ignore

BASE_DIR = Path(__file__).resolve().parent.parent
STATUS_DIR = BASE_DIR / "data" / "runtime" / "status"
CN_TZ = timezone(timedelta(hours=8))
SCHEMA_VERSION = "api_cache_health_summary.v1"


def main() -> None:
    parser = argparse.ArgumentParser(description="API cache health daily summary")
    parser.add_argument("--date", required=True, help="YYYYMMDD")
    args = parser.parse_args()

    date_key = args.date.strip().replace("-", "")
    summary = build_api_cache_health_summary(date_key)
    boundary = validate_api_cache_health_boundary(summary)

    status = str(summary.get("summary", {}).get("overall_status", "WARN")).upper()
    if boundary.get("errors"):
        status = "FAIL"

    b = summary.get("boundaries", {}) if isinstance(summary.get("boundaries", {}), dict) else {}
    s = summary.get("summary", {}) if isinstance(summary.get("summary", {}), dict) else {}
    safety = summary.get("safety", {}) if isinstance(summary.get("safety", {}), dict) else {}

    marker = {
        "status": status,
        "schema_version": SCHEMA_VERSION,
        "date": date_key,
        "mode": "daily_health_summary",
        "no_api": bool(b.get("no_api", False)),
        "no_key_read": bool(b.get("no_key_read", False)),
        "no_push": bool(b.get("no_push", False)),
        "no_strategy_recompute": bool(b.get("no_strategy_recompute", False)),
        "no_cron": bool(b.get("no_cron", False)),
        "production_dependency": False,
        "production_verified": False,
        "production_path_untouched": bool(b.get("production_path_untouched", False)),
        "formal_v2_uses_cache": bool(b.get("formal_v2_uses_cache", False)),
        "formal_v4_uses_cache": bool(b.get("formal_v4_uses_cache", False)),
        "qq_uses_cache": bool(b.get("qq_uses_cache", False)),
        "raw_response_visible": bool(b.get("raw_response_visible", False)),
        "secret_safe": bool(safety.get("secret_safe", False)),
        "overall_status": str(s.get("overall_status", "WARN")),
        "pass_count": int(s.get("pass_count", 0) or 0),
        "warn_count": int(s.get("warn_count", 0) or 0),
        "fail_count": int(s.get("fail_count", 0) or 0),
        "missing_count": int(s.get("missing_count", 0) or 0),
        "blocker_count": int(s.get("blocker_count", 0) or 0),
        "warnings": list(boundary.get("warnings", [])) + (summary.get("warnings", []) if isinstance(summary.get("warnings", []), list) else []),
        "errors": list(boundary.get("errors", [])) + (summary.get("errors", []) if isinstance(summary.get("errors", []), list) else []),
        "summary": summary,
        "generated_at": datetime.now(CN_TZ).isoformat(),
    }

    out = STATUS_DIR / f"api_cache_health_summary_{date_key}.json"
    out.write_text(json.dumps(marker, ensure_ascii=False, indent=2), encoding="utf-8")

    print(
        json.dumps(
            {
                "status": marker["status"],
                "out": str(out),
                "overall_status": marker["overall_status"],
                "pass_count": marker["pass_count"],
                "warn_count": marker["warn_count"],
                "fail_count": marker["fail_count"],
                "missing_count": marker["missing_count"],
                "blocker_count": marker["blocker_count"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    if marker["status"] in {"FAIL", "BLOCKER"}:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
