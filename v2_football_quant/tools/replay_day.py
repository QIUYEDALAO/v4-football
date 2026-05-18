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
    parser.add_argument("--module", required=False, choices=sorted(ALLOWED_MODULES))
    parser.add_argument("--target", required=False, choices=sorted(ALLOWED_MODULES))
    parser.add_argument("--mode", required=True, choices=sorted(ALLOWED_MODES))
    args = parser.parse_args()

    date_key = args.date.strip().replace("-", "")
    module = args.module or args.target
    if not module:
        raise SystemExit("one of --module/--target is required")
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

    shadow_consumer_path = STATUS_DIR / f"api_shadow_consumer_dryrun_{date_key}.json"
    shadow_consumer = _load_json(shadow_consumer_path, {})
    aux_display_path = STATUS_DIR / f"api_aux_display_dryrun_{date_key}.json"
    aux_display = _load_json(aux_display_path, {})
    aux_detail_path = STATUS_DIR / f"api_aux_detail_dryrun_{date_key}.json"
    aux_detail = _load_json(aux_detail_path, {})
    aux_explain_path = STATUS_DIR / f"api_aux_explain_dryrun_{date_key}.json"
    aux_explain = _load_json(aux_explain_path, {})

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
            "replay_primary_source": "original_artifact",
            "cache_reader_used_as_primary": False,
            "shadow_consumer_visible": shadow_consumer_path.exists(),
            "shadow_consumer_status": str((shadow_consumer.get("status", "MISSING") if isinstance(shadow_consumer, dict) else "MISSING")).upper(),
            "shadow_consumer_marker": str(shadow_consumer_path),
            "aux_display_visible": aux_display_path.exists(),
            "aux_display_status": str((aux_display.get("status", "MISSING") if isinstance(aux_display, dict) else "MISSING")).upper(),
            "aux_display_marker": str(aux_display_path),
            "aux_detail_visible": aux_detail_path.exists(),
            "aux_detail_status": str((aux_detail.get("status", "MISSING") if isinstance(aux_detail, dict) else "MISSING")).upper(),
            "aux_detail_marker": str(aux_detail_path),
            "aux_explain_visible": aux_explain_path.exists(),
            "aux_explain_status": str((aux_explain.get("status", "MISSING") if isinstance(aux_explain, dict) else "MISSING")).upper(),
            "aux_explain_marker": str(aux_explain_path),
            "raw_response_visible": False,
            "production_dependency": False,
        },
        "generated_at": datetime.now(CN_TZ).isoformat(),
    }

    out = STATUS_DIR / f"replay_{date_key}_{module}_{mode}.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "out": str(out), "module": module, "mode": mode}, ensure_ascii=False))


if __name__ == "__main__":
    main()
