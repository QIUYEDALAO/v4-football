#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
STATUS_DIR = BASE_DIR / "data" / "runtime" / "status"
CN_TZ = timezone(timedelta(hours=8))
DRYRUN_SCHEMA = "api_aux_detail_dryrun.v1"

SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"(?i)x-apisports-key\\s*[:=]\\s*['\"]?[A-Za-z0-9_\\-]{8,}"),
    re.compile(r"(?i)apifootball[_-]?key\\s*[:=]\\s*['\"]?[A-Za-z0-9_\\-]{8,}"),
    re.compile(r"(?i)token\\s*[:=]\\s*['\"]?[A-Za-z0-9_\\-]{16,}"),
    re.compile(r"(?i)secret\\s*[:=]\\s*['\"]?[A-Za-z0-9_\\-]{10,}"),
]

FORBIDDEN_KEYS = {"raw_response", "response_body", "body", "full_response"}


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _scan_secret(text: str) -> list[str]:
    out: list[str] = []
    for idx, pat in enumerate(SECRET_PATTERNS):
        if pat.search(text):
            out.append(f"pattern_{idx}")
    return out


def _has_forbidden_key(obj: Any) -> bool:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if str(k).lower() in FORBIDDEN_KEYS:
                return True
            if _has_forbidden_key(v):
                return True
    elif isinstance(obj, list):
        for x in obj:
            if _has_forbidden_key(x):
                return True
    return False


def _source_code_checks() -> tuple[bool, list[str]]:
    src = BASE_DIR / "engine" / "api_aux_detail.py"
    if not src.exists():
        return False, ["aux_detail_source_missing"]
    txt = src.read_text(encoding="utf-8", errors="replace")
    findings: list[str] = []
    for token in ["requests.", "httpx.", "urllib.request", "urlopen(", "socket."]:
        if token in txt:
            findings.append(f"network_call_token:{token}")
    for token in ["APIFOOTBALL_KEY", "OPENCLAW_APIFOOTBALL_KEY", "os.environ"]:
        if token in txt:
            findings.append(f"key_read_token:{token}")
    return (len(findings) == 0), findings


def main() -> None:
    parser = argparse.ArgumentParser(description="Check API auxiliary detail dry-run marker")
    parser.add_argument("--date", required=True, help="YYYYMMDD")
    args = parser.parse_args()

    date_key = args.date.strip().replace("-", "")
    in_path = STATUS_DIR / f"api_aux_detail_dryrun_{date_key}.json"
    out_path = STATUS_DIR / f"api_aux_detail_check_{date_key}.json"

    warnings: list[str] = []
    errors: list[str] = []

    if not in_path.exists():
        result = {
            "status": "BLOCKER",
            "schema_valid": False,
            "boundary_valid": False,
            "display_scope_valid": False,
            "labels_valid": False,
            "raw_response_hidden": False,
            "secret_safe": False,
            "no_api": True,
            "no_key_read": True,
            "production_dependency": False,
            "production_verified": False,
            "warnings": [],
            "errors": ["aux_detail_dryrun_marker_missing"],
            "date": date_key,
            "generated_at": datetime.now(CN_TZ).isoformat(),
        }
        out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        raise SystemExit(2)

    marker = _load_json(in_path, {})
    schema_valid = str(marker.get("schema_version", "")) == DRYRUN_SCHEMA

    boundary_valid = True
    if str(marker.get("mode", "")).lower() != "auxiliary_detail_display":
        boundary_valid = False
        errors.append("mode_invalid")
    for k in [
        "no_api",
        "no_key_read",
        "no_push",
        "no_strategy_recompute",
        "no_cron",
        "production_path_untouched",
        "fallback_to_original_source",
        "raw_response_hidden",
    ]:
        if not bool(marker.get(k, False)):
            boundary_valid = False
            errors.append(f"{k}_false")

    if bool(marker.get("raw_response_visible", True)):
        boundary_valid = False
        errors.append("raw_response_visible_not_false")

    if bool(marker.get("production_dependency", True)):
        boundary_valid = False
        errors.append("production_dependency_not_false")
    if bool(marker.get("production_verified", True)):
        boundary_valid = False
        errors.append("production_verified_not_false")

    display_scope_valid = True
    if bool(marker.get("v2_formal_cards_use_cache", True)):
        display_scope_valid = False
        errors.append("v2_formal_cards_use_cache_not_false")
    if bool(marker.get("v4_formal_cards_use_cache", True)):
        display_scope_valid = False
        errors.append("v4_formal_cards_use_cache_not_false")
    if bool(marker.get("qq_uses_cache", True)):
        display_scope_valid = False
        errors.append("qq_uses_cache_not_false")

    labels_valid = True
    report = marker.get("report", {}) if isinstance(marker.get("report", {}), dict) else {}
    detail_cards = report.get("detail_cards", []) if isinstance(report.get("detail_cards", []), list) else []
    if not detail_cards:
        labels_valid = False
        warnings.append("detail_cards_missing")

    for card in detail_cards:
        if not isinstance(card, dict):
            labels_valid = False
            errors.append("detail_card_invalid")
            continue
        label = str(card.get("label", ""))
        if ("辅助详情" not in label) and ("不作生产证据" not in label) and ("非生产证据" not in label):
            labels_valid = False
            errors.append(f"detail_card_label_invalid:{card.get('id', 'unknown')}")
        if _has_forbidden_key(card):
            boundary_valid = False
            errors.append(f"detail_card_has_forbidden_response_field:{card.get('id', 'unknown')}")

    secret_safe = True
    secret_findings = _scan_secret(json.dumps(marker, ensure_ascii=False))
    if secret_findings:
        secret_safe = False
        errors.append("secret_pattern_detected")

    src_ok, src_findings = _source_code_checks()
    if not src_ok:
        boundary_valid = False
        errors.extend(src_findings)

    if not schema_valid:
        errors.append("schema_invalid")

    status = "PASS"
    if not schema_valid or not boundary_valid or not display_scope_valid or not labels_valid or not secret_safe:
        status = "FAIL"
    elif marker.get("warnings") or warnings:
        status = "WARN"

    result = {
        "status": status,
        "schema_valid": schema_valid,
        "boundary_valid": boundary_valid,
        "display_scope_valid": display_scope_valid,
        "labels_valid": labels_valid,
        "raw_response_hidden": bool(marker.get("raw_response_hidden", False)),
        "secret_safe": secret_safe,
        "no_api": True,
        "no_key_read": True,
        "production_dependency": False,
        "production_verified": False,
        "warnings": warnings + (marker.get("warnings", []) if isinstance(marker.get("warnings", []), list) else []),
        "errors": errors,
        "secret_findings": secret_findings,
        "date": date_key,
        "generated_at": datetime.now(CN_TZ).isoformat(),
    }

    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
