#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
RUNTIME_DIR = BASE_DIR / "data" / "runtime"
STATUS_DIR = RUNTIME_DIR / "status"

SCHEMA_VERSION = "api_aux_display.v1"


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
    if any(v in {"MISSING", "BLOCKER"} for v in values):
        return "MISSING"
    return "PASS"


def _bool_false(v: Any) -> bool:
    return bool(v) is False


def build_aux_display_report(date_key: str) -> dict[str, Any]:
    clean = str(date_key).strip().replace("-", "")

    reader_dryrun_path = STATUS_DIR / f"api_cache_reader_dryrun_{clean}.json"
    reader_check_path = STATUS_DIR / f"api_cache_reader_check_{clean}.json"
    shadow_consumer_dryrun_path = STATUS_DIR / f"api_shadow_consumer_dryrun_{clean}.json"
    shadow_consumer_check_path = STATUS_DIR / f"api_shadow_consumer_check_{clean}.json"
    real_ingest_path = STATUS_DIR / f"api_controlled_ingest_real_{clean}.json"
    real_ingest_check_path = STATUS_DIR / f"api_real_ingest_check_{clean}.json"
    gray_check_path = STATUS_DIR / f"dashboard_api_cache_gray_check_{clean}.json"

    reader_dryrun = _load_json(reader_dryrun_path, {})
    reader_check = _load_json(reader_check_path, {})
    shadow_consumer_dryrun = _load_json(shadow_consumer_dryrun_path, {})
    shadow_consumer_check = _load_json(shadow_consumer_check_path, {})
    real_ingest = _load_json(real_ingest_path, {})
    real_ingest_check = _load_json(real_ingest_check_path, {})
    gray_check = _load_json(gray_check_path, {})

    reader_status = _card_status(_status_of(reader_dryrun), _status_of(reader_check), _status_of(gray_check))
    real_status = _card_status(_status_of(real_ingest), _status_of(real_ingest_check))
    consumer_status = _card_status(_status_of(shadow_consumer_dryrun), _status_of(shadow_consumer_check))
    real_req = real_ingest.get("request", {}) if isinstance(real_ingest.get("request", {}), dict) else {}

    cards = [
        {
            "id": "api_cache_health",
            "title": "API缓存健康",
            "label": "辅助展示，不作生产证据",
            "status": reader_status,
            "summary": f"Reader={_status_of(reader_dryrun)} / Checker={_status_of(reader_check)} / GrayPage={_status_of(gray_check)}",
            "evidence_collapsed": True,
        },
        {
            "id": "real_ingest_smoke",
            "title": "真实API烟雾测试",
            "label": "辅助展示，不作生产证据",
            "status": real_status,
            "summary": f"endpoint={str(real_req.get('endpoint_name', 'status'))} / request_count={int(real_req.get('request_count', 0) or 0)}",
            "evidence_collapsed": True,
        },
        {
            "id": "shadow_consumer",
            "title": "旁路消费者",
            "label": "仅dashboard/replay/audit，正式链路禁用",
            "status": consumer_status,
            "summary": f"allowed={','.join(shadow_consumer_dryrun.get('allowed_consumers', [])) if isinstance(shadow_consumer_dryrun.get('allowed_consumers', []), list) else 'missing'}",
            "evidence_collapsed": True,
        },
    ]

    warnings: list[str] = []
    errors: list[str] = []

    if not reader_dryrun_path.exists():
        warnings.append("reader_dryrun_missing")
    if not reader_check_path.exists():
        warnings.append("reader_check_missing")
    if not shadow_consumer_dryrun_path.exists():
        warnings.append("shadow_consumer_dryrun_missing")
    if not shadow_consumer_check_path.exists():
        warnings.append("shadow_consumer_check_missing")
    if not real_ingest_path.exists():
        warnings.append("real_ingest_marker_missing")
    if not real_ingest_check_path.exists():
        warnings.append("real_ingest_check_missing")

    display_scope = {
        "dashboard_aux_enabled": True,
        "replay_aux_visible": True,
        "audit_aux_visible": True,
        "v2_formal_cards_use_cache": False,
        "v4_formal_cards_use_cache": False,
        "qq_uses_cache": False,
    }

    report = {
        "schema_version": SCHEMA_VERSION,
        "date": clean,
        "mode": "auxiliary_display",
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
        },
        "display_scope": display_scope,
        "cards": cards,
        "inputs": {
            "reader_dryrun_found": reader_dryrun_path.exists(),
            "reader_check_found": reader_check_path.exists(),
            "shadow_consumer_dryrun_found": shadow_consumer_dryrun_path.exists(),
            "shadow_consumer_check_found": shadow_consumer_check_path.exists(),
            "real_ingest_found": real_ingest_path.exists(),
            "real_ingest_check_found": real_ingest_check_path.exists(),
            "gray_check_found": gray_check_path.exists(),
        },
        "warnings": warnings,
        "errors": errors,
    }
    return report


