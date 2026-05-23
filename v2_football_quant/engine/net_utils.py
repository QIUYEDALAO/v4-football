"""
共享网络工具 — API-Football provider routing + preflight + 403 circuit breaker
==========================================================================

安全口径：
  - active provider 必须唯一：RapidAPI 或 API-SPORTS official direct。
  - 403 subscription/not-subscribed 不允许 retry，不允许 curl fallback。
  - scanner 必须先通过 preflight；失败时进入 cache-only / API_BLOCKED。
  - 日志与 marker 只输出 key fingerprint，不输出完整 secret。
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import socket
import ssl
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
STATUS_DIR = BASE_DIR / "data" / "runtime" / "status"
STATUS_DIR.mkdir(parents=True, exist_ok=True)
CN_TZ = timezone(timedelta(hours=8))

PROVIDERS: dict[str, dict[str, Any]] = {
    "rapidapi": {
        "endpoint_host": "api-football-v1.p.rapidapi.com",
        "base_url": "https://api-football-v1.p.rapidapi.com/v3",
        "required_headers": ["x-rapidapi-key", "x-rapidapi-host"],
        "key_env_candidates": ["RAPIDAPI_KEY", "OPENCLAW_RAPIDAPI_KEY", "API_FOOTBALL_RAPIDAPI_KEY"],
    },
    "api_sports_direct": {
        "endpoint_host": "v3.football.api-sports.io",
        "base_url": "https://v3.football.api-sports.io",
        "required_headers": ["x-apisports-key"],
        "key_env_candidates": ["APIFOOTBALL_KEY", "OPENCLAW_APIFOOTBALL_KEY", "API_SPORTS_KEY", "APISPORTS_KEY"],
    },
}

NEGATIVE_CACHE_TTL_SECONDS = 30 * 60
DEFAULT_MAX_REMOTE_REQUESTS = int(os.environ.get("OPENCLAW_API_MAX_REMOTE_REQUESTS", "1200"))
DEFAULT_MAX_CONSECUTIVE_ERRORS = int(os.environ.get("OPENCLAW_API_MAX_CONSECUTIVE_ERRORS", "8"))
DEFAULT_MAX_FORBIDDEN_ERRORS = int(os.environ.get("OPENCLAW_API_MAX_FORBIDDEN_ERRORS", "1"))

_API_GUARD_STATE: dict[str, Any] = {
    "safe_to_scan": None,
    "api_status": "NOT_PREFLIGHTED",
    "circuit_breaker_triggered": False,
    "negative_cache_until": 0.0,
    "negative_cache_reason": None,
    "api_calls_attempted": 0,
    "api_calls_blocked_by_preflight": 0,
    "api_calls_blocked_by_circuit_breaker": 0,
    "remote_requests": 0,
    "forbidden_count": 0,
    "fallback_count": 0,
    "consecutive_errors": 0,
    "max_remote_requests": DEFAULT_MAX_REMOTE_REQUESTS,
    "max_consecutive_errors": DEFAULT_MAX_CONSECUTIVE_ERRORS,
    "max_forbidden_errors": DEFAULT_MAX_FORBIDDEN_ERRORS,
}

# ── Python urllib TLS context ──
try:
    import certifi
    _SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:  # pragma: no cover
    _SSL_CTX = ssl.create_default_context()

# 绕过本机代理，避免 API-Football 请求被本地代理污染。
urllib.request.install_opener(urllib.request.build_opener(urllib.request.ProxyHandler({})))

_RPM_LIMIT = 450
_rpm_window: list[float] = []


def _now() -> str:
    return datetime.now(CN_TZ).isoformat()


def _rpm_wait() -> None:
    global _rpm_window
    now = time.time()
    _rpm_window = [t for t in _rpm_window if now - t < 60]
    if len(_rpm_window) >= _RPM_LIMIT:
        wait_s = 60 - (now - _rpm_window[0]) + 0.5
        if wait_s > 0:
            time.sleep(wait_s)
    _rpm_window.append(time.time())


class ApiCredentialBlocked(RuntimeError):
    """Raised internally when API preflight/circuit breaker blocks remote calls."""


class _IPv4HTTPHandler(urllib.request.HTTPSHandler):
    def https_open(self, req):
        return self.do_open(self._ipv4_connection, req)

    @staticmethod
    def _ipv4_connection(host, **kwargs):
        import http.client
        try:
            addrs = socket.getaddrinfo(host, 443, socket.AF_INET, socket.SOCK_STREAM)
            ipv4 = addrs[0][4][0]
            conn = http.client.HTTPSConnection(ipv4, context=_SSL_CTX, **kwargs)
            conn.host = host
            return conn
        except Exception:
            return http.client.HTTPSConnection(host, context=_SSL_CTX, **kwargs)


_IPV4_OPENER = urllib.request.build_opener(_IPv4HTTPHandler, urllib.request.ProxyHandler({}))


def _get_config_value(name: str) -> str:
    try:
        from config import secrets  # type: ignore
        return str(getattr(secrets, name, "") or "")
    except Exception:
        return ""


def _normalized_host(api_host: str | None) -> str:
    raw = str(api_host or "").strip()
    if not raw:
        return PROVIDERS["api_sports_direct"]["endpoint_host"]
    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    return parsed.netloc or parsed.path.split("/", 1)[0]


def _base_url_for_host(api_host: str | None) -> str:
    raw = str(api_host or "").strip()
    if raw.startswith("http"):
        return raw.rstrip("/")
    host = _normalized_host(raw)
    if host == PROVIDERS["rapidapi"]["endpoint_host"]:
        return PROVIDERS["rapidapi"]["base_url"]
    return f"https://{host}"


def _detect_provider(api_host: str | None = None) -> str | None:
    explicit = os.environ.get("OPENCLAW_API_PROVIDER") or os.environ.get("V4_API_PROVIDER") or os.environ.get("API_FOOTBALL_PROVIDER")
    if explicit:
        value = explicit.strip().lower().replace("-", "_")
        if value in {"rapidapi", "rapid_api"}:
            return "rapidapi"
        if value in {"api_sports", "apisports", "api_sports_direct", "direct", "official"}:
            return "api_sports_direct"
        return None
    host = _normalized_host(api_host or _get_config_value("API_HOST") or os.environ.get("API_HOST"))
    if host == PROVIDERS["rapidapi"]["endpoint_host"]:
        return "rapidapi"
    if host == PROVIDERS["api_sports_direct"]["endpoint_host"]:
        return "api_sports_direct"
    return None


def _get_api_key(provider: str | None = None) -> tuple[str, str]:
    provider = provider or _detect_provider() or "api_sports_direct"
    for env_name in PROVIDERS.get(provider, {}).get("key_env_candidates", []):
        value = os.environ.get(env_name)
        if value:
            return value, env_name
    # Legacy config.secrets.API_KEY is allowed as local source but never printed raw.
    config_key = _get_config_value("API_KEY")
    if config_key:
        return config_key, "config.secrets.API_KEY"
    for env_name in ["APIFOOTBALL_KEY", "OPENCLAW_APIFOOTBALL_KEY", "RAPIDAPI_KEY", "OPENCLAW_RAPIDAPI_KEY"]:
        value = os.environ.get(env_name)
        if value:
            return value, env_name
    return "", "MISSING"


def mask_key(key: str) -> str:
    if not key:
        return "MISSING"
    if len(key) <= 8:
        return "****"
    digest = hashlib.sha256(key.encode()).hexdigest()[:10]
    return f"{key[:4]}...{key[-4:]}#{digest}"


def resolve_provider_config(api_host: str | None = None, api_key: str | None = None) -> dict[str, Any]:
    host = _normalized_host(api_host or _get_config_value("API_HOST") or os.environ.get("API_HOST"))
    provider = _detect_provider(api_host or host)
    key_source = "argument" if api_key else ""
    key = api_key or ""
    if not key:
        key, key_source = _get_api_key(provider)
    provider_cfg = PROVIDERS.get(provider or "", {})
    expected_host = provider_cfg.get("endpoint_host")
    header_names = list(provider_cfg.get("required_headers", [])) if provider_cfg else []
    provider_mismatch = provider is None
    host_mismatch = bool(expected_host and host != expected_host)
    header_mismatch = provider_mismatch or not header_names
    env_var_names_masked = {
        "provider_env_candidates": ["OPENCLAW_API_PROVIDER", "V4_API_PROVIDER", "API_FOOTBALL_PROVIDER"],
        "key_env_candidates": sorted(set(PROVIDERS["rapidapi"]["key_env_candidates"] + PROVIDERS["api_sports_direct"]["key_env_candidates"] + ["config.secrets.API_KEY"])),
        "active_key_source": key_source,
    }
    return {
        "active_provider": provider,
        "endpoint_host": host,
        "base_url": _base_url_for_host(api_host or host),
        "expected_host": expected_host,
        "header_names": header_names,
        "required_headers": header_names,
        "key": key,
        "key_source": key_source,
        "key_fingerprint": mask_key(key),
        "provider_mismatch": provider_mismatch,
        "host_mismatch": host_mismatch,
        "header_mismatch": header_mismatch,
        "env_var_names_masked": env_var_names_masked,
    }


def _headers_for(config: dict[str, Any]) -> dict[str, str]:
    provider = config.get("active_provider")
    key = config.get("key") or ""
    if provider == "rapidapi":
        return {
            "x-rapidapi-key": key,
            "x-rapidapi-host": PROVIDERS["rapidapi"]["endpoint_host"],
            "User-Agent": "OpenClaw-V4/1.0",
        }
    return {"x-apisports-key": key, "User-Agent": "OpenClaw-V4/1.0"}


def _message_from_payload(payload: Any, body: str = "") -> str:
    chunks: list[str] = []
    if isinstance(payload, dict):
        for key in ["message", "error", "errors"]:
            val = payload.get(key)
            if isinstance(val, str):
                chunks.append(val)
            elif isinstance(val, dict):
                chunks.extend(str(v) for v in val.values())
            elif isinstance(val, list):
                chunks.extend(str(v) for v in val)
        if isinstance(payload.get("response"), str):
            chunks.append(str(payload.get("response")))
    if body:
        chunks.append(body[:500])
    return " | ".join(chunks)


def classify_api_response(http_status: int | None, payload: Any = None, body: str = "") -> str:
    message = _message_from_payload(payload, body).lower()
    if http_status is None:
        return "API_NETWORK_ERROR"
    if http_status == 200:
        if "quota" in message and "exceed" in message:
            return "API_QUOTA_EXCEEDED"
        return "API_OK"
    if http_status == 401:
        return "API_KEY_INVALID"
    if http_status == 403:
        if "not subscribed" in message or "not subscribe" in message or "subscription" in message:
            return "API_FORBIDDEN_NOT_SUBSCRIBED"
        if "invalid" in message or "key" in message:
            return "API_KEY_INVALID"
        return "API_FORBIDDEN_NOT_SUBSCRIBED"
    if http_status == 429:
        return "API_RATE_LIMITED"
    if 500 <= http_status <= 599:
        return "API_NETWORK_ERROR"
    return f"API_HTTP_{http_status}"


def _read_response_body(resp) -> tuple[Any, str]:
    raw = resp.read().decode("utf-8", errors="replace")
    try:
        return json.loads(raw), raw
    except Exception:
        return None, raw


def _urllib_raw_get(endpoint: str, config: dict[str, Any], timeout: int = 8) -> dict[str, Any]:
    url = f"{str(config['base_url']).rstrip('/')}/{endpoint.lstrip('/')}"
    req = urllib.request.Request(url, headers=_headers_for(config))
    try:
        with _IPV4_OPENER.open(req, timeout=timeout) as resp:
            payload, body = _read_response_body(resp)
            return {"http_status": int(resp.status), "payload": payload, "body": body, "url": url, "headers": dict(resp.headers)}
    except urllib.error.HTTPError as e:
        payload, body = _read_response_body(e)
        return {"http_status": int(e.code), "payload": payload, "body": body, "url": url, "headers": dict(e.headers)}
    except Exception as e:
        return {"http_status": None, "payload": None, "body": str(e), "url": url, "headers": {}}


def _curl_raw_get(endpoint: str, config: dict[str, Any], timeout: int = 10) -> dict[str, Any]:
    url = f"{str(config['base_url']).rstrip('/')}/{endpoint.lstrip('/')}"
    cmd = ["curl", "-4", "-s", "-i", "--max-time", str(timeout)]
    for name, value in _headers_for(config).items():
        cmd.extend(["-H", f"{name}: {value}"])
    cmd.append(url)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 5)
        if result.returncode != 0:
            return {"http_status": None, "payload": None, "body": result.stderr[:500], "url": url, "headers": {}}
        head, _, body = result.stdout.partition("\r\n\r\n")
        if not body:
            head, _, body = result.stdout.partition("\n\n")
        status = None
        first = head.splitlines()[0] if head.splitlines() else ""
        if first.startswith("HTTP/"):
            try:
                status = int(first.split()[1])
            except Exception:
                status = None
        try:
            payload = json.loads(body)
        except Exception:
            payload = None
        return {"http_status": status, "payload": payload, "body": body, "url": url, "headers": {}}
    except Exception as e:
        return {"http_status": None, "payload": None, "body": str(e), "url": url, "headers": {}}


def _apply_subscription_block(reason: str) -> None:
    _API_GUARD_STATE["safe_to_scan"] = False
    _API_GUARD_STATE["api_status"] = reason
    _API_GUARD_STATE["circuit_breaker_triggered"] = True
    _API_GUARD_STATE["negative_cache_until"] = time.time() + NEGATIVE_CACHE_TTL_SECONDS
    _API_GUARD_STATE["negative_cache_reason"] = reason


def get_api_guard_snapshot() -> dict[str, Any]:
    snap = dict(_API_GUARD_STATE)
    snap["negative_cache_active"] = time.time() < float(snap.get("negative_cache_until") or 0)
    snap["negative_cache_ttl_seconds"] = NEGATIVE_CACHE_TTL_SECONDS
    return snap


def reset_api_guard_runtime_counters() -> None:
    for key in ["api_calls_attempted", "api_calls_blocked_by_preflight", "api_calls_blocked_by_circuit_breaker", "remote_requests", "forbidden_count", "fallback_count", "consecutive_errors"]:
        _API_GUARD_STATE[key] = 0
    _API_GUARD_STATE["circuit_breaker_triggered"] = False


def api_preflight(date_key: str | None = None, *, api_host: str | None = None, api_key: str | None = None, strict: bool = False, write_status: bool = True) -> dict[str, Any]:
    """Run one active-provider status request and return safe_to_scan decision."""
    config = resolve_provider_config(api_host=api_host, api_key=api_key)
    blockers: list[str] = []
    if config.get("provider_mismatch"):
        blockers.append("API_PROVIDER_MISMATCH")
    if config.get("host_mismatch"):
        blockers.append("API_HOST_MISMATCH")
    if config.get("header_mismatch"):
        blockers.append("API_HEADER_MISMATCH")
    if not config.get("key"):
        blockers.append("API_KEY_MISSING")

    raw = {"http_status": None, "payload": None, "headers": {}, "body": ""}
    if not blockers:
        raw = _urllib_raw_get("status", config, timeout=8)
    api_status = classify_api_response(raw.get("http_status"), raw.get("payload"), raw.get("body", "")) if not blockers else blockers[0]
    if api_status == "API_FORBIDDEN_NOT_SUBSCRIBED":
        _apply_subscription_block(api_status)
    else:
        _API_GUARD_STATE["safe_to_scan"] = api_status == "API_OK"
        _API_GUARD_STATE["api_status"] = api_status
        if api_status != "API_OK" and strict:
            _API_GUARD_STATE["negative_cache_reason"] = api_status

    payload = raw.get("payload") if isinstance(raw.get("payload"), dict) else {}
    account = payload.get("response", {}).get("account", {}) if isinstance(payload.get("response"), dict) else {}
    requests_info = payload.get("response", {}).get("requests", {}) if isinstance(payload.get("response"), dict) else {}
    rate_limit_remaining = None
    quota_remaining = None
    if isinstance(requests_info, dict):
        quota_remaining = requests_info.get("current") or requests_info.get("limit_day") or requests_info.get("remaining")
    result = {
        "schema_version": "v4_api_preflight.v1",
        "generated_at": _now(),
        "date": date_key or datetime.now(CN_TZ).strftime("%Y%m%d"),
        "active_provider": config.get("active_provider"),
        "endpoint_host": config.get("endpoint_host"),
        "expected_host": config.get("expected_host"),
        "header_names": config.get("header_names"),
        "key_fingerprint": config.get("key_fingerprint"),
        "key_source": config.get("key_source"),
        "http_status": raw.get("http_status"),
        "api_status": api_status,
        "subscription_ok": api_status == "API_OK",
        "quota_remaining": quota_remaining,
        "rate_limit_remaining": rate_limit_remaining,
        "provider_mismatch": bool(config.get("provider_mismatch")),
        "host_mismatch": bool(config.get("host_mismatch")),
        "header_mismatch": bool(config.get("header_mismatch")),
        "safe_to_scan": api_status == "API_OK",
        "safe_to_scan_false_blocks_remote": api_status != "API_OK",
        "request_count": 1 if not blockers else 0,
        "secret_printed": False,
        "blockers": blockers,
        "guard_state": get_api_guard_snapshot(),
    }
    if write_status:
        out = STATUS_DIR / f"v4_api_preflight_{result['date']}.json"
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def _guard_allows_remote() -> bool:
    if time.time() < float(_API_GUARD_STATE.get("negative_cache_until") or 0):
        _API_GUARD_STATE["api_calls_blocked_by_circuit_breaker"] += 1
        return False
    if _API_GUARD_STATE.get("safe_to_scan") is False:
        _API_GUARD_STATE["api_calls_blocked_by_preflight"] += 1
        return False
    if bool(_API_GUARD_STATE.get("circuit_breaker_triggered")):
        _API_GUARD_STATE["api_calls_blocked_by_circuit_breaker"] += 1
        return False
    if int(_API_GUARD_STATE.get("remote_requests") or 0) >= int(_API_GUARD_STATE.get("max_remote_requests") or 0):
        _API_GUARD_STATE["api_calls_blocked_by_circuit_breaker"] += 1
        _API_GUARD_STATE["circuit_breaker_triggered"] = True
        _API_GUARD_STATE["api_status"] = "API_REQUEST_BUDGET_EXCEEDED"
        return False
    return True


def api_get(endpoint: str, api_key: Optional[str] = None, api_host: str = "https://v3.football.api-sports.io", retries: int = 3) -> Optional[dict]:
    """Provider-aware API request with request budget and 403 fail-fast.

    Returns API JSON or None. Subscription 403 is terminal: no retry, no curl.
    """
    _API_GUARD_STATE["api_calls_attempted"] += 1
    if not _guard_allows_remote():
        logger.error("[GUARD] API_CREDENTIAL_BLOCKED | remote request blocked before endpoint=%s", endpoint[:80])
        return None

    config = resolve_provider_config(api_host=api_host, api_key=api_key)
    if config.get("provider_mismatch") or config.get("host_mismatch") or config.get("header_mismatch") or not config.get("key"):
        _apply_subscription_block("API_PROVIDER_OR_HEADER_BLOCKED")
        logger.error("[GUARD] API_PROVIDER_OR_HEADER_BLOCKED | host=%s provider=%s", config.get("endpoint_host"), config.get("active_provider"))
        return None

    _rpm_wait()
    time.sleep(0.03)
    _API_GUARD_STATE["remote_requests"] += 1
    raw = _urllib_raw_get(endpoint, config, timeout=8)
    status = classify_api_response(raw.get("http_status"), raw.get("payload"), raw.get("body", ""))
    if status == "API_OK":
        _API_GUARD_STATE["consecutive_errors"] = 0
        return raw.get("payload") if isinstance(raw.get("payload"), dict) else None
    if status == "API_FORBIDDEN_NOT_SUBSCRIBED":
        _API_GUARD_STATE["forbidden_count"] += 1
        _apply_subscription_block(status)
        logger.error("[GUARD] API_FORBIDDEN_FAIL_FAST | no_retry no_curl endpoint=%s", endpoint[:80])
        return None
    if status in {"API_KEY_INVALID", "API_PROVIDER_MISMATCH", "API_HOST_MISMATCH"}:
        _apply_subscription_block(status)
        return None

    _API_GUARD_STATE["consecutive_errors"] += 1
    if int(_API_GUARD_STATE["consecutive_errors"]) >= int(_API_GUARD_STATE["max_consecutive_errors"]):
        _API_GUARD_STATE["circuit_breaker_triggered"] = True
        _API_GUARD_STATE["api_status"] = "API_CONSECUTIVE_ERROR_BUDGET_EXCEEDED"
        return None

    # Only network/5xx style failures may curl fallback once; subscription 403 never reaches here.
    if status == "API_NETWORK_ERROR" and retries > 0:
        _API_GUARD_STATE["fallback_count"] += 1
        curl_raw = _curl_raw_get(endpoint, config, timeout=10)
        curl_status = classify_api_response(curl_raw.get("http_status"), curl_raw.get("payload"), curl_raw.get("body", ""))
        if curl_status == "API_OK":
            _API_GUARD_STATE["consecutive_errors"] = 0
            return curl_raw.get("payload") if isinstance(curl_raw.get("payload"), dict) else None
        if curl_status == "API_FORBIDDEN_NOT_SUBSCRIBED":
            _API_GUARD_STATE["forbidden_count"] += 1
            _apply_subscription_block(curl_status)
            return None
    return None
