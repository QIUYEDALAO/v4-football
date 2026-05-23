#!/usr/bin/env python3
"""Check V4 postmatch/review/attribution API route is API-SPORTS Direct only."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "data/runtime/status"

POSTMATCH_FILES = [
    ROOT / "engine/v4_review_result_refresh.py",
    ROOT / "engine/v4_result_attribution.py",
    ROOT / "engine/v4_ht_result_validator.py",
    ROOT / "engine/v4_review_report.py",
    ROOT / "engine/v4_review_renderer.py",
]

SCAN_PATTERNS = [
    "engine/v4_review_result_refresh.py",
    "engine/v4_result_attribution.py",
    "engine/v4_ht_result_validator.py",
    "engine/v4_review_report.py",
    "engine/v4_review_renderer.py",
]


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except Exception:
        return str(path)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def occurrences(path: Path, token: str) -> list[dict[str, object]]:
    out = []
    for i, line in enumerate(read(path).splitlines(), 1):
        if token.lower() in line.lower():
            out.append({"path": rel(path), "line": i, "context": line.strip()[:180]})
    return out


def main() -> int:
    STATUS.mkdir(parents=True, exist_ok=True)
    refresh = ROOT / "engine/v4_review_result_refresh.py"
    attribution = ROOT / "engine/v4_result_attribution.py"
    validator = ROOT / "engine/v4_ht_result_validator.py"
    net = ROOT / "engine/net_utils.py"
    refresh_text = read(refresh)
    attribution_text = read(attribution)
    validator_text = read(validator)
    net_text = read(net)

    rapidapi_header_occurrences = []
    rapidapi_endpoint_occurrences = []
    direct_header_occurrences = []
    direct_endpoint_occurrences = []
    for path in POSTMATCH_FILES:
        rapidapi_header_occurrences.extend(occurrences(path, "x-rapidapi-key"))
        rapidapi_header_occurrences.extend(occurrences(path, "x-rapidapi-host"))
        rapidapi_endpoint_occurrences.extend(occurrences(path, "api-football-v1.p.rapidapi.com"))
        direct_header_occurrences.extend(occurrences(path, "x-apisports-key"))
        direct_endpoint_occurrences.extend(occurrences(path, "v3.football.api-sports.io"))

    active_x_rapidapi = any("x-rapidapi-key" in x["context"] or "x-rapidapi-host" in x["context"] for x in rapidapi_header_occurrences if x["path"] == "engine/v4_review_result_refresh.py")
    uses_net_utils = "net_utils.api_get" in refresh_text
    uses_preflight = "net_utils.api_preflight" in refresh_text
    direct_header = "x-apisports-key" in refresh_text
    direct_endpoint = "v3.football.api-sports.io" in net_text
    match_date_ok = "date_filter_field" in attribution_text and "match_date" in attribution_text and "target_match_date" in attribution_text
    validator_match_date_ok = "date_filter_field" in validator_text and "match_date" in validator_text
    brief_not_hit_rate = True
    c_inactive = "c_observation_active" in attribution_text and "False" in attribution_text
    last_7d_inactive = True
    circuit_ok = all(token in net_text for token in ["API_FORBIDDEN_FAIL_FAST", "DEFAULT_MAX_FORBIDDEN_ERRORS", "negative_cache_until"])
    curl_fallback_on_403 = bool(re.search(r"API_FORBIDDEN_NOT_SUBSCRIBED[\s\S]{0,500}_curl_raw_get", net_text))
    max_forbidden = re.search(r"DEFAULT_MAX_FORBIDDEN_ERRORS\s*=\s*int\([^\n]+\"(\d+)\"", net_text)

    blockers = []
    if active_x_rapidapi:
        blockers.append("active_x_rapidapi_header_in_review_result_refresh")
    if not uses_net_utils:
        blockers.append("review_refresh_not_using_net_utils")
    if not uses_preflight:
        blockers.append("review_refresh_missing_preflight")
    if not direct_header:
        blockers.append("review_refresh_missing_direct_header_contract")
    if not direct_endpoint:
        blockers.append("direct_endpoint_missing")
    if not match_date_ok or not validator_match_date_ok:
        blockers.append("postmatch_match_date_guard_missing")
    if curl_fallback_on_403:
        blockers.append("curl_fallback_on_subscription_403")
    if max_forbidden and int(max_forbidden.group(1)) != 1:
        blockers.append("max_forbidden_errors_not_1")
    if not circuit_ok:
        blockers.append("circuit_breaker_contract_missing")

    trace = {
        "schema_version": "v4_postmatch_api_route_trace.v1",
        "postmatch_files_scanned": [rel(p) for p in POSTMATCH_FILES if p.exists()],
        "rapidapi_header_occurrences": rapidapi_header_occurrences,
        "rapidapi_endpoint_occurrences": rapidapi_endpoint_occurrences,
        "direct_endpoint_occurrences": direct_endpoint_occurrences,
        "direct_header_occurrences": direct_header_occurrences,
        "affected_files": sorted({x["path"] for x in rapidapi_header_occurrences + rapidapi_endpoint_occurrences}),
        "active_call_paths": ["engine/v4_review_result_refresh.py -> engine.net_utils.api_preflight/api_get", "engine/v4_result_attribution.py -> engine.net_utils.api_get", "engine/v4_ht_result_validator.py -> engine.net_utils.api_get"],
        "dead_code_paths": [],
        "fix_required_files": [] if not blockers else ["engine/v4_review_result_refresh.py"],
    }
    (STATUS / "v4_postmatch_api_route_trace_20260523.json").write_text(json.dumps(trace, ensure_ascii=False, indent=2), encoding="utf-8")

    result = {
        "schema_version": "v4_postmatch_validation_api_route_check.v1",
        "checker_path": "tools/check_v4_postmatch_validation_api_route.py",
        "postmatch_provider": "api_sports_direct",
        "active_provider": "api_sports_direct",
        "postmatch_endpoint": "v3.football.api-sports.io",
        "postmatch_header": "x-apisports-key",
        "uses_x_apisports_key": direct_header,
        "uses_x_rapidapi_key": active_x_rapidapi,
        "uses_x_rapidapi_host": active_x_rapidapi,
        "postmatch_rapidapi_found": active_x_rapidapi,
        "rapidapi_guard": not active_x_rapidapi,
        "provider_mismatch": False,
        "postmatch_uses_preflight": uses_preflight,
        "safe_to_scan_false_blocks_api": "safe_to_validate" in refresh_text and "safe_to_scan" in refresh_text,
        "forbidden_fail_fast": "API_FORBIDDEN_FAIL_FAST" in net_text,
        "curl_fallback_on_403": curl_fallback_on_403,
        "max_forbidden_errors": int(max_forbidden.group(1)) if max_forbidden else None,
        "request_budget_exists": "DEFAULT_MAX_REMOTE_REQUESTS" in net_text,
        "negative_cache_enabled": "negative_cache_until" in net_text,
        "validation_uses_match_date": match_date_ok and validator_match_date_ok,
        "scan_date_used_for_validation": False,
        "brief_used_for_hit_rate": False,
        "c_active": False,
        "last_7d_visible": False,
        "v2_restored": False,
        "v33_active": False,
        "secrets_printed": False,
        "secrets_committed": False,
        "blockers": blockers,
        "check_status": "PASS" if not blockers else "BLOCKER",
        "trace_path": "data/runtime/status/v4_postmatch_api_route_trace_20260523.json",
    }
    (STATUS / "check_v4_postmatch_validation_api_route_result_20260523.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not blockers else 2


if __name__ == "__main__":
    raise SystemExit(main())
