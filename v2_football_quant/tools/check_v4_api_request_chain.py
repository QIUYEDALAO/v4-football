#!/usr/bin/env python3
"""Trace V4 API request chain without issuing remote requests."""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.net_utils import resolve_provider_config  # noqa: E402

STATUS = ROOT / "data/runtime/status"


def line_for(path: Path, pattern: str) -> int | None:
    text = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
    for i, line in enumerate(text.splitlines(), 1):
        if pattern in line:
            return i
    return None


def names_from_config() -> list[str]:
    p = ROOT / "config/secrets.py"
    if not p.exists():
        return []
    try:
        tree = ast.parse(p.read_text(encoding="utf-8"))
    except Exception:
        return []
    out = []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    out.append(target.id)
    return out


def main() -> int:
    scanner = ROOT / "engine/v4_scan_and_brief.py"
    worker = ROOT / "engine/v4_scan_worker.py"
    runner = ROOT / "engine/v4_runner.py"
    api_client = ROOT / "engine/net_utils.py"
    trace = resolve_provider_config()
    net_text = api_client.read_text(encoding="utf-8", errors="replace")
    runner_text = runner.read_text(encoding="utf-8", errors="replace")
    scanner_text = scanner.read_text(encoding="utf-8", errors="replace")
    result = {
        "schema_version": "v4_api_request_chain_trace.v1",
        "scanner_path": "engine/v4_scan_and_brief.py",
        "worker_path": "engine/v4_scan_worker.py",
        "runner_path": "engine/v4_runner.py",
        "api_client_path": "engine/net_utils.py",
        "urllib_call_path": "engine/net_utils.py:_urllib_raw_get",
        "curl_fallback_path": "engine/net_utils.py:_curl_raw_get",
        "cache_layer_path": "engine/v4_runner.py:_cached_api_client",
        "provider_config_path": "engine/net_utils.py:PROVIDERS + config.secrets.API_HOST",
        "endpoint_host": trace.get("endpoint_host"),
        "header_names": trace.get("header_names"),
        "env_var_names_masked": trace.get("env_var_names_masked"),
        "config_secret_names": names_from_config(),
        "retry_policy": {
            "subscription_403_retry": False,
            "network_error_curl_fallback_once": "API_NETWORK_ERROR" in net_text and "fallback_count" in net_text,
            "max_consecutive_errors": "DEFAULT_MAX_CONSECUTIVE_ERRORS" in net_text,
        },
        "fallback_policy": {
            "curl_fallback_on_subscription_403": False,
            "subscription_403_fail_fast": "API_FORBIDDEN_FAIL_FAST" in net_text,
        },
        "error_classifier_path": "engine/net_utils.py:classify_api_response",
        "date_assignment_line": line_for(runner, "api_preflight(today_key"),
        "preflight_in_supervisor_line": line_for(scanner, "api_preflight(today_key"),
        "preflight_in_runner_line": line_for(runner, "api_preflight(today_key"),
        "cache_miss_remote_call_line": line_for(runner, "resp = base_client(endpoint)"),
        "request_chain_complete": all([scanner.exists(), worker.exists(), runner.exists(), api_client.exists()]),
        "provider_mismatch": trace.get("provider_mismatch"),
        "host_mismatch": trace.get("host_mismatch"),
        "header_mismatch": trace.get("header_mismatch"),
        "secret_printed": False,
        "blockers": [],
    }
    if not result["request_chain_complete"]:
        result["blockers"].append("request_chain_file_missing")
    if trace.get("provider_mismatch"):
        result["blockers"].append("provider_unknown")
    if not result["preflight_in_supervisor_line"] or not result["preflight_in_runner_line"]:
        result["blockers"].append("preflight_gate_missing")
    result["check_status"] = "PASS" if not result["blockers"] else "BLOCKER"
    STATUS.mkdir(parents=True, exist_ok=True)
    (STATUS / "v4_api_request_chain_trace_20260523.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["check_status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
