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

SCHEMA_VERSION = "api_snapshot_cache.v1"


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
    parser = argparse.ArgumentParser(description="Check API snapshot/cache dry-run bundle integrity")
    parser.add_argument("--date", required=True, help="YYYYMMDD")
    args = parser.parse_args()

    date_key = args.date.strip().replace("-", "")
    bundle_path = CACHE_DIR / date_key / "bundle.json"
    marker_path = STATUS_DIR / f"api_snapshot_cache_check_{date_key}.json"

    errors: list[str] = []
    warnings: list[str] = []

    if not bundle_path.exists():
        errors.append("bundle_missing")
        result = {
            "status": "FAIL",
            "schema_valid": False,
            "integrity_valid": False,
            "secret_safe": False,
            "no_api": False,
            "production_dependency": False,
            "production_verified": False,
            "warnings": warnings,
            "errors": errors,
            "date": date_key,
            "bundle_path": str(bundle_path),
            "generated_at": datetime.now(CN_TZ).isoformat(),
        }
        marker_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        raise SystemExit(1)

    raw_text = bundle_path.read_text(encoding="utf-8")
    bundle = _load_json(bundle_path, {})

    schema_valid = True
    integrity_valid = True

    if bundle.get("schema_version") != SCHEMA_VERSION:
        schema_valid = False
        errors.append("schema_version_invalid")

    if str(bundle.get("mode", "")).lower() != "dry_run":
        integrity_valid = False
        errors.append("mode_not_dry_run")

    expected_runtime = str(RUNTIME_DIR.resolve())
    runtime_root = str(bundle.get("runtime_root", ""))
    if runtime_root != expected_runtime:
        integrity_valid = False
        errors.append("runtime_root_not_project_runtime")

    if bool(bundle.get("production_dependency", True)):
        integrity_valid = False
        errors.append("production_dependency_not_false")

    boundaries = bundle.get("boundaries", {}) if isinstance(bundle.get("boundaries", {}), dict) else {}
    no_api = bool(boundaries.get("no_api", False))
    no_push = bool(boundaries.get("no_push", False))
    no_strategy = bool(boundaries.get("no_strategy_recompute", False))
    no_cron = bool(boundaries.get("no_cron", False))
    production_verified = bool(boundaries.get("production_verified", True))

    if not no_api:
        integrity_valid = False
        errors.append("no_api_false")
    if not no_push:
        integrity_valid = False
        errors.append("no_push_false")
    if not no_strategy:
        integrity_valid = False
        errors.append("no_strategy_recompute_false")
    if not no_cron:
        integrity_valid = False
        errors.append("no_cron_false")
    if production_verified:
        integrity_valid = False
        errors.append("production_verified_true")

    modules = bundle.get("modules", {}) if isinstance(bundle.get("modules", {}), dict) else {}
    if not modules:
        integrity_valid = False
        errors.append("modules_missing")

    snapshots = bundle.get("snapshots", []) if isinstance(bundle.get("snapshots", []), list) else []
    expected_snapshot_len = 0
    for mod_name, mod_obj in modules.items():
        if not isinstance(mod_obj, dict):
            integrity_valid = False
            errors.append(f"module_{mod_name}_invalid")
            continue
        if bool(mod_obj.get("api_called", True)):
            integrity_valid = False
            errors.append(f"module_{mod_name}_api_called_true")
        sc = mod_obj.get("snapshot_count", 0)
        if not isinstance(sc, int):
            integrity_valid = False
            errors.append(f"module_{mod_name}_snapshot_count_non_int")
            sc = 0
        expected_snapshot_len += sc

    if expected_snapshot_len != len(snapshots):
        integrity_valid = False
        errors.append("snapshot_count_mismatch")

    secret_findings = _scan_secret_risk(raw_text)
    secret_safe = len(secret_findings) == 0
    if not secret_safe:
        errors.append("secret_pattern_detected")

    # soft warnings
    if bundle.get("safety") is None:
        warnings.append("legacy_safety_block_missing")
    if bundle.get("path_mismatch_warnings"):
        warnings.append("path_mismatch_detected")

    if not schema_valid or not integrity_valid or not secret_safe:
        status = "FAIL"
    elif warnings:
        status = "WARN"
    else:
        status = "PASS"

    result = {
        "status": status,
        "schema_valid": schema_valid,
        "integrity_valid": integrity_valid,
        "secret_safe": secret_safe,
        "no_api": no_api,
        "production_dependency": False,
        "production_verified": False,
        "warnings": warnings,
        "errors": errors,
        "secret_findings": secret_findings,
        "date": date_key,
        "bundle_path": str(bundle_path),
        "generated_at": datetime.now(CN_TZ).isoformat(),
    }

    marker_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
