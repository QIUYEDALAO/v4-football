#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
RUNTIME_DIR = BASE_DIR / "data" / "runtime"
STATUS_DIR = RUNTIME_DIR / "status"

SCHEMA_VERSION = "api_shadow_consumer.v1"

ALLOWED_CONSUMERS = ["dashboard", "replay", "audit"]
BLOCKED_CONSUMERS = [
    "v2_daily_pool",
    "v2_window_checker",
    "v2_settlement",
    "v4_scan",
    "v4_review",
    "qq_sender",
    "production_report_router",
]


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def list_allowed_consumers() -> list[str]:
    return list(ALLOWED_CONSUMERS)


def is_consumer_allowed(name: str) -> bool:
    return str(name).strip() in ALLOWED_CONSUMERS


def evaluate_consumer_consistency(date_key: str) -> dict[str, Any]:
    clean = str(date_key).strip().replace("-", "")
    shadow_path = STATUS_DIR / f"api_shadow_read_dryrun_{clean}.json"
    shadow = _load_json(shadow_path, {})
    threshold = 1.0

    matched = int(shadow.get("matched", 0) or 0) if isinstance(shadow, dict) else 0
    mismatch = int(shadow.get("mismatch", 0) or 0) if isinstance(shadow, dict) else 0
    missing = int(shadow.get("missing", 0) or 0) if isinstance(shadow, dict) else 0
    not_comparable = int(shadow.get("not_comparable", 0) or 0) if isinstance(shadow, dict) else 0
    compared = matched + mismatch

    status = "PASS"
    if mismatch > 0:
        status = "FAIL"
    elif compared == 0 or missing > 0 or not_comparable > 0:
        status = "WARN"
    # threshold=1.0 means compared rows must be all matched to keep PASS.
    if compared > 0:
        ratio = matched / float(compared)
        if ratio < threshold:
            status = "FAIL"

    return {
        "threshold": threshold,
        "matched": matched,
        "mismatch": mismatch,
        "missing": missing,
        "not_comparable": not_comparable,
        "status": status,
        "shadow_read_marker_found": shadow_path.exists(),
    }


def build_shadow_consumer_report(date_key: str) -> dict[str, Any]:
    clean = str(date_key).strip().replace("-", "")
    consistency = evaluate_consumer_consistency(clean)

    consumers = {
        c: {
            "enabled": True,
            "mode": "shadow",
            "fallback_enabled": True,
            "cache_read_allowed": True,
            "production_dependency": False,
        }
        for c in ALLOWED_CONSUMERS
    }

    report = {
        "schema_version": SCHEMA_VERSION,
        "date": clean,
        "mode": "non_critical_shadow",
        "runtime_root": str(RUNTIME_DIR),
        "production_dependency": False,
        "production_verified": False,
        "allowed_consumers": list_allowed_consumers(),
        "blocked_consumers": list(BLOCKED_CONSUMERS),
        "boundaries": {
            "no_api": True,
            "no_key_read": True,
            "no_push": True,
            "no_strategy_recompute": True,
            "no_cron": True,
            "production_path_untouched": True,
            "fallback_to_original_source": True,
        },
        "consumers": consumers,
        "consistency": consistency,
        "business_scope": {
            "v2_production_compared": False,
            "v4_production_compared": False,
            "reason": "C7 only enables non-critical shadow consumers; production links remain forbidden",
        },
        "warnings": [],
        "errors": [],
    }
    if not consistency.get("shadow_read_marker_found", False):
        report["warnings"].append("shadow_read_baseline_missing")
    if consistency.get("status") == "WARN":
        report["warnings"].append("consistency_not_full_pass")
    if consistency.get("status") == "FAIL":
        report["errors"].append("consistency_failed")
    return report


def summarize_shadow_status(report: dict[str, Any]) -> str:
    if not isinstance(report, dict):
        return "FAIL"
    c = report.get("consistency", {}) if isinstance(report.get("consistency", {}), dict) else {}
    return str(c.get("status", "FAIL")).upper()


def validate_shadow_consumer_boundary(report: dict[str, Any]) -> dict[str, Any]:
    warnings: list[str] = []
    errors: list[str] = []

    if str(report.get("schema_version", "")) != SCHEMA_VERSION:
        errors.append("schema_version_invalid")
    if str(report.get("mode", "")) != "non_critical_shadow":
        errors.append("mode_invalid")
    if bool(report.get("production_dependency", True)):
        errors.append("production_dependency_not_false")
    if bool(report.get("production_verified", True)):
        errors.append("production_verified_not_false")

    b = report.get("boundaries", {}) if isinstance(report.get("boundaries", {}), dict) else {}
    for k in (
        "no_api",
        "no_key_read",
        "no_push",
        "no_strategy_recompute",
        "no_cron",
        "production_path_untouched",
        "fallback_to_original_source",
    ):
        if not bool(b.get(k, False)):
            errors.append(f"{k}_false")

    allowed = report.get("allowed_consumers", []) if isinstance(report.get("allowed_consumers", []), list) else []
    blocked = report.get("blocked_consumers", []) if isinstance(report.get("blocked_consumers", []), list) else []
    if sorted(allowed) != sorted(ALLOWED_CONSUMERS):
        errors.append("allowed_consumers_invalid")
    for x in [
        "v2_daily_pool",
        "v2_window_checker",
        "v2_settlement",
        "v4_scan",
        "v4_review",
        "qq_sender",
    ]:
        if x not in blocked:
            errors.append(f"blocked_consumer_missing:{x}")

    scope = report.get("business_scope", {}) if isinstance(report.get("business_scope", {}), dict) else {}
    if bool(scope.get("v2_production_compared", True)):
        errors.append("v2_production_compared_not_false")
    if bool(scope.get("v4_production_compared", True)):
        errors.append("v4_production_compared_not_false")

    if str((report.get("consistency", {}) if isinstance(report.get("consistency", {}), dict) else {}).get("status", "WARN")).upper() == "WARN":
        warnings.append("consistency_warn")

    return {"status": "PASS" if not errors else "FAIL", "warnings": warnings, "errors": errors}

