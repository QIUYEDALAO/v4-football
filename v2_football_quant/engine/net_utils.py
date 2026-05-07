"""
共享网络工具 — 统一 SSL 上下文
==============================
解决 macOS Python 证书链不完整导致 CERT_NONE 触发 API-Football 403 的问题。
使用 certifi 提供正确 CA 证书。

用法:
  from net_utils import SSL_CTX, api
"""

import ssl
import json
import time
import urllib.request
from typing import Optional

try:
    import certifi
    SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    SSL_CTX = ssl.create_default_context()
    SSL_CTX.check_hostname = False
    SSL_CTX.verify_mode = ssl.CERT_NONE


def api(endpoint: str, api_key: str, api_host: str = "https://v3.football.api-sports.io") -> Optional[dict]:
    url = f"{api_host}/{endpoint}"
    req = urllib.request.Request(url, headers={
        "x-apisports-key": api_key,
        "User-Agent": "Mozilla/5.0"
    })
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, context=SSL_CTX, timeout=15) as resp:
                return json.loads(resp.read())
        except Exception:
            if attempt < 2:
                time.sleep(2 ** attempt)
    return None