def build_dashboard_aux_cards(date_key: str) -> list[dict[str, Any]]:
    report = build_aux_display_report(date_key)
    cards = report.get("cards", []) if isinstance(report.get("cards", []), list) else []
    return [c for c in cards if isinstance(c, dict)]


def build_replay_aux_status(date_key: str) -> dict[str, Any]:
    report = build_aux_display_report(date_key)
    cards = report.get("cards", []) if isinstance(report.get("cards", []), list) else []
    statuses = [str((c if isinstance(c, dict) else {}).get("status", "MISSING")).upper() for c in cards]

    status = "PASS"
    if any(s == "FAIL" for s in statuses):
        status = "FAIL"
    elif any(s in {"WARN", "MISSING"} for s in statuses):
        status = "WARN"

    return {
        "status": status,
        "cards_count": len(cards),
        "production_dependency": False,
        "production_verified": False,
        "cache_reader_used_as_primary": False,
        "aux_display_visible": True,
    }


def validate_aux_display_boundary(report: dict[str, Any]) -> dict[str, Any]:
    warnings: list[str] = []
    errors: list[str] = []

    if str(report.get("schema_version", "")) != SCHEMA_VERSION:
        errors.append("schema_version_invalid")
    if str(report.get("mode", "")) != "auxiliary_display":
        errors.append("mode_invalid")

    if not _bool_false(report.get("production_dependency", True)):
        errors.append("production_dependency_not_false")
    if not _bool_false(report.get("production_verified", True)):
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

    scope = report.get("display_scope", {}) if isinstance(report.get("display_scope", {}), dict) else {}
    if not bool(scope.get("dashboard_aux_enabled", False)):
        errors.append("dashboard_aux_disabled")
    if not bool(scope.get("replay_aux_visible", False)):
        errors.append("replay_aux_not_visible")
    if not bool(scope.get("audit_aux_visible", False)):
        errors.append("audit_aux_not_visible")
    if not _bool_false(scope.get("v2_formal_cards_use_cache", True)):
        errors.append("v2_formal_cards_use_cache_not_false")
    if not _bool_false(scope.get("v4_formal_cards_use_cache", True)):
        errors.append("v4_formal_cards_use_cache_not_false")
    if not _bool_false(scope.get("qq_uses_cache", True)):
        errors.append("qq_uses_cache_not_false")

    cards = report.get("cards", []) if isinstance(report.get("cards", []), list) else []
    if not cards:
        warnings.append("cards_missing")
    for card in cards:
        if not isinstance(card, dict):
            errors.append("card_invalid")
            continue
        label = str(card.get("label", ""))
        if not label:
            errors.append(f"card_label_missing:{card.get('id', 'unknown')}")

    return {
        "status": "PASS" if not errors else "FAIL",
        "warnings": warnings + (report.get("warnings", []) if isinstance(report.get("warnings", []), list) else []),
        "errors": errors + (report.get("errors", []) if isinstance(report.get("errors", []), list) else []),
    }
