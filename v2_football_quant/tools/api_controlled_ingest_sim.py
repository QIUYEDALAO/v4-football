#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

try:
    from engine.api_snapshot_cache import (
        SUPPORTED_MODULES,
        build_controlled_ingest_plan,
        write_controlled_ingest_plan,
    )
except Exception:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from engine.api_snapshot_cache import (  # type: ignore
        SUPPORTED_MODULES,
        build_controlled_ingest_plan,
        write_controlled_ingest_plan,
    )


BASE_DIR = Path(__file__).resolve().parent.parent
STATUS_DIR = BASE_DIR / "data" / "runtime" / "status"
CN_TZ = timezone(timedelta(hours=8))


def main() -> None:
    parser = argparse.ArgumentParser(description="Controlled API ingest simulation (no API)")
    parser.add_argument("--date", required=True, help="YYYYMMDD")
    parser.add_argument("--module", default="all", help="all|v2|v4_scan|v4_review|dashboard|ledger or comma-separated")
    args = parser.parse_args()

    date_key = args.date.strip().replace("-", "")
    if args.module.strip().lower() == "all":
        modules = sorted(SUPPORTED_MODULES)
    else:
        modules = [x.strip() for x in args.module.split(",") if x.strip()]

    plan = build_controlled_ingest_plan(date_key, modules)
    plan_path = write_controlled_ingest_plan(plan)

    status = {
        "status": "PASS",
        "date": date_key,
        "mode": "simulation",
        "no_api": True,
        "api_called": False,
        "api_allowed": False,
        "no_push": True,
        "no_strategy_recompute": True,
        "no_cron": True,
        "production_dependency": False,
        "production_verified": False,
        "result": "controlled ingest simulation generated",
        "plan_path": str(plan_path),
        "modules": modules,
        "generated_at": datetime.now(CN_TZ).isoformat(),
    }
    marker = STATUS_DIR / f"api_controlled_ingest_sim_{date_key}.json"
    marker.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")

    print(
        json.dumps(
            {
                "ok": True,
                "plan": str(plan_path),
                "marker": str(marker),
                "no_api": True,
                "api_called": False,
                "production_verified": False,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
