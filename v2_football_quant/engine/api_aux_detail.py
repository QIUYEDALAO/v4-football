#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
RUNTIME_DIR = BASE_DIR / "data" / "runtime"
STATUS_DIR = RUNTIME_DIR / "status"

SCHEMA_VERSION = "api_aux_detail.v1"


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _status_of(obj: Any, default: str = "MISSING") -> str:
    if isinstance(obj, dict):
        return str(obj.get("status", default)).upper()
    return str(default).upper()


def _card_status(*statuses: str) -> str:
    values = [str(s or "MISSING").upper() for s in statuses]
    if any(v == "FAIL" for v in values):
        return "FAIL"
    if any(v == "WARN" for v in values):
        return "WARN"
    if any(v == "BLOCKER" for v in values):
        return "FAIL"
    if any(v == "MISSING" for v in values):
        return "MISSING"
    return "PASS"


def summarize_real_ingest_detail(date_key: str) -> dict[str, Any]:
    clean = str(date_key).strip().replace("-", "")
    marker_path = STATUS_DIR / f"api_controlled_ingest_real_{clean}.json"
    check_path = STATUS_DIR / f"api_real_ingest_check_{clean}.json"
    marker = _load_json(marker_path, {})
    check = _load_json(check_path, {})

    req = marker.get("request", {}) if isinstance(marker.get("request", {}), dict) else {}
    res = marker.get("response", {}) if isinstance(marker.get("response", {}), dict) else {}
    safety = marker.get("safety", {}) if isinstance(marker.get("safety", {}), dict) else {}

    snapshot_path = Path(str(res.get("raw_snapshot_path", ""))).expanduser() if res.get("raw_snapshot_path") else None
    snapshot_size = 0
    if snapshot_path and snapshot_path.exists() and snapshot_path.is_file():
        snapshot_size = snapshot_path.stat().st_size

    status = _card_status(_status_of(marker), _status_of(check))

    return {
        "status": status,
        "fields": {
            "endpoint": str(req.get("endpoint_name", "status")),
            "http_status": str(res.get("http_status", "缺失")),
            "request_count": int(req.get("request_count", 0) or 0),
            "timeout_seconds": int(req.get("timeout_seconds", 0) or 0),
            "retry_count": int(req.get("retry_count", 0) or 0),
            "duration_ms": int(res.get("duration_ms", 0) or 0),
            "snapshot_size_bytes": int(snapshot_size),
            "secret_safe": bool(check.get("secret_safe", False)) if isinstance(check, dict) else bool(safety.get("secret_safe", False)),
        },
        "raw_response_hidden": True,
        "evidence_collapsed": True,
        "found": marker_path.exists(),
        "check_found": check_path.exists(),
    }


def summarize_reader_detail(date_key: str) -> dict[str, Any]:
    clean = str(date_key).strip().replace("-", "")
    dryrun_path = STATUS_DIR / f"api_cache_reader_dryrun_{clean}.json"
    check_path = STATUS_DIR / f"api_cache_reader_check_{clean}.json"
    dryrun = _load_json(dryrun_path, {})
    check = _load_json(check_path, {})
    status = _card_status(_status_of(dryrun), _status_of(check))

    return {
        "status": status,
        "fields": {
            "bundle_found": bool(dryrun.get("bundle_found", False)) if isinstance(dryrun, dict) else False,
            "snapshot_count": int(dryrun.get("snapshot_count", 0) or 0) if isinstance(dryrun, dict) else 0,
            "real_ingest_snapshot_found": bool(dryrun.get("real_ingest_snapshot_found", False)) if isinstance(dryrun, dict) else False,
            "secret_safe": bool(check.get("secret_safe", False)) if isinstance(check, dict) else False,
        },
        "raw_response_hidden": True,
        "evidence_collapsed": True,
        "found": dryrun_path.exists(),
        "check_found": check_path.exists(),
    }


def summarize_shadow_detail(date_key: str) -> dict[str, Any]:
    clean = str(date_key).strip().replace("-", "")
    dryrun_path = STATUS_DIR / f"api_shadow_read_dryrun_{clean}.json"
    check_path = STATUS_DIR / f"api_shadow_read_check_{clean}.json"
    dryrun = _load_json(dryrun_path, {})
    check = _load_json(check_path, {})
    status = _card_status(_status_of(dryrun), _status_of(check))

    scope = dryrun.get("business_scope", {}) if isinstance(dryrun.get("business_scope", {}), dict) else {}

    return {
        "status": status,
        "fields": {
            "comparison_count": int(dryrun.get("comparison_count", 0) or 0) if isinstance(dryrun, dict) else 0,
            "matched": int(dryrun.get("matched", 0) or 0) if isinstance(dryrun, dict) else 0,
            "mismatch": int(dryrun.get("mismatch", 0) or 0) if isinstance(dryrun, dict) else 0,
            "missing": int(dryrun.get("missing", 0) or 0) if isinstance(dryrun, dict) else 0,
            "not_comparable": int(dryrun.get("not_comparable", 0) or 0) if isinstance(dryrun, dict) else 0,
            "v2_production_compared": bool(scope.get("v2_production_compared", False)),
            "v4_production_compared": bool(scope.get("v4_production_compared", False)),
        },
        "raw_response_hidden": True,
        "evidence_collapsed": True,
        "found": dryrun_path.exists(),
        "check_found": check_path.exists(),
    }


