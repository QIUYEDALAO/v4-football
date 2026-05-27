#!/usr/bin/env python3
"""
v4_outside57_scanner.py — outside_57 全量并行扫描引擎
=======================================================
将 outside_57 从逐场串行 I/O 架构改为并行架构：

  fixture worker pool (默认8 workers)
  + 单场内部并发 fetch (H2H / home recent / away recent 并行)
  + 全局 API RPM limiter (默认290, 硬上限300)
  + 全局 in-flight semaphore (max 30)
  + HTTP session 复用 (requests.Session)
  + team recent / H2H / event 独立缓存
  + timeout / retry with exponential backoff
  + progress marker / resume 断点续跑
  + 全量覆盖保证 (每场都有最终状态)

用法:
  python3 engine/v4_outside57_scanner.py
  python3 engine/v4_outside57_scanner.py --workers 8 --api-rpm 290 --max-inflight 30
  python3 engine/v4_outside57_scanner.py --resume --run-id outside57_20260527_001

BOSS 约束:
  - 不得减少 fixture 数量
  - 不得 topN 替代全量
  - 不得跳过 H2H / recent form（必须保持最近10场）
  - 不得突破 300 RPM / 30 in-flight
  - 不得写入 official candidate / validation / live bet / QQ
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import threading
import hashlib
import traceback
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeoutError
from datetime import datetime, timedelta, date, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

# ── project path setup ──
BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))
ENGINE_DIR = BASE_DIR / "engine"
STATUS_DIR = BASE_DIR / "data" / "runtime" / "status"
CACHE_DIR = BASE_DIR / "data" / "runtime" / "outside57_cache"
STATUS_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# ── import engine modules (after path setup) ──
from engine.net_utils import _get_config_value as get_secret, _SSL_CTX
from engine.data_sources.h2h_engine import evaluate_h2h_edge, warm_recent_goal_profiles, reset_recent_profile_cache_stats
from engine.v4_match_intelligence import build_ht_recommendation
from engine.v4_runner import fetch_today_fixtures, _capture_ht_ou_lines, _best_pre_live_line

# ── constants ──
API_HOST = get_secret("API_HOST") or "v3.football.api-sports.io"
API_KEY = get_secret("API_KEY") or ""
CN_TZ = timezone(timedelta(hours=8))

OUTSIDE57_MARKER = {
    "outside57": True,
    "full_scan": True,
    "official_candidate": False,
    "not_for_validation": True,
    "not_for_live_bet": True,
    "not_for_qq_recommendation": True,
}


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  GLOBAL RATE LIMITER                                                        ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

class RateLimiter:
    """线程安全的 60 秒滑动窗口 RPM 限速器。"""

    def __init__(self, rpm_target: int = 290, rpm_hard_cap: int = 300):
        self.rpm_target = rpm_target
        self.rpm_hard_cap = rpm_hard_cap
        self._lock = threading.Lock()
        self._window: deque[float] = deque()
        self.rpm_peak_60s = 0
        self.rate_limited_count = 0
        self.backoff_count = 0
        self.http_429_count = 0

    def acquire(self) -> None:
        """在发起 API 请求前调用，必要时等待。"""
        with self._lock:
            now = time.time()
            cutoff = now - 60
            while self._window and self._window[0] < cutoff:
                self._window.popleft()

            current_rpm = len(self._window)
            if current_rpm > self.rpm_peak_60s:
                self.rpm_peak_60s = current_rpm

            # 接近 hard cap 时强制等待
            if current_rpm >= self.rpm_hard_cap:
                wait_s = 60 - (now - self._window[0]) + 0.5
                if wait_s > 0:
                    self.backoff_count += 1
                    time.sleep(wait_s)
                    # 重新清理窗口
                    now = time.time()
                    cutoff = now - 60
                    while self._window and self._window[0] < cutoff:
                        self._window.popleft()

            # 接近 target 时轻微等待
            elif current_rpm >= self.rpm_target:
                self.rate_limited_count += 1
                oldest = self._window[0]
                wait_s = (oldest + 60 - now) / max(1, self.rpm_hard_cap - current_rpm) + 0.05
                if wait_s > 0:
                    time.sleep(min(wait_s, 2.0))

            self._window.append(time.time())
            if len(self._window) > self.rpm_peak_60s:
                self.rpm_peak_60s = len(self._window)

    def record_429(self) -> None:
        """记录 429 响应并强制 backoff。"""
        with self._lock:
            self.http_429_count += 1
            self.backoff_count += 1
        backoff = min(2 ** min(self.http_429_count, 6), 120)
        time.sleep(backoff)

    def snapshot(self) -> dict:
        with self._lock:
            now = time.time()
            cutoff = now - 60
            current = sum(1 for t in self._window if t >= cutoff)
            return {
                "rpm_target": self.rpm_target,
                "rpm_hard_cap": self.rpm_hard_cap,
                "rpm_current_60s": current,
                "rpm_peak_60s": self.rpm_peak_60s,
                "rate_limited_count": self.rate_limited_count,
                "backoff_count": self.backoff_count,
                "http_429_count": self.http_429_count,
            }


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  GLOBAL IN-FLIGHT SEMAPHORE                                                 ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

class InFlightLimiter:
    """全局同时在途 API 请求上限（信号量）。"""

    def __init__(self, max_inflight: int = 30):
        self.max_inflight = max_inflight
        self._semaphore = threading.Semaphore(max_inflight)
        self.peak_inflight_requests = 0
        self.semaphore_wait_count = 0
        self.semaphore_timeout_count = 0
        self._lock = threading.Lock()
        self._current = 0

    def acquire(self, timeout: float = 30.0) -> bool:
        """获取信号量；超时返回 False。"""
        self.semaphore_wait_count += 1
        acquired = self._semaphore.acquire(timeout=timeout)
        if acquired:
            with self._lock:
                self._current += 1
                if self._current > self.peak_inflight_requests:
                    self.peak_inflight_requests = self._current
        else:
            self.semaphore_timeout_count += 1
        return acquired

    def release(self) -> None:
        """释放信号量。"""
        with self._lock:
            self._current = max(0, self._current - 1)
        self._semaphore.release()

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "max_inflight_requests": self.max_inflight,
                "peak_inflight_requests": self.peak_inflight_requests,
                "semaphore_wait_count": self.semaphore_wait_count,
                "semaphore_timeout_count": self.semaphore_timeout_count,
                "current_inflight": self._current,
            }


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  OUTSIDE57 CACHE                                                            ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

class Outside57Cache:
    """outside_57 独立缓存（文件级），不污染 official scan 缓存。"""

    def __init__(self):
        self.hits = 0
        self.misses = 0
        self.h2h_hits = 0
        self.recent_hits = 0
        self.event_hits = 0
        self.errors = 0
        self._lock = threading.Lock()

    def _cache_path(self, namespace: str, key: str) -> Path:
        h = hashlib.sha256(key.encode()).hexdigest()[:32]
        return CACHE_DIR / f"{namespace}_{h}.json"

    def get(self, namespace: str, key: str, ttl_hours: float) -> Optional[dict]:
        """读取缓存；TTL 过期返回 None。"""
        p = self._cache_path(namespace, key)
        if not p.exists():
            with self._lock:
                self.misses += 1
            return None
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            cached_at = data.get("_cached_at", 0)
            if time.time() - cached_at > ttl_hours * 3600:
                with self._lock:
                    self.misses += 1
                return None
            with self._lock:
                self.hits += 1
                if namespace == "h2h":
                    self.h2h_hits += 1
                elif namespace == "recent":
                    self.recent_hits += 1
                elif namespace == "event":
                    self.event_hits += 1
            return data.get("_payload")
        except Exception:
            with self._lock:
                self.errors += 1
            return None

    def put(self, namespace: str, key: str, payload: Any, is_error: bool = False) -> None:
        """写入缓存（atomic write）。API_TIMEOUT 不缓存。"""
        if is_error:
            return  # 不缓存 error/timeout
        p = self._cache_path(namespace, key)
        tmp = p.with_suffix(".tmp")
        try:
            data = {
                "_cached_at": time.time(),
                "_namespace": namespace,
                "_key_hash": hashlib.sha256(key.encode()).hexdigest()[:16],
                "_payload": payload,
            }
            tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            tmp.replace(p)  # atomic on POSIX
        except Exception:
            with self._lock:
                self.errors += 1
            if tmp.exists():
                try:
                    tmp.unlink()
                except Exception:
                    pass

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "cache_hits": self.hits,
                "cache_misses": self.misses,
                "h2h_cache_hits": self.h2h_hits,
                "recent_form_cache_hits": self.recent_hits,
                "event_cache_hits": self.event_hits,
                "cache_errors": self.errors,
            }


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  THREAD-SAFE API CLIENT                                                     ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

class Outside57ApiClient:
    """线程安全的 API 客户端，集成 rate limiter / semaphore / cache / session。"""

    def __init__(
        self,
        rate_limiter: RateLimiter,
        inflight_limiter: InFlightLimiter,
        cache: Outside57Cache,
        timeout_sec: int = 12,
        retry_max: int = 2,
    ):
        self.rate_limiter = rate_limiter
        self.inflight_limiter = inflight_limiter
        self.cache = cache
        self.timeout_sec = timeout_sec
        self.retry_max = retry_max
        self._session_local = threading.local()
        self.api_request_count = 0
        self._count_lock = threading.Lock()

    def _get_session(self) -> requests.Session:
        if not hasattr(self._session_local, "session"):
            s = requests.Session()
            s.headers.update({
                "x-apisports-key": API_KEY,
                "Accept": "application/json",
            })
            adapter = requests.adapters.HTTPAdapter(
                pool_connections=10,
                pool_maxsize=30,
                max_retries=0,
            )
            s.mount("https://", adapter)
            self._session_local.session = s
        return self._session_local.session

    def _build_url(self, endpoint: str) -> str:
        endpoint = endpoint.lstrip("/")
        host = API_HOST
        if host.startswith("https://"):
            host = host[len("https://"):]
        elif host.startswith("http://"):
            host = host[len("http://"):]
        return f"https://{host}/{endpoint}"

    def call(self, endpoint: str) -> dict | None:
        """线程安全的 API 调用，带 rate limiting / semaphore / retry。"""
        # rate limiter
        self.rate_limiter.acquire()

        # in-flight semaphore
        if not self.inflight_limiter.acquire(timeout=30.0):
            return None  # semaphore timeout — 视为失败

        try:
            with self._count_lock:
                self.api_request_count += 1

            url = self._build_url(endpoint)
            session = self._get_session()

            last_error = None
            for attempt in range(self.retry_max + 1):
                try:
                    resp = session.get(url, timeout=self.timeout_sec)
                    if resp.status_code == 429:
                        self.rate_limiter.record_429()
                        continue
                    if resp.status_code == 403:
                        return None  # 不重试
                    if resp.status_code >= 500:
                        last_error = f"HTTP_{resp.status_code}"
                        backoff = min(2 ** attempt, 8)
                        time.sleep(backoff)
                        continue
                    resp.raise_for_status()
                    return resp.json()
                except requests.exceptions.Timeout:
                    last_error = "API_TIMEOUT"
                    backoff = min(2 ** attempt, 8)
                    self.rate_limiter.record_429()
                    time.sleep(backoff)
                except requests.exceptions.ConnectionError:
                    last_error = "API_CONNECTION_ERROR"
                    backoff = min(2 ** attempt, 8)
                    time.sleep(backoff)
                except Exception as e:
                    last_error = f"API_ERROR:{type(e).__name__}"
                    backoff = min(2 ** attempt, 8)
                    time.sleep(backoff)

            return None  # 所有重试耗尽
        finally:
            self.inflight_limiter.release()


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  CACHE-AWARE API FETCH HELPERS                                              ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

def _cached_h2h(api: Outside57ApiClient, home_id: int, away_id: int, date_str: str) -> dict:
    """缓存感知的 H2H 查询。"""
    pair_key = f"{min(home_id, away_id)}_{max(home_id, away_id)}"
    cache_key = f"h2h_{pair_key}_{date_str}_v1"
    cached = api.cache.get("h2h", cache_key, ttl_hours=24)
    if cached is not None:
        return cached
    result = api.call(f"fixtures/headtohead?h2h={home_id}-{away_id}")
    api.cache.put("h2h", cache_key, result)
    return result


def _cached_recent_form(api: Outside57ApiClient, team_id: int, last_n: int, date_str: str) -> dict:
    """缓存感知的球队近期战绩查询。"""
    cache_key = f"recent_{team_id}_{last_n}_{date_str}_v1"
    cached = api.cache.get("recent", cache_key, ttl_hours=12)
    if cached is not None:
        return cached
    result = api.call(f"fixtures?team={team_id}&last={last_n}&status=FT")
    api.cache.put("recent", cache_key, result)
    return result


def _cached_events(api: Outside57ApiClient, fixture_id: int) -> dict:
    """缓存感知的 events 查询。"""
    cache_key = f"event_{fixture_id}_v1"
    cached = api.cache.get("event", cache_key, ttl_hours=24)
    if cached is not None:
        return cached
    result = api.call(f"fixtures/events?fixture={fixture_id}")
    api.cache.put("event", cache_key, result)
    return result


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  PER-FIXTURE PARALLEL FETCH + SCORE                                         ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

def _process_one_fixture(
    fx: dict,
    api: Outside57ApiClient,
    scan_date_str: str,
    scan_mode: str = "full",
) -> dict:
    """单场 complete 处理：并行 fetch + score + isolation markers。"""
    fixture_id = fx["id"]
    home_id = fx["homeId"]
    away_id = fx["awayId"]
    result_base = {
        "fixture_id": fixture_id,
        "home_team": fx["home"],
        "away_team": fx["away"],
        "league_id": fx["league"],
        "league_name": fx["league_name"],
        "country": fx.get("country"),
        "kickoff_time": fx["kickoff"],
        **OUTSIDE57_MARKER,
        "processed_at": datetime.now(CN_TZ).isoformat(),
    }

    # ── 单场内部并发 fetch ──
    fetch_results = {}
    fetch_errors = []

    def _do_h2h():
        try:
            return ("h2h", _cached_h2h(api, home_id, away_id, scan_date_str))
        except Exception as e:
            fetch_errors.append(f"H2H_fetch_error:{e}")
            return ("h2h", None)

    def _do_home_recent():
        try:
            return ("home_recent", _cached_recent_form(api, home_id, 10, scan_date_str))
        except Exception as e:
            fetch_errors.append(f"home_recent_fetch_error:{e}")
            return ("home_recent", None)

    def _do_away_recent():
        try:
            return ("away_recent", _cached_recent_form(api, away_id, 10, scan_date_str))
        except Exception as e:
            fetch_errors.append(f"away_recent_fetch_error:{e}")
            return ("away_recent", None)

    def _do_odds():
        try:
            return ("odds", api.call(f"odds?fixture={fixture_id}"))
        except Exception as e:
            fetch_errors.append(f"odds_fetch_error:{e}")
            return ("odds", None)

    # 并行执行 H2H + home recent + away recent + odds
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {
            pool.submit(_do_h2h): "h2h",
            pool.submit(_do_home_recent): "home_recent",
            pool.submit(_do_away_recent): "away_recent",
            pool.submit(_do_odds): "odds",
        }
        for future in as_completed(futures, timeout=35):
            try:
                key, val = future.result()
                fetch_results[key] = val
            except FuturesTimeoutError:
                fetch_errors.append(f"{futures[future]}_timeout")
            except Exception as e:
                fetch_errors.append(f"{futures[future]}_error:{e}")

    # ── 使用现有引擎评分 ──
    # 构建简化的 api_client wrapper 给 evaluate_h2h_edge
    # evaluate_h2h_edge 内部会调用 api_client 获取 H2H / recent / events
    # 我们需要注入缓存过的数据

    h2h_result = None
    scoring_error = None

    try:
        # 对 evaluate_h2h_edge 的调用：需要原始 API 响应格式
        def engine_api_client(endpoint: str) -> dict | None:
            """适配器：把 endpoint 路由到缓存或 API。"""
            ep_lower = endpoint.lower()
            if "headtohead" in ep_lower:
                return fetch_results.get("h2h")
            if f"team={home_id}" in ep_lower and "last=" in ep_lower:
                return fetch_results.get("home_recent")
            if f"team={away_id}" in ep_lower and "last=" in ep_lower:
                return fetch_results.get("away_recent")
            if "events" in ep_lower:
                # 解析 fixture id
                m = re.search(r'fixture=(\d+)', endpoint)
                if m:
                    return _cached_events(api, int(m.group(1)))
                return None
            return api.call(endpoint)

        h2h_result = evaluate_h2h_edge(
            home_id,
            away_id,
            engine_api_client,
            mode=scan_mode,
            current_league_id=fx["league"],
            current_league_name=fx["league_name"],
            current_country=fx.get("country"),
        )

        # 评分
        odds_lines = _capture_ht_ou_lines(fetch_results.get("odds") or {})
        best_line = _best_pre_live_line(odds_lines)

        recommendation = build_ht_recommendation(h2h_result)

        result_base.update({
            "status": "DONE",
            "grade": recommendation.get("grade", "SKIP"),
            "ht_score": h2h_result.get("metrics", {}).get("ht_raw_score"),
            "h2h_valid": h2h_result.get("valid", False),
            "h2h_reason": h2h_result.get("reason", ""),
            "prematch_line": best_line.get("line") if best_line else None,
            "prematch_over_odds": best_line.get("over") if best_line else None,
            "prematch_under_odds": best_line.get("under") if best_line else None,
            "api_coverage_level": h2h_result.get("metrics", {}).get("official_h2h_count", 0),
            "is_candidate": recommendation.get("grade", "SKIP") in ("A", "B"),
            "candidate_score": recommendation.get("fit", ""),
            "h2h_official_count": h2h_result.get("metrics", {}).get("official_h2h_count", 0),
            "h2h_sample_category": h2h_result.get("metrics", {}).get("h2h_sample_category", ""),
            "recent_form_low_sample": h2h_result.get("metrics", {}).get("recent_form_low_sample", False),
            "recommendation_summary": recommendation.get("summary", ""),
            "fetch_errors": fetch_errors if fetch_errors else None,
        })
    except Exception as e:
        scoring_error = f"score_error:{type(e).__name__}:{e}"
        result_base.update({
            "status": "SCORE_ERROR",
            "grade": "SKIP",
            "scoring_error": scoring_error,
            "fetch_errors": fetch_errors if fetch_errors else None,
        })

    # ── 补充缓存统计 ──
    result_base["_cache_stats"] = api.cache.snapshot()

    return result_base


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  PROGRESS MARKER / RESUME                                                   ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

class ProgressMarker:
    """断点续跑进度文件（atomic write）。"""

    def __init__(self, run_id: str):
        self.run_id = run_id
        self.path = STATUS_DIR / f"v4_outside57_progress_{run_id}.json"
        self._lock = threading.Lock()
        self.done_fixture_ids: set[int] = set()
        self.failed_fixture_ids: dict[int, str] = {}  # fixture_id -> reason

    def load(self) -> None:
        """加载已有进度。"""
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                self.done_fixture_ids = set(data.get("done_fixture_ids", []))
                self.failed_fixture_ids = {int(k): v for k, v in data.get("failed_fixture_ids", {}).items()}
            except Exception:
                pass

    def mark_done(self, fixture_id: int) -> None:
        """标记 fixture 已完成。"""
        with self._lock:
            self.done_fixture_ids.add(fixture_id)
        self._write()

    def mark_failed(self, fixture_id: int, reason: str) -> None:
        """标记 fixture 失败。"""
        with self._lock:
            self.failed_fixture_ids[fixture_id] = reason
        self._write()

    def is_done(self, fixture_id: int) -> bool:
        return fixture_id in self.done_fixture_ids

    def _write(self) -> None:
        """atomic write 进度文件。"""
        tmp = self.path.with_suffix(".tmp")
        data = {
            "run_id": self.run_id,
            "updated_at": datetime.now(CN_TZ).isoformat(),
            "done_count": len(self.done_fixture_ids),
            "failed_count": len(self.failed_fixture_ids),
            "done_fixture_ids": sorted(list(self.done_fixture_ids)),
            "failed_fixture_ids": {str(k): v for k, v in self.failed_fixture_ids.items()},
        }
        tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.path)


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  MAIN SCANNER                                                               ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

def run_outside57_scan(
    workers: int = 8,
    worker_max: int = 12,
    api_rpm: int = 290,
    api_rpm_hard_cap: int = 300,
    max_inflight: int = 30,
    api_timeout_sec: int = 12,
    fixture_timeout_sec: int = 35,
    retry_max: int = 2,
    resume: bool = False,
    run_id: str | None = None,
    scan_mode: str = "full",
    scan_date_str: str | None = None,
) -> dict:
    """outside_57 并行全量扫描主入口。"""
    t_start = time.perf_counter()

    if run_id is None:
        run_id = f"outside57_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    if scan_date_str is None:
        scan_date_str = datetime.now().strftime("%Y%m%d")

    # ── 初始化组件 ──
    rate_limiter = RateLimiter(rpm_target=api_rpm, rpm_hard_cap=api_rpm_hard_cap)
    inflight_limiter = InFlightLimiter(max_inflight=max_inflight)
    cache = Outside57Cache()
    progress = ProgressMarker(run_id)

    if resume:
        progress.load()

    api = Outside57ApiClient(
        rate_limiter=rate_limiter,
        inflight_limiter=inflight_limiter,
        cache=cache,
        timeout_sec=api_timeout_sec,
        retry_max=retry_max,
    )

    # ── 拉取 fixtures ──
    fixtures = fetch_today_fixtures(
        lookahead_hours=None,
        min_hours_to_kickoff=None,
        api_client=api.call,
        scan_base_date=date.today(),
        include_outside_57=True,
    )

    input_fixture_count = len(fixtures)
    print(f"[outside57] input fixtures: {input_fixture_count}")
    print(f"[outside57] workers={workers}, rpm={api_rpm}/{api_rpm_hard_cap}, inflight={max_inflight}")

    if resume:
        # 过滤已完成的 fixtures
        pending_fixtures = [fx for fx in fixtures if not progress.is_done(int(fx["id"]))]
        skipped_count = input_fixture_count - len(pending_fixtures)
        print(f"[outside57] resume: skipped {skipped_count} already-done fixtures, {len(pending_fixtures)} pending")
        fixtures = pending_fixtures

    # ── Worker pool 并行处理 ──
    actual_workers = min(workers, max(1, len(fixtures)))
    actual_workers = min(actual_workers, worker_max)

    results: list[dict] = []
    done_count = 0
    timeout_count = 0
    failed_count = 0
    silent_drop_count = 0
    results_lock = threading.Lock()

    def _process_with_timeout(fx: dict) -> dict:
        """在 fixture 级别加超时保护。"""
        try:
            result = _process_one_fixture(fx, api, scan_date_str, scan_mode)
        except Exception as e:
            result = {
                "fixture_id": fx["id"],
                "status": "FAILED_WITH_REASON",
                "failure_reason": f"unhandled:{type(e).__name__}:{e}",
                **OUTSIDE57_MARKER,
                "processed_at": datetime.now(CN_TZ).isoformat(),
            }
        return result

    print(f"[outside57] starting worker pool with {actual_workers} workers...")
    with ThreadPoolExecutor(max_workers=actual_workers) as pool:
        future_to_fx = {pool.submit(_process_with_timeout, fx): fx for fx in fixtures}

        for i, future in enumerate(as_completed(future_to_fx)):
            fx = future_to_fx[future]
            try:
                result = future.result(timeout=fixture_timeout_sec + 10)
            except FuturesTimeoutError:
                result = {
                    "fixture_id": fx["id"],
                    "home_team": fx["home"],
                    "away_team": fx["away"],
                    "status": "API_TIMEOUT",
                    "failure_reason": f"fixture_timeout_{fixture_timeout_sec}s",
                    **OUTSIDE57_MARKER,
                    "processed_at": datetime.now(CN_TZ).isoformat(),
                }
                timeout_count += 1
            except Exception as e:
                result = {
                    "fixture_id": fx["id"],
                    "home_team": fx.get("home", "?"),
                    "away_team": fx.get("away", "?"),
                    "status": "FAILED_WITH_REASON",
                    "failure_reason": f"worker_error:{type(e).__name__}:{e}",
                    **OUTSIDE57_MARKER,
                    "processed_at": datetime.now(CN_TZ).isoformat(),
                }
                failed_count += 1

            with results_lock:
                results.append(result)
                status = result.get("status", "UNKNOWN")
                if status == "DONE":
                    done_count += 1
                    progress.mark_done(int(fx["id"]))
                elif status == "API_TIMEOUT":
                    timeout_count += 1
                    progress.mark_failed(int(fx["id"]), "API_TIMEOUT")
                elif status in ("SCORE_ERROR", "FAILED_WITH_REASON"):
                    failed_count += 1
                    progress.mark_failed(int(fx["id"]), result.get("failure_reason", result.get("scoring_error", "unknown")))
                else:
                    failed_count += 1
                    progress.mark_failed(int(fx["id"]), f"unknown_status:{status}")

            if (i + 1) % 20 == 0 or (i + 1) == len(fixtures):
                elapsed = time.perf_counter() - t_start
                print(f"  [{i+1}/{len(fixtures)}] done={done_count} timeout={timeout_count} "
                      f"failed={failed_count} elapsed={elapsed:.0f}s "
                      f"rpm_peak={rate_limiter.rpm_peak_60s} inflight_peak={inflight_limiter.peak_inflight_requests} "
                      f"cache_hits={cache.hits}")

    # ── 补足 resume 跳过的 fixtures ──
    if resume:
        for fx in fixtures:
            if progress.is_done(int(fx["id"])) and not any(
                r.get("fixture_id") == fx["id"] for r in results
            ):
                results.append({
                    "fixture_id": fx["id"],
                    "home_team": fx["home"],
                    "away_team": fx["away"],
                    "status": "DONE",
                    "resumed": True,
                    **OUTSIDE57_MARKER,
                    "processed_at": datetime.now(CN_TZ).isoformat(),
                })
                done_count += 1

    # ── 全量覆盖验证 ──
    processed_fixture_count = len(results)
    silent_drop_count = input_fixture_count - processed_fixture_count
    coverage_rate = processed_fixture_count / max(1, input_fixture_count)

    # ── 排序结果 ──
    results.sort(key=lambda r: (r.get("kickoff_time", ""), str(r.get("fixture_id", ""))))

    t_end = time.perf_counter()
    total_duration_sec = t_end - t_start

    # ── 汇总输出 ──
    summary = {
        "phase": "V4-OUTSIDE57-FULL-SCAN-PARALLEL-ARCHITECTURE-FIX-20260527",
        "run_id": run_id,
        "generated_at": datetime.now(CN_TZ).isoformat(),
        "scan_date": scan_date_str,
        "full_coverage": {
            "input_fixture_count": input_fixture_count,
            "processed_fixture_count": processed_fixture_count,
            "done_count": done_count,
            "timeout_count": timeout_count,
            "failed_count": failed_count,
            "silent_drop_count": silent_drop_count,
            "coverage_rate": coverage_rate,
            "processed_eq_input": processed_fixture_count == input_fixture_count,
            "silent_drop_eq_zero": silent_drop_count == 0,
        },
        "performance": {
            "total_duration_sec": total_duration_sec,
            "total_duration_min": total_duration_sec / 60,
            "avg_sec_per_fixture": total_duration_sec / max(1, processed_fixture_count),
            "api_request_count": api.api_request_count,
        },
        "rate_limiter": rate_limiter.snapshot(),
        "inflight_limiter": inflight_limiter.snapshot(),
        "cache": cache.snapshot(),
        "config": {
            "workers": actual_workers,
            "worker_max": worker_max,
            "api_rpm": api_rpm,
            "api_rpm_hard_cap": api_rpm_hard_cap,
            "max_inflight": max_inflight,
            "api_timeout_sec": api_timeout_sec,
            "fixture_timeout_sec": fixture_timeout_sec,
            "retry_max": retry_max,
            "resume": resume,
            "scan_mode": scan_mode,
        },
        "isolation": {
            "outside57": True,
            "official_candidate_written": False,
            "validation_triggered": False,
            "live_bet_modified": False,
            "qq_pushed": False,
            "official_scan_modified": False,
            "strategy_changed": False,
            "candidate_rating_changed": False,
        },
        "results": results,
    }

    # 判定状态
    if silent_drop_count > 0:
        summary["conclusion"] = "BLOCKER"
        summary["conclusion_reason"] = f"silent_drop_count={silent_drop_count} > 0"
    elif rate_limiter.rpm_peak_60s > api_rpm_hard_cap:
        summary["conclusion"] = "BLOCKER"
        summary["conclusion_reason"] = f"rpm_peak_60s={rate_limiter.rpm_peak_60s} > {api_rpm_hard_cap}"
    elif inflight_limiter.peak_inflight_requests > max_inflight:
        summary["conclusion"] = "BLOCKER"
        summary["conclusion_reason"] = f"peak_inflight={inflight_limiter.peak_inflight_requests} > {max_inflight}"
    else:
        summary["conclusion"] = "PASS"

    return summary


def main():
    parser = argparse.ArgumentParser(description="outside_57 全量并行扫描")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--worker-max", type=int, default=12)
    parser.add_argument("--api-rpm", type=int, default=290)
    parser.add_argument("--api-rpm-hard-cap", type=int, default=300)
    parser.add_argument("--max-inflight", type=int, default=30)
    parser.add_argument("--api-timeout", type=int, default=12, dest="api_timeout_sec")
    parser.add_argument("--fixture-timeout", type=int, default=35, dest="fixture_timeout_sec")
    parser.add_argument("--retry", type=int, default=2, dest="retry_max")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--scan-mode", default="full")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    workers = max(1, min(args.workers, args.worker_max))

    summary = run_outside57_scan(
        workers=workers,
        worker_max=args.worker_max,
        api_rpm=args.api_rpm,
        api_rpm_hard_cap=args.api_rpm_hard_cap,
        max_inflight=args.max_inflight,
        api_timeout_sec=args.api_timeout_sec,
        fixture_timeout_sec=args.fixture_timeout_sec,
        retry_max=args.retry_max,
        resume=args.resume,
        run_id=args.run_id,
        scan_mode=args.scan_mode,
    )

    output_path = args.output or str(
        STATUS_DIR / f"v4_outside57_scan_result_{summary['run_id']}.json"
    )
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    # Standalone mode: ONLY write isolated result, never official candidate_view.
    # Official output path is only written when called through v4_scan_and_brief.py
    # adapter with the write-official-output flag.
    # 写结果（不含 results 数组太大时的截断版本）
    summary_light = {k: v for k, v in summary.items() if k != "results"}
    summary_light["results_count"] = len(summary["results"])
    summary_light["results_file"] = output_path

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"\n[outside57] conclusion={summary['conclusion']}")
    print(f"[outside57] fixtures: {summary['full_coverage']['input_fixture_count']} in, "
          f"{summary['full_coverage']['processed_fixture_count']} processed, "
          f"{summary['full_coverage']['done_count']} done")
    print(f"[outside57] duration: {summary['performance']['total_duration_sec']:.0f}s "
          f"({summary['performance']['total_duration_min']:.1f}min)")
    print(f"[outside57] rpm_peak={summary['rate_limiter']['rpm_peak_60s']}, "
          f"inflight_peak={summary['inflight_limiter']['peak_inflight_requests']}")
    print(f"[outside57] cache: hits={summary['cache']['cache_hits']} misses={summary['cache']['cache_misses']}")
    print(f"[outside57] output: {output_path}")

    return 0 if summary["conclusion"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
