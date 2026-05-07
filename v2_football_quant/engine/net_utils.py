"""
共享网络工具 — 统一 SSL + curl 兜底
=====================================
解决 Python urllib TLS 指纹被 API-Football 防火墙封杀的 403 问题。

策略:
  1. 先尝试 Python urllib + certifi
  2. 403 或 SSL 错误 → 自动回退 subprocess + curl
  3. curl 经过 macOS 原生 TLS 栈，不会被封

用法:
  from engine.net_utils import api_get
  data = api_get("fixtures?date=2026-05-08")
"""

import json
import ssl
import time
import subprocess
import urllib.request
import urllib.error
from typing import Optional


def _get_api_key() -> str:
    try:
        from config.secrets import API_KEY
        return API_KEY
    except Exception:
        return os.getenv("APIFOOTBALL_KEY", "")

# ── Python urllib (优先尝试) ──
try:
    import certifi
    _SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    _SSL_CTX = ssl.create_default_context()
    _SSL_CTX.check_hostname = False
    _SSL_CTX.verify_mode = ssl.CERT_NONE


def _urllib_get(endpoint: str, api_key: str, api_host: str = "https://v3.football.api-sports.io") -> Optional[dict]:
    """Python urllib 请求 (可能被 403)"""
    url = f"{api_host}/{endpoint}"
    req = urllib.request.Request(url, headers={
        "x-apisports-key": api_key,
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    })
    try:
        with urllib.request.urlopen(req, context=_SSL_CTX, timeout=15) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        if e.code == 403:
            return None  # 触发 curl 回退
        raise
    except Exception:
        return None


def _curl_get(endpoint: str, api_key: str, api_host: str = "https://v3.football.api-sports.io") -> Optional[dict]:
    """subprocess + curl 兜底 (TLS 指纹不会被封)"""
    url = f"{api_host}/{endpoint}"
    try:
        result = subprocess.run(
            ["curl", "-s", "--max-time", "15", "-H", f"x-apisports-key: {api_key}", url],
            capture_output=True, text=True, timeout=20
        )
        if result.returncode != 0:
            return None
        return json.loads(result.stdout)
    except Exception:
        return None


def api_get(endpoint: str, api_key: str = None, api_host: str = "https://v3.football.api-sports.io",
            retries: int = 3) -> Optional[dict]:
    """智能 API 请求: urllib 优先, 403 自动回退 curl"""
    if not api_key:
        try:
            from config.secrets import API_KEY
            api_key = API_KEY
        except Exception:
            return None

    for attempt in range(retries):
        # 先试 urllib
        result = _urllib_get(endpoint, api_key, api_host)
        if result is not None:
            return result

        # urllib 被 403 → 回退 curl
        if attempt == 0:
            pass  # 第一次就触发回退

        result = _curl_get(endpoint, api_key, api_host)
        if result is not None:
            return result

        if attempt < retries - 1:
            time.sleep(2 ** attempt)

    return None
