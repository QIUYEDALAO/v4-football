#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
RUNTIME_DIR = BASE_DIR / "data" / "runtime"
STATUS_DIR = RUNTIME_DIR / "status"

SCHEMA_VERSION = "api_aux_explain.v1"
FORBIDDEN_WORDING = [
    "V2已通过cache",
    "V4已通过cache",
    "已接入生产",
    "生产验证通过",
    "PRODUCTION_VERIFIED true",
    "可以替换正式API",
]


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


def _is_ok(status: str) -> bool:
    return str(status).upper() in {"PASS", "WARN"}


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


def summarize_capabilities(date_key: str) -> list[str]:
    clean = str(date_key).strip().replace("-", "")
    real_ingest_check = _load_json(STATUS_DIR / f"api_real_ingest_check_{clean}.json", {})
    reader_check = _load_json(STATUS_DIR / f"api_cache_reader_check_{clean}.json", {})
    shadow_read_check = _load_json(STATUS_DIR / f"api_shadow_read_check_{clean}.json", {})
    shadow_consumer_dryrun = _load_json(STATUS_DIR / f"api_shadow_consumer_dryrun_{clean}.json", {})

    out: list[str] = []

    if _is_ok(_status_of(real_ingest_check)) and bool(real_ingest_check.get("secret_safe", False)):
        out.append("真实API单请求smoke已通过（仅工程烟雾验证）")
    if _is_ok(_status_of(reader_check)) and bool(reader_check.get("boundary_valid", False)):
        out.append("cache reader可只读读取snapshot metadata")
    if _is_ok(_status_of(shadow_read_check)) and bool(shadow_read_check.get("boundary_valid", False)):
        out.append("shadow read可做metadata旁路对账")
    allowed = shadow_consumer_dryrun.get("allowed_consumers", []) if isinstance(shadow_consumer_dryrun.get("allowed_consumers", []), list) else []
    if {"dashboard", "replay", "audit"}.issubset(set(allowed)):
        out.append("dashboard/replay/audit可做非关键辅助展示")

    if not out:
        out.append("当前可读工程能力信息不完整，需先补齐状态marker")

    return out


def summarize_limitations(date_key: str) -> list[str]:
    _ = date_key
    return [
        "当前不能代表V2/V4业务数据一致",
        "当前不能替换正式API调用",
        "当前不能用于推荐、结算、消息发送",
        "当前不能写PRODUCTION_VERIFIED",
    ]


def build_explanation_cards(date_key: str) -> list[dict[str, Any]]:
    clean = str(date_key).strip().replace("-", "")

    aux_detail = _load_json(STATUS_DIR / f"api_aux_detail_dryrun_{clean}.json", {})
    aux_display = _load_json(STATUS_DIR / f"api_aux_display_dryrun_{clean}.json", {})
    shadow_consumer = _load_json(STATUS_DIR / f"api_shadow_consumer_dryrun_{clean}.json", {})
    reader_check = _load_json(STATUS_DIR / f"api_cache_reader_check_{clean}.json", {})

    can_prove_status = "PASS"
    st_candidates = [
        _status_of(aux_detail),
        _status_of(aux_display),
        _status_of(shadow_consumer),
        _status_of(reader_check),
    ]
    if any(s == "FAIL" for s in st_candidates):
        can_prove_status = "WARN"
    elif any(s in {"MISSING", "BLOCKER"} for s in st_candidates):
        can_prove_status = "WARN"

    cards = [
        {
            "id": "what_cache_can_prove",
            "title": "当前cache能证明什么",
            "label": "辅助解释，不作生产证据",
            "status": can_prove_status,
            "text": "可证明工程侧：reader/checker链路可读、smoke存在、旁路消费者边界有效。",
            "evidence_collapsed": True,
        },
        {
            "id": "what_cache_cannot_prove",
            "title": "当前cache不能证明什么",
            "label": "辅助解释，不作生产证据",
            "status": "WARN",
            "text": "不能证明V2/V4业务一致，不能替代正式数据源，不能用于推荐/结算/消息发送判断。",
            "evidence_collapsed": True,
        },
        {
            "id": "production_boundary",
            "title": "生产边界",
            "label": "正式链路禁用cache",
            "status": "PASS",
            "text": "V2/V4正式卡片仍走原来源；QQ发送链路不读cache；仅保留非关键只读展示。",
            "evidence_collapsed": True,
        },
    ]
    return cards


