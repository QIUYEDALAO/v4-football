#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
RUNTIME_DIR = BASE_DIR / "data" / "runtime"
STATUS_DIR = RUNTIME_DIR / "status"

SCHEMA_VERSION = "api_cache_health.v1"


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _norm_status(value: Any) -> str:
    s = str(value or "MISSING").strip().upper()
    mapping = {
        "PASS": "PASS",
        "DONE": "PASS",
        "OK": "PASS",
        "CODE_READY": "PASS",
        "WARN": "WARN",
        "WARNING": "WARN",
        "PARTIAL": "WARN",
        "PARTIAL_DONE": "WARN",
        "FAIL": "FAIL",
        "FAILED": "FAIL",
        "ERROR": "FAIL",
        "BLOCKER": "BLOCKER",
        "MISSING": "MISSING",
        "NONE": "MISSING",
        "": "MISSING",
    }
    return mapping.get(s, "WARN")


def _combine_statuses(*statuses: str) -> str:
    vals = [_norm_status(s) for s in statuses]
    if any(v == "BLOCKER" for v in vals):
        return "BLOCKER"
    if any(v == "FAIL" for v in vals):
        return "FAIL"
    if any(v == "WARN" for v in vals):
        return "WARN"
    if any(v == "MISSING" for v in vals):
        return "MISSING"
    return "PASS"


def _bool_value(obj: Any, key: str, default: bool = False) -> bool:
    if isinstance(obj, dict):
        return bool(obj.get(key, default))
    return default


def collect_phase_statuses(date_key: str) -> dict[str, str]:
    clean = str(date_key).strip().replace("-", "")

    dashboard_card = _load_json(STATUS_DIR / f"dashboard_api_cache_status_card_{clean}.json", {})
    c2_check = _load_json(STATUS_DIR / f"api_snapshot_cache_check_{clean}.json", {})

    c3_sim = _load_json(STATUS_DIR / f"api_controlled_ingest_sim_{clean}.json", {})
    c3_check = _load_json(STATUS_DIR / f"api_controlled_ingest_check_{clean}.json", {})

    c4_real = _load_json(STATUS_DIR / f"api_controlled_ingest_real_{clean}.json", {})
    c4_check = _load_json(STATUS_DIR / f"api_real_ingest_check_{clean}.json", {})

    c5_reader = _load_json(STATUS_DIR / f"api_cache_reader_dryrun_{clean}.json", {})
    c5_check = _load_json(STATUS_DIR / f"api_cache_reader_check_{clean}.json", {})

    c6_shadow = _load_json(STATUS_DIR / f"api_shadow_read_dryrun_{clean}.json", {})
    c6_check = _load_json(STATUS_DIR / f"api_shadow_read_check_{clean}.json", {})

    c7_consumer = _load_json(STATUS_DIR / f"api_shadow_consumer_dryrun_{clean}.json", {})
    c7_check = _load_json(STATUS_DIR / f"api_shadow_consumer_check_{clean}.json", {})

    c8_gray = _load_json(STATUS_DIR / f"dashboard_api_cache_gray_check_{clean}.json", {})

    c9_aux = _load_json(STATUS_DIR / f"api_aux_display_dryrun_{clean}.json", {})
    c9_check = _load_json(STATUS_DIR / f"api_aux_display_check_{clean}.json", {})

    c10_aux_detail = _load_json(STATUS_DIR / f"api_aux_detail_dryrun_{clean}.json", {})
    c10_check = _load_json(STATUS_DIR / f"api_aux_detail_check_{clean}.json", {})

    c11_aux_explain = _load_json(STATUS_DIR / f"api_aux_explain_dryrun_{clean}.json", {})
    c11_check = _load_json(STATUS_DIR / f"api_aux_explain_check_{clean}.json", {})

    phases = {
        "c1_dashboard_status_card": _norm_status(dashboard_card.get("status", "MISSING")),
        "c2_schema_checker": _norm_status(c2_check.get("status", "MISSING")),
        "c3_controlled_sim": _combine_statuses(
            _norm_status(c3_sim.get("status", "MISSING")),
            _norm_status(c3_check.get("status", "MISSING")),
        ),
        "c4_real_smoke": _combine_statuses(
            _norm_status(c4_real.get("status", "MISSING")),
            _norm_status(c4_check.get("status", "MISSING")),
        ),
        "c5_reader": _combine_statuses(
            _norm_status(c5_reader.get("status", "MISSING")),
            _norm_status(c5_check.get("status", "MISSING")),
        ),
        "c6_shadow_read": _combine_statuses(
            _norm_status(c6_shadow.get("status", "MISSING")),
            _norm_status(c6_check.get("status", "MISSING")),
        ),
        "c7_shadow_consumer": _combine_statuses(
            _norm_status(c7_consumer.get("status", "MISSING")),
            _norm_status(c7_check.get("status", "MISSING")),
        ),
        "c8_gray_page": _norm_status(c8_gray.get("status", "MISSING")),
        "c9_aux_display": _combine_statuses(
            _norm_status(c9_aux.get("status", "MISSING")),
            _norm_status(c9_check.get("status", "MISSING")),
        ),
        "c10_aux_detail": _combine_statuses(
            _norm_status(c10_aux_detail.get("status", "MISSING")),
            _norm_status(c10_check.get("status", "MISSING")),
        ),
        "c11_aux_explain": _combine_statuses(
            _norm_status(c11_aux_explain.get("status", "MISSING")),
            _norm_status(c11_check.get("status", "MISSING")),
        ),
    }
    return phases


