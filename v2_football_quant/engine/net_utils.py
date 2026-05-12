"""
共享网络工具 — 统一 SSL + curl 兜底
=====================================
解决 Python urllib TLS 指纹被 API-Football 防火墙封杀的 403 问题。

策略:
  1. 先尝试 Python urllib + certifi (重试 1 次)
  2. 403 或 5xx → 自动回退 subprocess + curl
  3. curl 经过 macOS 原生 TLS 栈，不会被封
  4. [GUARD] 日志记录所有 fallback 和 hard fail

用法:
  from engine.net_utils import api_get
  data = api_get("fixtures?date=2026-05-08")
"""

import json
import os
import ssl
import time
import logging
import subprocess
import urllib.request
import urllib.error
from typing import Optional

logger = logging.getLogger(__name__)


def _get_api_key() -> str:
    try:
        from config.secrets import API_KEY
        return API_KEY
    except Exception:
        return os.environ.get("APIFOOTBALL_KEY", "")

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
        "User-Agent": "V2-Football-Quant/1.0"
    })
    try:
        with urllib.request.urlopen(req, context=_SSL_CTX, timeout=15) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        if e.code == 403:
            logger.warning(f"[GUARD] API_URLLIB_403 | url={url} code=403")
            return None
        logger.error(f"[GUARD] API_URLLIB_HTTPERROR | url={url} code={e.code}")
        return None
    except Exception as e:
        logger.error(f"[GUARD] API_URLLIB_EXCEPTION | url={url} err={e}")
        return None


def _curl_get(endpoint: str, api_key: str, api_host: str = "https://v3.football.api-sports.io") -> Optional[dict]:
    """subprocess + curl 兜底 (TLS 指纹不会被封)"""
    url = f"{api_host}/{endpoint}"
    try:
        result = subprocess.run(
            ["curl", "-s", "--max-time", "15",
             "-H", f"x-apisports-key: {api_key}",
             "-H", "User-Agent: V2-Football-Quant/1.0", url],
            capture_output=True, text=True, timeout=20
        )
        if result.returncode != 0:
            logger.error(f"[GUARD] API_CURL_RETERR | url={url} code={result.returncode} stderr={result.stderr[:200]}")
            return None
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as e:
            logger.error(f"[GUARD] API_CURL_JSONERR | url={url} err={e} raw={result.stdout[:200]}")
            return None
    except Exception as e:
        logger.error(f"[GUARD] API_CURL_EXCEPTION | url={url} err={e}")
        return None


def api_get(endpoint: str, api_key: Optional[str] = None,
            api_host: str = "https://v3.football.api-sports.io",
            retries: int = 3) -> Optional[dict]:
    """智能 API 请求: urllib 优先 (重试1次), 403/5xx 自动回退 curl"""
    if not api_key:
        api_key = _get_api_key()
        if not api_key:
            logger.error("[GUARD] API_NO_KEY | 无法获取 API Key")
            return None

    # ── 阶段 1: urllib (主路径, 重试) ──
    urllib_fail_reason = None
    for attempt in range(2):  # urllib 最多2次
        result = _urllib_get(endpoint, api_key, api_host)
        if result is not None:
            return result  # ✅ 成功
        if attempt < 1:
            time.sleep(0.5)  # 重试前等待
    urllib_fail_reason = "403_or_5xx"

    # ── 阶段 2: curl 兜底 ──
    logger.warning(f"[GUARD] API_FALLBACK | code=HTTP_403_URLLIB → fallback=curl | path=/{endpoint[:60]}")

    for attempt in range(retries):
        result = _curl_get(endpoint, api_key, api_host)
        if result is not None:
            return result  # ✅ curl 救回来了
        if attempt < retries - 1:
            time.sleep(2 ** attempt)

    # ── 阶段 3: 双路全灭 ──
    logger.error(f"[GUARD] API_HARD_FAIL | path=/{endpoint[:80]} | reason='{urllib_fail_reason} + curl_fail'")
    return None
