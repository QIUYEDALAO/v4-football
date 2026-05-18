#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

try:
    from engine.api_snapshot_cache import (
        SUPPORTED_MODULES,
        build_snapshot_bundle,
        write_snapshot_bundle,
    )
except Exception:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from engine.api_snapshot_cache import (  # type: ignore
        SUPPORTED_MODULES,
        build_snapshot_bundle,
        write_snapshot_bundle,
    )


BASE_DIR = Path(__file__).resolve().parent.parent
STATUS_DIR = BASE_DIR / "data" / "runtime" / "status"
CN_TZ = timezone(timedelta(hours=8))


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase C API Snapshot / Cache dry-run (read-only)")
    parser.add_argument("--date", required=True, help="YYYYMMDD")
    parser.add_argument("--module", default="all", help="all|v2|v4_scan|v4_review|dashboard|ledger or comma-separated")
    parser.add_argument("--check", action="store_true", help="run local cache checker after dry-run")
    args = parser.parse_args()

    date_key = args.date.strip().replace("-", "")
    if args.module.strip().lower() == "all":
        modules = sorted(SUPPORTED_MODULES)
    else:
        modules = [x.strip() for x in args.module.split(",") if x.strip()]

    bundle = build_snapshot_bundle(date_key, modules)
    out = write_snapshot_bundle(bundle)

    status = {
        "date": date_key,
        "phase": "Phase_C_Framework_DryRun",
        "status": "CODE_READY",
        "bundle_path": str(out),
        "modules": modules,
        "no_api": True,
        "no_push": True,
        "no_strategy_recompute": True,
        "no_cron": True,
        "production_verified": False,
        "generated_at": datetime.now(CN_TZ).isoformat(),
    }
    marker = STATUS_DIR / f"api_snapshot_cache_dryrun_{date_key}.json"
    marker.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")

    payload = {
        "ok": True,
        "bundle": str(out),
        "marker": str(marker),
        "module_count": len(modules),
        "no_api": True,
        "no_push": True,
        "production_verified": False,
    }

    if args.check:
        checker_cmd = [sys.executable, str(BASE_DIR / "tools" / "check_api_snapshot_cache.py"), "--date", date_key]
        cp = subprocess.run(checker_cmd, cwd=str(BASE_DIR), capture_output=True, text=True)
        payload["check_executed"] = True
        payload["check_returncode"] = cp.returncode
        try:
            payload["check_result"] = json.loads(cp.stdout) if cp.stdout.strip() else {}
        except Exception:
            payload["check_stdout"] = cp.stdout[-2000:]
        if cp.returncode != 0:
            payload["ok"] = False
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            raise SystemExit(cp.returncode)

    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