def build_api_cache_detail_cards(date_key: str) -> list[dict[str, Any]]:
    real = summarize_real_ingest_detail(date_key)
    reader = summarize_reader_detail(date_key)
    shadow = summarize_shadow_detail(date_key)

    return [
        {
            "id": "real_ingest_detail",
            "title": "真实API烟雾详情",
            "label": "辅助详情，不作生产证据",
            "status": real["status"],
            "fields": real["fields"],
            "raw_response_hidden": True,
            "evidence_collapsed": True,
        },
        {
            "id": "reader_detail",
            "title": "Cache Reader详情",
            "label": "辅助详情，不作生产证据",
            "status": reader["status"],
            "fields": reader["fields"],
            "raw_response_hidden": True,
            "evidence_collapsed": True,
        },
        {
            "id": "shadow_detail",
            "title": "旁路对账详情",
            "label": "辅助详情，不作生产证据",
            "status": shadow["status"],
            "fields": shadow["fields"],
            "raw_response_hidden": True,
            "evidence_collapsed": True,
        },
    ]


def build_aux_detail_report(date_key: str) -> dict[str, Any]:
    clean = str(date_key).strip().replace("-", "")
    cards = build_api_cache_detail_cards(clean)

    warnings: list[str] = []
    errors: list[str] = []

    if any(str(c.get("status", "")).upper() == "MISSING" for c in cards if isinstance(c, dict)):
        warnings.append("detail_source_partial_missing")
    if any(str(c.get("status", "")).upper() == "FAIL" for c in cards if isinstance(c, dict)):
        warnings.append("detail_checker_not_full_pass")

    report = {
        "schema_version": SCHEMA_VERSION,
        "date": clean,
        "mode": "auxiliary_detail_display",
        "runtime_root": str(RUNTIME_DIR),
        "production_dependency": False,
        "production_verified": False,
        "boundaries": {
            "no_api": True,
            "no_key_read": True,
            "no_push": True,
            "no_strategy_recompute": True,
            "no_cron": True,
            "production_path_untouched": True,
            "fallback_to_original_source": True,
            "raw_response_hidden": True,
        },
        "display_scope": {
            "dashboard_aux_detail_enabled": True,
            "v2_formal_cards_use_cache": False,
            "v4_formal_cards_use_cache": False,
            "qq_uses_cache": False,
            "raw_response_visible": False,
        },
        "detail_cards": cards,
        "warnings": warnings,
        "errors": errors,
    }
    return report


def _has_forbidden_response_key(obj: Any) -> bool:
    forbidden = {"raw_response", "response_body", "body", "full_response"}
    if isinstance(obj, dict):
        for k, v in obj.items():
            if str(k).lower() in forbidden:
                return True
            if _has_forbidden_response_key(v):
                return True
    elif isinstance(obj, list):
        for x in obj:
            if _has_forbidden_response_key(x):
                return True
    return False


def validate_aux_detail_boundary(report: dict[str, Any]) -> dict[str, Any]:
    warnings: list[str] = []
    errors: list[str] = []

    if str(report.get("schema_version", "")) != SCHEMA_VERSION:
        errors.append("schema_version_invalid")
    if str(report.get("mode", "")) != "auxiliary_detail_display":
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
        "raw_response_hidden",
    ):
        if not bool(b.get(k, False)):
            errors.append(f"{k}_false")

    scope = report.get("display_scope", {}) if isinstance(report.get("display_scope", {}), dict) else {}
    if not bool(scope.get("dashboard_aux_detail_enabled", False)):
        errors.append("dashboard_aux_detail_disabled")
    if bool(scope.get("v2_formal_cards_use_cache", True)):
        errors.append("v2_formal_cards_use_cache_not_false")
    if bool(scope.get("v4_formal_cards_use_cache", True)):
        errors.append("v4_formal_cards_use_cache_not_false")
    if bool(scope.get("qq_uses_cache", True)):
        errors.append("qq_uses_cache_not_false")
    if bool(scope.get("raw_response_visible", True)):
        errors.append("raw_response_visible_not_false")

    cards = report.get("detail_cards", []) if isinstance(report.get("detail_cards", []), list) else []
    if not cards:
        warnings.append("detail_cards_missing")

    for card in cards:
        if not isinstance(card, dict):
            errors.append("detail_card_invalid")
            continue
        label = str(card.get("label", ""))
        if ("辅助详情" not in label) and ("不作生产证据" not in label) and ("非生产证据" not in label):
            errors.append(f"detail_card_label_invalid:{card.get('id', 'unknown')}")
        if _has_forbidden_response_key(card):
            errors.append(f"detail_card_has_forbidden_response_field:{card.get('id', 'unknown')}")
        if bool(card.get("raw_response_hidden", False)) is False:
            errors.append(f"detail_card_raw_response_hidden_false:{card.get('id', 'unknown')}")

    return {
        "status": "PASS" if not errors else "FAIL",
        "warnings": warnings + (report.get("warnings", []) if isinstance(report.get("warnings", []), list) else []),
        "errors": errors + (report.get("errors", []) if isinstance(report.get("errors", []), list) else []),
    }
