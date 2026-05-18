#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

try:
    from engine.api_snapshot_cache import build_real_ingest_result
except Exception:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from engine.api_snapshot_cache import build_real_ingest_result  # type: ignore

BASE_DIR = Path(__file__).resolve().parent.parent
RUNTIME_DIR = BASE_DIR / "data" / "runtime"
STATUS_DIR = RUNTIME_DIR / "status"
REAL_DIR = RUNTIME_DIR / "cache" / "api_snapshot"
CN_TZ = timezone(timedelta(hours=8))

API_HOST = "https://v3.football.api-sports.io"
SAFE_ENDPOINTS = {
    "status": "status",
    # reserved aliases (kept blocked for now unless explicitly enabled later)
    "fixtures_minimal": None,
    "leagues_minimal": None,
}


def _write_marker(date_key: str, payload: dict) -> Path:
    marker = STATUS_DIR / f"api_controlled_ingest_real_{date_key}.json"
    marker.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return marker


def _safe_secret_scan(text: str) -> bool:
    lowered = text.lower()
    if "x-apisports-key" in lowered:
        return False
    if "apifootball_key" in lowered:
        return False
    if "token" in lowered and "access_token" in lowered:
        return False
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Controlled real API ingest smoke test (single request)")
    parser.add_argument("--date", required=True, help="YYYYMMDD")
    parser.add_argument("--endpoint", required=True, help="status|fixtures_minimal|leagues_minimal")
    args = parser.parse_args()

    date_key = args.date.strip().replace("-", "")
    endpoint_name = args.endpoint.strip()

    endpoint_path = SAFE_ENDPOINTS.get(endpoint_name)
    result = build_real_ingest_result(date_key, endpoint_name=endpoint_name, endpoint_path=str(endpoint_path or ""), timeout_seconds=10, max_requests=1)

    if endpoint_name not in SAFE_ENDPOINTS:
        result["errors"].append("unsupported_endpoint")
        result["status"] = "BLOCKER"
        marker = _write_marker(date_key, result)
        print(json.dumps({"ok": False, "status": "BLOCKER", "reason": "unsupported_endpoint", "marker": str(marker)}, ensure_ascii=False, indent=2))
        raise SystemExit(2)

    if endpoint_path is None:
        result["errors"].append("endpoint_not_approved_for_c4")
        result["status"] = "BLOCKER"
        marker = _write_marker(date_key, result)
        print(json.dumps({"ok": False, "status": "BLOCKER", "reason": "endpoint_not_approved_for_c4", "marker": str(marker)}, ensure_ascii=False, indent=2))
        raise SystemExit(2)

    api_key = os.environ.get("APIFOOTBALL_KEY") or os.environ.get("OPENCLAW_APIFOOTBALL_KEY")
    if not api_key:
        result["errors"].append("missing_APIFOOTBALL_KEY")
        result["status"] = "BLOCKER"
        marker = _write_marker(date_key, result)
        print(json.dumps({"ok": False, "status": "BLOCKER", "reason": "missing_APIFOOTBALL_KEY", "marker": str(marker)}, ensure_ascii=False, indent=2))
        raise SystemExit(2)

    url = f"{API_HOST}/{endpoint_path}"
    req = urllib.request.Request(
        url,
        headers={
            "x-apisports-key": api_key,
            "User-Agent": "V2-Football-Quant/PhaseC4-Smoke",
        },
        method="GET",
    )

    timeout = int(result["request"].get("timeout_seconds", 10) or 10)
    result["request"]["request_count"] = 1

    start = time.time()
    raw_bytes = b""
    http_status = None
    ok = False

    try:
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            http_status = int(resp.status)
            raw_bytes = resp.read()
            ok = 200 <= http_status < 300
    except urllib.error.HTTPError as e:
        http_status = int(e.code)
        raw_bytes = e.read() if hasattr(e, "read") else b""
        ok = False
        result["warnings"].append("http_error")
    except Exception:
        ok = False
        result["warnings"].append("request_exception")

    duration_ms = int((time.time() - start) * 1000)
    result["response"]["http_status"] = http_status
    result["response"]["ok"] = ok
    result["response"]["duration_ms"] = duration_ms
    result["response"]["response_size_bytes"] = len(raw_bytes)

    real_dir = REAL_DIR / date_key / "real_ingest"
    real_dir.mkdir(parents=True, exist_ok=True)
    raw_path = real_dir / f"{endpoint_name}.json"

    payload_obj = None
    if raw_bytes:
        try:
            payload_obj = json.loads(raw_bytes.decode("utf-8", errors="replace"))
        except Exception:
            payload_obj = {"raw_text": raw_bytes.decode("utf-8", errors="replace")[:20000]}

    snapshot = {
        "schema_version": "real_ingest.raw.v1",
        "date": date_key,
        "endpoint_name": endpoint_name,
        "endpoint_path": endpoint_path,
        "http_status": http_status,
        "captured_at": datetime.now(CN_TZ).isoformat(),
        "response": payload_obj,
        "meta": {
            "api_key_logged": False,
            "request_headers_redacted": True,
        },
    }
    raw_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    result["response"]["raw_snapshot_path"] = str(raw_path)

    secret_safe = _safe_secret_scan(raw_path.read_text(encoding="utf-8"))
    result["safety"]["secret_safe"] = bool(secret_safe)
    if not secret_safe:
        result["errors"].append("secret_leak_detected_in_snapshot")

    result["status"] = "PASS" if (secret_safe and result["request"]["request_count"] == 1) else "FAIL"

    marker = _write_marker(date_key, result)
    print(
        json.dumps(
            {
                "ok": result["status"] == "PASS",
                "status": result["status"],
                "marker": str(marker),
                "raw_snapshot": str(raw_path),
                "http_status": http_status,
                "request_count": result["request"]["request_count"],
                "no_push": result["boundaries"]["no_push"],
                "no_cron": result["boundaries"]["no_cron"],
                "production_verified": result.get("production_verified", False),
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    if result["status"] == "BLOCKER":
        raise SystemExit(2)
    if result["status"] == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
