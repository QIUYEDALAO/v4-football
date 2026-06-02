#!/usr/bin/env python3
"""Validate V4 API 403 fail-fast, request budget, and scanner preflight gate."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "data/runtime/status"


def read(path: str) -> str:
    p = ROOT / path
    return p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""


def main() -> int:
    net = read("engine/net_utils.py")
    runner = read("engine/v4_runner.py")
    supervisor = read("engine/v4_scan_and_brief.py")
    dashboard = read("tools/build_v4_control_center_model.py")
    forbidden_fail_fast = "API_FORBIDDEN_FAIL_FAST" in net and "no_retry no_curl" in net
    curl_fallback_on_403 = bool(re.search(r"API_FORBIDDEN_NOT_SUBSCRIBED[\s\S]{0,500}_curl_raw_get", net))
    preflight_required = "api_preflight(today_key" in runner and "api_preflight(today_key" in supervisor
    scan_allowed_when_preflight_fail = "remote_scan_started\": False" not in runner or "worker_started\": False" not in supervisor
    max_remote = re.search(r"DEFAULT_MAX_REMOTE_REQUESTS\s*=\s*int\([^\n]+\"(\d+)\"", net)
    max_forbidden = re.search(r"DEFAULT_MAX_FORBIDDEN_ERRORS\s*=\s*int\([^\n]+\"(\d+)\"", net)
    negative_cache_enabled = "NEGATIVE_CACHE_TTL_SECONDS = 30 * 60" in net and "negative_cache_until" in net
    result = {
        "schema_version": "v4_api_403_circuit_breaker_check.v1",
        "forbidden_fail_fast": forbidden_fail_fast,
        "curl_fallback_on_403": curl_fallback_on_403,
        "preflight_required": preflight_required,
        "scan_allowed_when_preflight_fail": scan_allowed_when_preflight_fail,
        "max_remote_requests": int(max_remote.group(1)) if max_remote else None,
        "max_consecutive_errors": "DEFAULT_MAX_CONSECUTIVE_ERRORS" in net,
        "max_forbidden_errors": int(max_forbidden.group(1)) if max_forbidden else None,
        "negative_cache_enabled": negative_cache_enabled,
        "negative_cache_ttl_seconds_min": 1800,
        "request_budget_fields": all(token in net for token in [
            "api_calls_attempted", "api_calls_blocked_by_preflight", "api_calls_blocked_by_circuit_breaker",
            "remote_requests", "forbidden_count", "fallback_count", "cache_hits", "cache_misses"
        ]) or ("api_cache_hits" in runner and "api_cache_misses" in runner),
        "dashboard_api_status_visible": all(token in dashboard for token in ["API credential blocked", "last_good"]),
        "no_capture": True,
        "no_push": True,
        "no_cloud_publish": True,
        "blockers": [],
    }
    if not forbidden_fail_fast:
        result["blockers"].append("subscription_403_not_fail_fast")
    if curl_fallback_on_403:
        result["blockers"].append("curl_fallback_on_subscription_403")
    if not preflight_required:
        result["blockers"].append("scanner_preflight_missing")
    if scan_allowed_when_preflight_fail:
        result["blockers"].append("scan_allowed_when_preflight_fail")
    if result["max_forbidden_errors"] != 1:
        result["blockers"].append("max_forbidden_errors_not_1")
    if not negative_cache_enabled:
        result["blockers"].append("negative_cache_missing")
    result["check_status"] = "PASS" if not result["blockers"] else "BLOCKER"
    STATUS.mkdir(parents=True, exist_ok=True)
    (STATUS / "v4_api_403_circuit_breaker_check_20260523.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["check_status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