def summarize_health_status(phase_statuses: dict[str, str]) -> dict[str, Any]:
    counts = {"PASS": 0, "WARN": 0, "FAIL": 0, "MISSING": 0, "BLOCKER": 0}
    for v in phase_statuses.values():
        counts[_norm_status(v)] += 1

    if counts["BLOCKER"] > 0:
        overall = "BLOCKER"
    elif counts["FAIL"] > 0:
        overall = "FAIL"
    elif counts["WARN"] > 0 or counts["MISSING"] > 0:
        overall = "WARN"
    else:
        overall = "PASS"

    return {
        "pass_count": counts["PASS"],
        "warn_count": counts["WARN"],
        "fail_count": counts["FAIL"],
        "missing_count": counts["MISSING"],
        "blocker_count": counts["BLOCKER"],
        "overall_status": overall,
    }


def build_api_cache_health_summary(date_key: str) -> dict[str, Any]:
    clean = str(date_key).strip().replace("-", "")

    c4_check = _load_json(STATUS_DIR / f"api_real_ingest_check_{clean}.json", {})
    c5_reader = _load_json(STATUS_DIR / f"api_cache_reader_dryrun_{clean}.json", {})
    c5_check = _load_json(STATUS_DIR / f"api_cache_reader_check_{clean}.json", {})
    c6_shadow = _load_json(STATUS_DIR / f"api_shadow_read_dryrun_{clean}.json", {})
    c6_check = _load_json(STATUS_DIR / f"api_shadow_read_check_{clean}.json", {})
    c7_consumer = _load_json(STATUS_DIR / f"api_shadow_consumer_dryrun_{clean}.json", {})
    c7_check = _load_json(STATUS_DIR / f"api_shadow_consumer_check_{clean}.json", {})
    c9_aux = _load_json(STATUS_DIR / f"api_aux_display_dryrun_{clean}.json", {})
    c10_aux_detail = _load_json(STATUS_DIR / f"api_aux_detail_dryrun_{clean}.json", {})
    c11_aux_explain = _load_json(STATUS_DIR / f"api_aux_explain_dryrun_{clean}.json", {})

    phase_statuses = collect_phase_statuses(clean)
    summary = summarize_health_status(phase_statuses)

    secret_safe = all(
        [
            _bool_value(c4_check, "secret_safe", True),
            _bool_value(c5_check, "secret_safe", True),
            _bool_value(c6_check, "secret_safe", True),
            _bool_value(c7_check, "secret_safe", True),
            _bool_value(_load_json(STATUS_DIR / f"api_aux_display_check_{clean}.json", {}), "secret_safe", True),
            _bool_value(_load_json(STATUS_DIR / f"api_aux_detail_check_{clean}.json", {}), "secret_safe", True),
            _bool_value(_load_json(STATUS_DIR / f"api_aux_explain_check_{clean}.json", {}), "secret_safe", True),
        ]
    )

    formal_v2_uses_cache = any(
        [
            _bool_value(c9_aux, "v2_formal_cards_use_cache", False),
            _bool_value(c10_aux_detail, "v2_formal_cards_use_cache", False),
            _bool_value(c11_aux_explain, "v2_formal_cards_use_cache", False),
        ]
    )
    formal_v4_uses_cache = any(
        [
            _bool_value(c9_aux, "v4_formal_cards_use_cache", False),
            _bool_value(c10_aux_detail, "v4_formal_cards_use_cache", False),
            _bool_value(c11_aux_explain, "v4_formal_cards_use_cache", False),
        ]
    )
    qq_uses_cache = any(
        [
            _bool_value(c9_aux, "qq_uses_cache", False),
            _bool_value(c10_aux_detail, "qq_uses_cache", False),
            _bool_value(c11_aux_explain, "qq_uses_cache", False),
        ]
    )

    raw_response_visible = any(
        [
            _bool_value(c10_aux_detail, "raw_response_visible", False),
            _bool_value(c11_aux_explain, "raw_response_visible", False),
        ]
    )

    production_dependency_flag = any(
        [
            _bool_value(c5_reader, "production_dependency", False),
            _bool_value(c6_shadow, "production_dependency", False),
            _bool_value(c7_consumer, "production_dependency", False),
            _bool_value(c9_aux, "production_dependency", False),
            _bool_value(c10_aux_detail, "production_dependency", False),
            _bool_value(c11_aux_explain, "production_dependency", False),
        ]
    )
    production_verified_flag = any(
        [
            _bool_value(c5_reader, "production_verified", False),
            _bool_value(c6_shadow, "production_verified", False),
            _bool_value(c7_consumer, "production_verified", False),
            _bool_value(c9_aux, "production_verified", False),
            _bool_value(c10_aux_detail, "production_verified", False),
            _bool_value(c11_aux_explain, "production_verified", False),
        ]
    )

    safety = {
        "secret_safe": bool(secret_safe),
        "production_dependency_safe": not production_dependency_flag,
        "production_verified_safe": not production_verified_flag,
        "formal_link_safe": not formal_v2_uses_cache and not formal_v4_uses_cache and not qq_uses_cache,
        "raw_response_safe": not raw_response_visible,
    }

    warnings: list[str] = []
    errors: list[str] = []

    if summary["warn_count"] > 0 or summary["missing_count"] > 0:
        warnings.append("phase_status_contains_warn_or_missing")

    if not safety["secret_safe"]:
        errors.append("secret_safe_false")
    if production_dependency_flag:
        errors.append("production_dependency_true")
    if production_verified_flag:
        errors.append("production_verified_true")
    if formal_v2_uses_cache:
        errors.append("formal_v2_uses_cache_true")
    if formal_v4_uses_cache:
        errors.append("formal_v4_uses_cache_true")
    if qq_uses_cache:
        errors.append("qq_uses_cache_true")
    if raw_response_visible:
        errors.append("raw_response_visible_true")

    overall = summary["overall_status"]
    if errors:
        overall = "FAIL"

    limitations = [
        "当前不能代表V2/V4业务数据一致",
        "当前不能替换正式API调用",
        "当前不能用于推荐、结算、消息发送",
        "当前不能写PRODUCTION_VERIFIED",
    ]

    return {
        "schema_version": SCHEMA_VERSION,
        "date": clean,
        "mode": "daily_health_summary",
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
            "formal_v2_uses_cache": formal_v2_uses_cache,
            "formal_v4_uses_cache": formal_v4_uses_cache,
            "qq_uses_cache": qq_uses_cache,
            "raw_response_visible": raw_response_visible,
        },
        "phase_statuses": phase_statuses,
        "summary": {
            **summary,
            "overall_status": overall,
        },
        "safety": safety,
        "limitations": limitations,
        "warnings": warnings,
        "errors": errors,
    }