def build_aux_explain_report(date_key: str) -> dict[str, Any]:
    clean = str(date_key).strip().replace("-", "")
    cards = build_explanation_cards(clean)
    capabilities = summarize_capabilities(clean)
    limitations = summarize_limitations(clean)

    warnings: list[str] = []
    errors: list[str] = []

    if len(capabilities) == 0:
        warnings.append("capabilities_missing")
    if len(limitations) == 0:
        warnings.append("limitations_missing")
    if any(str(c.get("status", "")).upper() == "MISSING" for c in cards if isinstance(c, dict)):
        warnings.append("explanation_card_partial_missing")

    report = {
        "schema_version": SCHEMA_VERSION,
        "date": clean,
        "mode": "auxiliary_explanation",
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
            "dashboard_aux_explain_enabled": True,
            "replay_aux_explain_visible": True,
            "v2_formal_cards_use_cache": False,
            "v4_formal_cards_use_cache": False,
            "qq_uses_cache": False,
            "raw_response_visible": False,
        },
        "capabilities": capabilities,
        "limitations": limitations,
        "explanation_cards": cards,
        "warnings": warnings,
        "errors": errors,
    }
    return report


def validate_aux_explain_boundary(report: dict[str, Any]) -> dict[str, Any]:
    warnings: list[str] = []
    errors: list[str] = []

    if str(report.get("schema_version", "")) != SCHEMA_VERSION:
        errors.append("schema_version_invalid")
    if str(report.get("mode", "")) != "auxiliary_explanation":
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
    if not bool(scope.get("dashboard_aux_explain_enabled", False)):
        errors.append("dashboard_aux_explain_disabled")
    if not bool(scope.get("replay_aux_explain_visible", False)):
        errors.append("replay_aux_explain_not_visible")
    if bool(scope.get("v2_formal_cards_use_cache", True)):
        errors.append("v2_formal_cards_use_cache_not_false")
    if bool(scope.get("v4_formal_cards_use_cache", True)):
        errors.append("v4_formal_cards_use_cache_not_false")
    if bool(scope.get("qq_uses_cache", True)):
        errors.append("qq_uses_cache_not_false")
    if bool(scope.get("raw_response_visible", True)):
        errors.append("raw_response_visible_not_false")

    cards = report.get("explanation_cards", []) if isinstance(report.get("explanation_cards", []), list) else []
    if not cards:
        warnings.append("explanation_cards_missing")

    for card in cards:
        if not isinstance(card, dict):
            errors.append("explanation_card_invalid")
            continue
        label = str(card.get("label", ""))
        if ("辅助解释" not in label) and ("不作生产证据" not in label) and ("正式链路禁用cache" not in label):
            errors.append(f"explanation_card_label_invalid:{card.get('id', 'unknown')}")
        if _has_forbidden_response_key(card):
            errors.append(f"explanation_card_has_forbidden_response_field:{card.get('id', 'unknown')}")

        text = str(card.get("text", ""))
        for banned in FORBIDDEN_WORDING:
            if banned in text:
                errors.append(f"forbidden_wording_in_card:{card.get('id', 'unknown')}:{banned}")

    text_pool = "\n".join(
        [
            "\n".join(str(x) for x in report.get("capabilities", []) if isinstance(report.get("capabilities", []), list)),
            "\n".join(str(x) for x in report.get("limitations", []) if isinstance(report.get("limitations", []), list)),
        ]
    )
    for banned in FORBIDDEN_WORDING:
        if banned in text_pool:
            errors.append(f"forbidden_wording_in_report:{banned}")

    if not report.get("capabilities"):
        warnings.append("capabilities_missing")
    if not report.get("limitations"):
        warnings.append("limitations_missing")

    return {
        "status": "PASS" if not errors else "FAIL",
        "warnings": warnings + (report.get("warnings", []) if isinstance(report.get("warnings", []), list) else []),
        "errors": errors + (report.get("errors", []) if isinstance(report.get("errors", []), list) else []),
    }
