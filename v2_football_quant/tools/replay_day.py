#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent.parent
STATUS_DIR = BASE_DIR / "data" / "runtime" / "status"
LEDGER_DIR = BASE_DIR / "data" / "runtime" / "ledger"
CN_TZ = timezone(timedelta(hours=8))

ALLOWED_MODULES = {"dashboard", "v2", "v4_scan", "v4_review"}
ALLOWED_MODES = {"evidence_only", "dashboard_only", "guard_only", "report_only"}


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay Day v1 (read-only)")
    parser.add_argument("--date", required=True, help="YYYYMMDD")
    parser.add_argument("--module", required=True, choices=sorted(ALLOWED_MODULES))
    parser.add_argument("--mode", required=True, choices=sorted(ALLOWED_MODES))
    args = parser.parse_args()

    date_key = args.date.strip().replace("-", "")
    module = args.module
    mode = args.mode

    ledger_path = LEDGER_DIR / f"{date_key}.json"
    ledger = _load_json(ledger_path, {})

    module_data = {}
    if module == "dashboard":
        module_data = ledger.get("dashboard", {})
    elif module == "v2":
        module_data = ledger.get("v2", {})
    elif module == "v4_scan":
        module_data = ledger.get("v4_scan", {})
    elif module == "v4_review":
        module_data = ledger.get("v4_review", {})

    result = {
        "date": date_key,
        "module": module,
        "mode": mode,
        "no_api": True,
        "no_push": True,
        "no_strategy_recompute": True,
        "no_production_sent": True,
        "no_cron": True,
        "production_verified": False,
        "result": {
            "ledger_exists": ledger_path.exists(),
            "module_data_present": bool(module_data),
            "module_summary_keys": sorted(list(module_data.keys()))[:12] if isinstance(module_data, dict) else [],
        },
        "generated_at": datetime.now(CN_TZ).isoformat(),
    }

    out = STATUS_DIR / f"replay_{date_key}_{module}_{mode}.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "out": str(out), "module": module, "mode": mode}, ensure_ascii=False))


if __name__ == "__main__":
    main()