def validate_api_cache_health_boundary(summary: dict[str, Any]) -> dict[str, Any]:
    warnings: list[str] = []
    errors: list[str] = []

    if str(summary.get("schema_version", "")) != SCHEMA_VERSION:
        errors.append("schema_version_invalid")
    if str(summary.get("mode", "")) != "daily_health_summary":
        errors.append("mode_invalid")

    if bool(summary.get("production_dependency", True)):
        errors.append("production_dependency_not_false")
    if bool(summary.get("production_verified", True)):
        errors.append("production_verified_not_false")

    b = summary.get("boundaries", {}) if isinstance(summary.get("boundaries", {}), dict) else {}
    for key in ("no_api", "no_key_read", "no_push", "no_strategy_recompute", "no_cron", "production_path_untouched"):
        if not bool(b.get(key, False)):
            errors.append(f"{key}_false")

    if bool(b.get("formal_v2_uses_cache", True)):
        errors.append("formal_v2_uses_cache_not_false")
    if bool(b.get("formal_v4_uses_cache", True)):
        errors.append("formal_v4_uses_cache_not_false")
    if bool(b.get("qq_uses_cache", True)):
        errors.append("qq_uses_cache_not_false")
    if bool(b.get("raw_response_visible", True)):
        errors.append("raw_response_visible_not_false")

    ps = summary.get("phase_statuses", {}) if isinstance(summary.get("phase_statuses", {}), dict) else {}
    if not ps:
        warnings.append("phase_statuses_missing")

    stats = summary.get("summary", {}) if isinstance(summary.get("summary", {}), dict) else {}
    counts = {
        "PASS": 0,
        "WARN": 0,
        "FAIL": 0,
        "MISSING": 0,
        "BLOCKER": 0,
    }
    for v in ps.values():
        counts[_norm_status(v)] += 1

    if int(stats.get("pass_count", -1)) != counts["PASS"]:
        errors.append("pass_count_mismatch")
    if int(stats.get("warn_count", -1)) != counts["WARN"]:
        errors.append("warn_count_mismatch")
    if int(stats.get("fail_count", -1)) != counts["FAIL"]:
        errors.append("fail_count_mismatch")
    if int(stats.get("missing_count", -1)) != counts["MISSING"]:
        errors.append("missing_count_mismatch")
    if int(stats.get("blocker_count", -1)) != counts["BLOCKER"]:
        errors.append("blocker_count_mismatch")

    expected = "PASS"
    if counts["BLOCKER"] > 0:
        expected = "BLOCKER"
    elif counts["FAIL"] > 0:
        expected = "FAIL"
    elif counts["WARN"] > 0 or counts["MISSING"] > 0:
        expected = "WARN"

    if summary.get("errors"):
        expected = "FAIL"

    if _norm_status(stats.get("overall_status", "MISSING")) != expected:
        errors.append("overall_status_mismatch")

    limitations = summary.get("limitations", []) if isinstance(summary.get("limitations", []), list) else []
    need = [
        "不能代表V2/V4业务数据一致",
        "不能替换正式API调用",
        "不能用于推荐、结算",
        "不能写PRODUCTION_VERIFIED",
    ]
    lim_text = "\n".join(str(x) for x in limitations)
    for s in need:
        if s not in lim_text:
            errors.append(f"limitations_missing:{s}")

    return {
        "status": "PASS" if not errors else "FAIL",
        "warnings": warnings,
        "errors": errors,
    }
