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
SUMMARY_SCHEMA = "api_cache_health_summary.v1"

SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"(?i)x-apisports-key\\s*[:=]\\s*['\"]?[A-Za-z0-9_\\-]{8,}"),
    re.compile(r"(?i)apifootball[_-]?key\\s*[:=]\\s*['\"]?[A-Za-z0-9_\\-]{8,}"),
    re.compile(r"(?i)token\\s*[:=]\\s*['\"]?[A-Za-z0-9_\\-]{16,}"),
    re.compile(r"(?i)secret\\s*[:=]\\s*['\"]?[A-Za-z0-9_\\-]{10,}"),
]


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


def _norm_status(value: Any) -> str:
    s = str(value or "MISSING").strip().upper()
    if s in {"PASS", "WARN", "FAIL", "MISSING", "BLOCKER"}:
        return s
    if s in {"DONE", "OK", "CODE_READY"}:
        return "PASS"
    if s in {"WARNING", "PARTIAL", "PARTIAL_DONE"}:
        return "WARN"
    if s in {"FAILED", "ERROR"}:
        return "FAIL"
    return "WARN"


def _source_code_checks() -> tuple[bool, list[str]]:
    src = BASE_DIR / "engine" / "api_cache_health.py"
    if not src.exists():
        return False, ["api_cache_health_source_missing"]
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
    parser = argparse.ArgumentParser(description="Check API cache health summary")
    parser.add_argument("--date", required=True, help="YYYYMMDD")
    args = parser.parse_args()

    date_key = args.date.strip().replace("-", "")
    in_path = STATUS_DIR / f"api_cache_health_summary_{date_key}.json"
    out_path = STATUS_DIR / f"api_cache_health_check_{date_key}.json"

    warnings: list[str] = []
    errors: list[str] = []

    if not in_path.exists():
        result = {
            "status": "BLOCKER",
            "schema_valid": False,
            "boundary_valid": False,
            "counts_valid": False,
            "limitations_valid": False,
            "secret_safe": False,
            "formal_link_safe": False,
            "production_dependency": False,
            "production_verified": False,
            "warnings": [],
            "errors": ["api_cache_health_summary_missing"],
            "date": date_key,
            "generated_at": datetime.now(CN_TZ).isoformat(),
        }
        out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        raise SystemExit(2)

    marker = _load_json(in_path, {})

    schema_valid = str(marker.get("schema_version", "")) == SUMMARY_SCHEMA

    boundary_valid = True
    if str(marker.get("mode", "")).lower() != "daily_health_summary":
        boundary_valid = False
        errors.append("mode_invalid")

    for k in ["no_api", "no_key_read", "no_push", "no_strategy_recompute", "no_cron", "production_path_untouched"]:
        if not bool(marker.get(k, False)):
            boundary_valid = False
            errors.append(f"{k}_false")

    if bool(marker.get("production_dependency", True)):
        boundary_valid = False
        errors.append("production_dependency_not_false")
    if bool(marker.get("production_verified", True)):
        boundary_valid = False
        errors.append("production_verified_not_false")
    if bool(marker.get("formal_v2_uses_cache", True)):
        boundary_valid = False
        errors.append("formal_v2_uses_cache_not_false")
    if bool(marker.get("formal_v4_uses_cache", True)):
        boundary_valid = False
        errors.append("formal_v4_uses_cache_not_false")
    if bool(marker.get("qq_uses_cache", True)):
        boundary_valid = False
        errors.append("qq_uses_cache_not_false")
    if bool(marker.get("raw_response_visible", True)):
        boundary_valid = False
        errors.append("raw_response_visible_not_false")

    summary = marker.get("summary", {}) if isinstance(marker.get("summary", {}), dict) else {}
    phase_statuses = summary.get("phase_statuses", {}) if isinstance(summary.get("phase_statuses", {}), dict) else {}
    summary_counts = summary.get("summary", {}) if isinstance(summary.get("summary", {}), dict) else {}
    counts_valid = True

    counts = {"PASS": 0, "WARN": 0, "FAIL": 0, "MISSING": 0, "BLOCKER": 0}
    for v in phase_statuses.values():
        counts[_norm_status(v)] += 1

    if int(summary_counts.get("pass_count", -1)) != counts["PASS"]:
        counts_valid = False
        errors.append("pass_count_mismatch")
    if int(summary_counts.get("warn_count", -1)) != counts["WARN"]:
        counts_valid = False
        errors.append("warn_count_mismatch")
    if int(summary_counts.get("fail_count", -1)) != counts["FAIL"]:
        counts_valid = False
        errors.append("fail_count_mismatch")
    if int(summary_counts.get("missing_count", -1)) != counts["MISSING"]:
        counts_valid = False
        errors.append("missing_count_mismatch")
    if int(summary_counts.get("blocker_count", -1)) != counts["BLOCKER"]:
        counts_valid = False
        errors.append("blocker_count_mismatch")

    expected = "PASS"
    if counts["BLOCKER"] > 0:
        expected = "BLOCKER"
    elif counts["FAIL"] > 0:
        expected = "FAIL"
    elif counts["WARN"] > 0 or counts["MISSING"] > 0:
        expected = "WARN"

    if _norm_status(summary_counts.get("overall_status", "MISSING")) != expected:
        counts_valid = False
        errors.append("overall_status_mismatch")

    limitations_valid = True
    limitations = summary.get("limitations", []) if isinstance(summary.get("limitations", []), list) else []
    lim_text = "\n".join(str(x) for x in limitations)
    required = [
        "不能代表V2/V4业务数据一致",
        "不能替换正式API调用",
        "不能用于推荐、结算",
        "不能写PRODUCTION_VERIFIED",
    ]
    for r in required:
        if r not in lim_text:
            limitations_valid = False
            errors.append(f"limitations_missing:{r}")

    secret_safe = bool(marker.get("secret_safe", False))
    if not secret_safe:
        errors.append("secret_safe_false")

    findings = _scan_secret(json.dumps(marker, ensure_ascii=False))
    if findings:
        secret_safe = False
        errors.append("secret_pattern_detected")

    formal_link_safe = (
        not bool(marker.get("formal_v2_uses_cache", True))
        and not bool(marker.get("formal_v4_uses_cache", True))
        and not bool(marker.get("qq_uses_cache", True))
    )
    if not formal_link_safe:
        errors.append("formal_link_not_safe")

    src_ok, src_findings = _source_code_checks()
    if not src_ok:
        boundary_valid = False
        errors.extend(src_findings)

    if not schema_valid:
        errors.append("schema_invalid")

    status = "PASS"
    if _norm_status(summary_counts.get("overall_status", "WARN")) in {"WARN", "MISSING"}:
        status = "WARN"
    if _norm_status(summary_counts.get("overall_status", "WARN")) in {"FAIL", "BLOCKER"}:
        status = _norm_status(summary_counts.get("overall_status", "WARN"))

    if not schema_valid or not boundary_valid or not counts_valid or not limitations_valid or not secret_safe or not formal_link_safe:
        status = "FAIL"

    result = {
        "status": status,
        "schema_valid": schema_valid,
        "boundary_valid": boundary_valid,
        "counts_valid": counts_valid,
        "limitations_valid": limitations_valid,
        "secret_safe": secret_safe,
        "formal_link_safe": formal_link_safe,
        "production_dependency": False,
        "production_verified": False,
        "warnings": warnings + (marker.get("warnings", []) if isinstance(marker.get("warnings", []), list) else []),
        "errors": errors,
        "date": date_key,
        "generated_at": datetime.now(CN_TZ).isoformat(),
    }

    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
