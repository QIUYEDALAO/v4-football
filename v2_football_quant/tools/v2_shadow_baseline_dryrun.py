#!/usr/bin/env python3
"""Phase D.2 — V2 Shadow Baseline Dry-Run (read-only, no production impact)."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from engine.v2_shadow_baseline import build_v2_shadow_baseline

BASE_DIR = Path(__file__).resolve().parent.parent
STATUS_DIR = BASE_DIR / "data" / "runtime" / "status"
CN_TZ = timezone(timedelta(hours=8))


def main() -> None:
    parser = argparse.ArgumentParser(description="V2 Shadow Baseline Dry-Run")
    parser.add_argument("--date", required=False, default=None, help="YYYYMMDD (default: today)")
    args = parser.parse_args()
    date_key = args.date or datetime.now(CN_TZ).strftime("%Y%m%d")

    report = build_v2_shadow_baseline(date_key)
    summary = report.get("summary", {})

    marker = {
        "schema_version": "v2_shadow_baseline_dryrun.v1",
        "date": date_key,
        "status": summary.get("overall_status", "UNKNOWN"),
        "generated_at": datetime.now(CN_TZ).isoformat(),
        "production_dependency": False,
        "production_verified": False,
        "formal_v2_uses_cache": False,
        "shadow_affects_formal": False,
        "no_api": True,
        "no_key_read": True,
        "no_push": True,
        "no_cron": True,
        "no_task_trigger": True,
        "no_bet_locked_write": True,
        "no_settlement_write": True,
        "overall_status": summary,
        "report": report,
    }

    out_path = STATUS_DIR / f"v2_shadow_baseline_{date_key}.json"
    out_path.write_text(json.dumps(marker, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({
        "ok": summary.get("overall_status") != "FAIL",
        "status": summary.get("overall_status"),
        "marker": str(out_path),
        "pass": summary.get("pass_count"),
        "warn": summary.get("warn_count"),
        "fail": summary.get("fail_count"),
        "missing": summary.get("missing_count"),
    }, ensure_ascii=False, indent=2))

    if summary.get("overall_status") == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
