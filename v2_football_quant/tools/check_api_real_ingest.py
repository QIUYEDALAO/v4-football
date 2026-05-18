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
STATUS_DIR = RUNTIME_DIR / "status"
REAL_DIR = RUNTIME_DIR / "cache" / "api_snapshot"
CN_TZ = timezone(timedelta(hours=8))

SCHEMA_VERSION = "real_ingest.v1"


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _secret_findings(text: str) -> list[str]:
    pats = [
        ("openai_sk", r"sk-[A-Za-z0-9]{20,}"),
        ("api_key_like", r"(?i)(api[_-]?key|x-apisports-key)\\s*[:=]\\s*['\"]?[A-Za-z0-9_\\-]{10,}"),
        ("token_like", r"(?i)token\\s*[:=]\\s*['\"]?[A-Za-z0-9_\\-]{16,}"),
        ("secret_like", r"(?i)secret\\s*[:=]\\s*['\"]?[A-Za-z0-9_\\-]{10,}"),
    ]
    out = []
    for name, pat in pats:
        if re.search(pat, text):
            out.append(name)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Check controlled real ingest smoke result")
    parser.add_argument("--date", required=True, help="YYYYMMDD")
    args = parser.parse_args()

    date_key = args.date.strip().replace("-", "")
    marker_path = STATUS_DIR / f"api_controlled_ingest_real_{date_key}.json"
    out_marker = STATUS_DIR / f"api_real_ingest_check_{date_key}.json"

    warnings: list[str] = []
    errors: list[str] = []

    if not marker_path.exists():
        result = {
            "status": "BLOCKER",
            "schema_valid": False,
            "boundary_valid": False,
            "secret_safe": False,
            "request_count_valid": False,
            "no_api": False,
            "api_called": False,
            "production_dependency": False,
            "production_verified": False,
            "warnings": warnings,
            "errors": ["real_ingest_marker_missing"],
            "date": date_key,
            "generated_at": datetime.now(CN_TZ).isoformat(),
        }
        out_marker.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        raise SystemExit(2)

    marker = _load_json(marker_path, {})

    # Safe blocker path: missing key or endpoint blocked should pass as BLOCKER-compliant.
    if str(marker.get("status", "")).upper() == "BLOCKER":
        result = {
            "status": "BLOCKER",
            "schema_valid": bool(marker.get("schema_version") == SCHEMA_VERSION),
            "boundary_valid": True,
            "secret_safe": True,
            "request_count_valid": True,
            "no_api": False,
            "api_called": False,
            "production_dependency": False,
            "production_verified": False,
            "warnings": ["real_ingest_blocked_before_request"],
            "errors": marker.get("errors", []),
            "date": date_key,
            "generated_at": datetime.now(CN_TZ).isoformat(),
        }
        out_marker.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        raise SystemExit(2)

    schema_valid = marker.get("schema_version") == SCHEMA_VERSION
    boundary_valid = True

    if str(marker.get("mode", "")).lower() != "controlled_real_smoke":
        boundary_valid = False
        errors.append("mode_invalid")

    if bool(marker.get("production_dependency", True)):
        boundary_valid = False
        errors.append("production_dependency_not_false")
    if bool(marker.get("production_verified", True)):
        boundary_valid = False
        errors.append("production_verified_not_false")

    b = marker.get("boundaries", {}) if isinstance(marker.get("boundaries", {}), dict) else {}
    if int(b.get("max_requests", 0) or 0) != 1:
        boundary_valid = False
        errors.append("max_requests_not_1")
    if not bool(b.get("no_push", False)):
        boundary_valid = False
        errors.append("no_push_false")
    if not bool(b.get("no_strategy_recompute", False)):
        boundary_valid = False
        errors.append("no_strategy_recompute_false")
    if not bool(b.get("no_cron", False)):
        boundary_valid = False
        errors.append("no_cron_false")

    req = marker.get("request", {}) if isinstance(marker.get("request", {}), dict) else {}
    request_count = int(req.get("request_count") if req.get("request_count") is not None else 0)
    retry_count = int(req.get("retry_count") if req.get("retry_count") is not None else -1)
    timeout_seconds = int(req.get("timeout_seconds") if req.get("timeout_seconds") is not None else 999)
    request_count_valid = request_count <= 1 and retry_count == 0 and timeout_seconds <= 10
    if not request_count_valid:
        boundary_valid = False
        errors.append("request_guard_invalid")

    # API called only if request_count==1
    api_called = request_count == 1

    raw_path = marker.get("response", {}).get("raw_snapshot_path") if isinstance(marker.get("response", {}), dict) else None
    raw_exists = bool(raw_path and Path(raw_path).exists())
    if api_called and not raw_exists:
        boundary_valid = False
        errors.append("raw_snapshot_missing")

    secret_safe = True
    findings: list[str] = []
    marker_text = json.dumps(marker, ensure_ascii=False)
    findings.extend(_secret_findings(marker_text))

    if raw_exists:
        raw_text = Path(raw_path).read_text(encoding="utf-8", errors="replace")
        findings.extend(_secret_findings(raw_text))

    if findings:
        secret_safe = False
        errors.append("secret_pattern_detected")

    status = "PASS"
    if not schema_valid or not boundary_valid or not secret_safe:
        status = "FAIL"
    if status == "PASS" and marker.get("warnings"):
        warnings.append("ingest_runtime_warnings_present")
        status = "WARN"

    result = {
        "status": status,
        "schema_valid": schema_valid,
        "boundary_valid": boundary_valid,
        "secret_safe": secret_safe,
        "request_count_valid": request_count_valid,
        "no_api": False,
        "api_called": api_called,
        "production_dependency": False,
        "production_verified": False,
        "warnings": warnings,
        "errors": errors,
        "secret_findings": sorted(set(findings)),
        "raw_snapshot_exists": raw_exists,
        "date": date_key,
        "generated_at": datetime.now(CN_TZ).isoformat(),
    }

    out_marker.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
