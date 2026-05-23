#!/usr/bin/env python3
"""Phase D.8.24 checker — validate controlled worker dry-run wrapper output."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

CN = timezone(timedelta(hours=8))
STATUS_DIR = Path(__file__).resolve().parent.parent / "data" / "runtime" / "status"
SCHEMA_VERSION = "v2_controlled_worker_dryrun_wrapper_check.v1"


def _load(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _bool(v: Any, default: bool = False) -> bool:
    if isinstance(v, bool):
        return v
    return default


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=False)
    parser.add_argument("--window", default="midday")
    args = parser.parse_args()

    date_key = args.date or datetime.now(CN).strftime("%Y%m%d")
    window = args.window

    p = STATUS_DIR / f"v2_controlled_worker_dryrun_wrapper_{date_key}_{window}.json"
    d = _load(p)

    errors: list[str] = []
    warnings: list[str] = []

    if not d:
        errors.append("WRAPPER_MARKER_MISSING")
    else:
        if str(d.get("wrapper_mode", "")) != "dry_run_only":
            errors.append("WRAPPER_MODE_INVALID")
        if not _bool(d.get("dry_run_only"), False):
            errors.append("DRY_RUN_ONLY_FALSE")
        if not _bool(d.get("sandbox_or_synthetic_path_only"), False):
            errors.append("SANDBOX_OR_SYNTHETIC_SCOPE_FALSE")

        gp = d.get("guard_presence", {}) if isinstance(d.get("guard_presence"), dict) else {}
        for g in (
            "dry_run_only",
            "openclaw_no_push",
            "no_supervisor",
            "no_push",
            "no_cron",
            "no_verified_write",
            "no_formal_state_write",
        ):
            if not _bool(gp.get(g), False):
                errors.append(f"GUARD_MISSING:{g}")

        for field in (
            "pipeline_ready",
            "production_verified",
            "execution_performed",
            "production_resume_executed",
            "formal_daily_pool_executed",
            "supervisor_executed",
            "live_worker_executed",
            "cron_modified",
            "qq_sent",
            "verified_written",
            "formal_state_written",
            "api_called",
            "key_read",
        ):
            if _bool(d.get(field), False):
                errors.append(f"FIELD_TRUE_FORBIDDEN:{field}")

        pg = d.get("production_gates", {}) if isinstance(d.get("production_gates"), dict) else {}
        for field in (
            "production_resume_allowed_now",
            "cron_enable_allowed",
            "qq_push_allowed",
            "verified_write_allowed",
            "state_write_allowed",
        ):
            if _bool(pg.get(field), False):
                errors.append(f"PRODUCTION_GATE_LEAK:{field}")

        d825 = d.get("d825_draft", {}) if isinstance(d.get("d825_draft"), dict) else {}
        if not _bool(d825.get("allowed_to_generate"), False):
            errors.append("D825_ALLOWED_TO_GENERATE_FALSE")
        if _bool(d825.get("allowed_to_execute"), True):
            errors.append("D825_ALLOWED_TO_EXECUTE_TRUE")

    status = "PASS"
    if errors:
        status = "BLOCKER" if any(e.startswith("FIELD_TRUE_FORBIDDEN:pipeline_ready") or e.startswith("FIELD_TRUE_FORBIDDEN:production_verified") for e in errors) else "FAIL"
    elif warnings:
        status = "WARN"

    out = {
        "schema_version": SCHEMA_VERSION,
        "date": date_key,
        "window": window,
        "dryrun_wrapper_check_status": status,
        "source_marker": str(p),
        "execution_performed": False,
        "production_resume_executed": False,
        "production_resume_allowed_now": False,
        "cron_enable_allowed": False,
        "qq_push_allowed": False,
        "verified_write_allowed": False,
        "state_write_allowed": False,
        "pipeline_ready": False,
        "production_verified": False,
        "errors": errors,
        "warnings": warnings,
        "generated_at": datetime.now(CN).isoformat(),
    }

    out_path = STATUS_DIR / f"v2_controlled_worker_dryrun_wrapper_check_{date_key}_{window}.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))

    if status in {"FAIL", "BLOCKER"}:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
