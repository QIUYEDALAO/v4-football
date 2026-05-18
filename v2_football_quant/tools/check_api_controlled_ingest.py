#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
RUNTIME_DIR = BASE_DIR / "data" / "runtime"
CACHE_DIR = RUNTIME_DIR / "cache" / "api_snapshot"
STATUS_DIR = RUNTIME_DIR / "status"
CN_TZ = timezone(timedelta(hours=8))

SCHEMA_VERSION = "controlled_ingest.v1"


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _scan_secret_risk(text: str) -> list[str]:
    findings: list[str] = []
    patterns: list[tuple[str, str]] = [
        ("openai_sk", r"sk-[A-Za-z0-9]{20,}"),
        ("api_key_assignment", r"(?i)api[_-]?key\\s*[:=]\\s*['\"]?[A-Za-z0-9_\\-]{12,}"),
        ("token_assignment", r"(?i)token\\s*[:=]\\s*['\"]?[A-Za-z0-9_\\-]{16,}"),
        ("app_secret_assignment", r"(?i)app[_-]?secret\\s*[:=]\\s*['\"]?[A-Za-z0-9_\\-]{12,}"),
    ]
    for key, pat in patterns:
        if re.search(pat, text):
            findings.append(key)
    return findings


def main() -> None:
    parser = argparse.ArgumentParser(description="Check controlled ingest simulation plan")
    parser.add_argument("--date", required=True, help="YYYYMMDD")
    args = parser.parse_args()

    date_key = args.date.strip().replace("-", "")
    plan_path = CACHE_DIR / date_key / "controlled_ingest_plan.json"
    marker_path = STATUS_DIR / f"api_controlled_ingest_check_{date_key}.json"

    warnings: list[str] = []
    errors: list[str] = []

    if not plan_path.exists():
        errors.append("plan_missing")
        result = {
            "status": "FAIL",
            "schema_valid": False,
            "boundary_valid": False,
            "secret_safe": False,
            "no_api": False,
            "api_called": False,
            "production_dependency": False,
            "production_verified": False,
            "warnings": warnings,
            "errors": errors,
            "date": date_key,
            "plan_path": str(plan_path),
            "generated_at": datetime.now(CN_TZ).isoformat(),
        }
        marker_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        raise SystemExit(1)

    raw = plan_path.read_text(encoding="utf-8")
    plan = _load_json(plan_path, {})

    schema_valid = True
    boundary_valid = True

    if plan.get("schema_version") != SCHEMA_VERSION:
        schema_valid = False
        errors.append("schema_version_invalid")

    if str(plan.get("mode", "")).lower() != "simulation":
        boundary_valid = False
        errors.append("mode_not_simulation")

    runtime_root = str(plan.get("runtime_root", ""))
    expected_runtime = str(RUNTIME_DIR.resolve())
    if runtime_root != expected_runtime:
        boundary_valid = False
        errors.append("runtime_root_not_project_runtime")

    if bool(plan.get("production_dependency", True)):
        boundary_valid = False
        errors.append("production_dependency_not_false")

    boundaries = plan.get("boundaries", {}) if isinstance(plan.get("boundaries", {}), dict) else {}
    no_api = bool(boundaries.get("no_api", False))
    no_push = bool(boundaries.get("no_push", False))
    no_strategy = bool(boundaries.get("no_strategy_recompute", False))
    no_cron = bool(boundaries.get("no_cron", False))
    production_verified = bool(boundaries.get("production_verified", True))

    if not no_api:
        boundary_valid = False
        errors.append("no_api_false")
    if not no_push:
        boundary_valid = False
        errors.append("no_push_false")
    if not no_strategy:
        boundary_valid = False
        errors.append("no_strategy_recompute_false")
    if not no_cron:
        boundary_valid = False
        errors.append("no_cron_false")
    if production_verified:
        boundary_valid = False
        errors.append("production_verified_true")

    targets = plan.get("targets", {}) if isinstance(plan.get("targets", {}), dict) else {}
    if not targets:
        boundary_valid = False
        errors.append("targets_missing")

    api_called = False
    for key, obj in targets.items():
        if not isinstance(obj, dict):
            boundary_valid = False
            errors.append(f"target_{key}_invalid")
            continue
        if bool(obj.get("api_allowed", True)):
            boundary_valid = False
            errors.append(f"target_{key}_api_allowed_true")
        if obj.get("planned_endpoints") and not isinstance(obj.get("planned_endpoints"), list):
            boundary_valid = False
            errors.append(f"target_{key}_planned_endpoints_invalid")

    outputs = plan.get("outputs", {}) if isinstance(plan.get("outputs", {}), dict) else {}
    if bool(outputs.get("would_write_snapshots", False)):
        boundary_valid = False
        errors.append("would_write_snapshots_true")
    if bool(outputs.get("would_update_cache_index", False)):
        boundary_valid = False
        errors.append("would_update_cache_index_true")

    if "sent" in raw.lower() and "marker" in raw.lower():
        warnings.append("text_mentions_sent_marker")

    secret_findings = _scan_secret_risk(raw)
    secret_safe = len(secret_findings) == 0
    if not secret_safe:
        errors.append("secret_pattern_detected")

    if not schema_valid or not boundary_valid or not secret_safe:
        status = "FAIL"
    elif warnings:
        status = "WARN"
    else:
        status = "PASS"

    result = {
        "status": status,
        "schema_valid": schema_valid,
        "boundary_valid": boundary_valid,
        "secret_safe": secret_safe,
        "no_api": no_api,
        "api_called": api_called,
        "production_dependency": False,
        "production_verified": False,
        "warnings": warnings,
        "errors": errors,
        "secret_findings": secret_findings,
        "date": date_key,
        "plan_path": str(plan_path),
        "generated_at": datetime.now(CN_TZ).isoformat(),
    }

    marker_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
