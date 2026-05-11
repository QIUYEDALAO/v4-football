"""
V4 多源赔率适配器 — Sbobet / Bet365 (via odds-api.io)
=========================================================
限 free tier: 每小时100次, 最多2家, Bet365 + Sbobet

用法:
  from engine.odds_io_adapter import fetch_fulltime_totals
  lines = fetch_fulltime_totals(fixture_id)

输出结构:
  [{"bookmaker": "Sbobet", "line": 1.5, "over": 1.55, "under": 2.53}, ...]
"""

from __future__ import annotations

import json, ssl, certifi, time, logging, os
import urllib.request
from pathlib import Path
from datetime import datetime

logger = logging.getLogger("V4_OddsIO")

import os

try:
    from config.secrets import ODDS_IO_API_KEY
except (ImportError, RuntimeError):
    ODDS_IO_API_KEY = os.environ.get("ODDS_IO_API_KEY", "")

API_BASE = "https://api.odds-api.io/v3"
BOOKMAKERS = "Bet365,Sbobet"
CTX = ssl.create_default_context(cafile=certifi.where())

# 限流
_last_call = 0.0
MIN_INTERVAL = 0.8  # 每小时100次 => ~1次/36秒, 单次访问保守0.8s间隔


def _throttle():
    global _last_call
    elapsed = time.monotonic() - _last_call
    if elapsed < MIN_INTERVAL:
        time.sleep(MIN_INTERVAL - elapsed)
    _last_call = time.monotonic()


def _api_get(url: str) -> dict | list | None:
    _throttle()
    req = urllib.request.Request(url, headers={"User-Agent": "V4-Football-Quant/1.0"})
    try:
        with urllib.request.urlopen(req, context=CTX, timeout=10) as resp:
            return json.loads(resp.read())
    except Exception as e:
        logger.warning(f"[OddsIO] {e}")
        return None


def fetch_fulltime_totals(api_football_fixture_id: int) -> list[dict]:
    """
    拉取全场大小球盘口。返回按 bookmaker + line 聚合的结果。
    api_football_fixture_id 直接用 API-Football event id 即可。
    """
    key = ODDS_IO_API_KEY
    if not key:
        logger.warning("[OddsIO] ODDS_IO_API_KEY not set")
        return []

    url = f"{API_BASE}/odds?apiKey={key}&eventId={api_football_fixture_id}&bookmakers={BOOKMAKERS}&oddsFormat=decimal"
    resp = _api_get(url)
    if not resp or not isinstance(resp, dict):
        return []

    bms = resp.get("bookmakers", {})
    if not bms:
        return []

    lines = []
    for bm_name, markets in bms.items():
        if not isinstance(markets, list):
            continue
        for mk in markets:
            if mk.get("name") != "Totals":
                continue
            for odd in mk.get("odds", []):
                hdp = odd.get("hdp")
                over = odd.get("over")
                under = odd.get("under")
                if hdp is not None and over is not None:
                    lines.append({
                        "bookmaker": bm_name,
                        "line": float(hdp),
                        "over": float(over),
                        "under": float(under) if under else None,
                    })
    return lines


def fetch_pre_match_snapshot(api_football_fixture_id: int) -> dict:
    """
    拉取全场大小球 + 亚盘让球快照。用于赛后复盘/历史对比。
    """
    key = ODDS_IO_API_KEY
    if not key:
        return {"error": "ODDS_IO_API_KEY not set"}

    url = f"{API_BASE}/odds?apiKey={key}&eventId={api_football_fixture_id}&bookmakers={BOOKMAKERS}&oddsFormat=decimal"
    resp = _api_get(url)
    if not resp or not isinstance(resp, dict):
        return {"error": "API_ERROR"}

    bms = resp.get("bookmakers", {})
    snapshot = {
        "fixture_id": api_football_fixture_id,
        "captured_at": datetime.now().isoformat(),
        "home": resp.get("home", ""),
        "away": resp.get("away", ""),
        "status": resp.get("status", ""),
        "bookmakers": {},
    }

    for bm_name, markets in bms.items():
        if not isinstance(markets, list):
            continue
        entry = []
        for mk in markets:
            entry.append({"name": mk.get("name"), "odds": mk.get("odds", [])})
        if entry:
            snapshot["bookmakers"][bm_name] = entry

    return snapshot
