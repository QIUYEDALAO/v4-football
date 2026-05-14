#!/usr/bin/env python3
"""engine/task_watchdog.py — 统一任务状态监控
=============================================
所有定时任务接入此模块进行：
1. 状态文件读写 2. heartbeat 更新 3. 超时检测
4. 并发锁 5. 进度推送 6. 半成品文件保护

不修改策略逻辑/评分阈值/赔率带/API Key。
"""

from __future__ import annotations

import json
import os
import time
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Optional

LOCAL_TZ = timezone(timedelta(hours=8))
BASE_DIR = Path(__file__).resolve().parent.parent
RUNTIME_DIR = BASE_DIR / "data" / "runtime"
STATUS_DIR = RUNTIME_DIR / "status"
LOCK_DIR = RUNTIME_DIR / "locks"


def _ensure_dirs() -> None:
    STATUS_DIR.mkdir(parents=True, exist_ok=True)
    LOCK_DIR.mkdir(parents=True, exist_ok=True)


class TaskWatchdog:
    """任务监控器：每个定时任务实例化一个"""

    def __init__(
        self,
        task_name: str,
        system: str = "SYS",
        timeout_soft_s: int = 1800,
        timeout_hard_s: int = 3600,
        heartbeat_interval_s: int = 300,
    ):
        self.task_name = task_name
        self.system = system
        self.timeout_soft_s = timeout_soft_s
        self.timeout_hard_s = timeout_hard_s
        self.heartbeat_interval_s = heartbeat_interval_s
        self._started_at: Optional[datetime] = None
        self._lock_path = LOCK_DIR / f"{task_name}.lock"
        self._status_path = STATUS_DIR / f"task_status_{task_name}.json"
        self._heartbeat_timer: Optional[threading.Timer] = None
        self._progress: dict[str, Any] = {}
        self._api_calls: int = 0
        _ensure_dirs()

    # ── Lock ──

    def acquire_lock(self, max_stale_s: int = 3600) -> bool:
        """获取并发锁，防止同任务并发。返回 True 表示获得锁"""
        if self._lock_path.exists():
            stale_s = time.time() - self._lock_path.stat().st_mtime
            if stale_s < max_stale_s:
                return False
            # 过期锁，标记异常后覆盖
            self._write_status("STALE_LOCK", message=f"旧锁过期 {stale_s:.0f}s，覆盖")
        self._lock_path.write_text(str(os.getpid()))
        return True

    def release_lock(self) -> None:
        if self._lock_path.exists():
            self._lock_path.unlink(missing_ok=True)

    # ── Status ──

    def start(self, total_items: int = 0) -> dict:
        """任务启动，写状态文件，启动心跳"""
        now = datetime.now(LOCAL_TZ)
        self._started_at = now
        state = {
            "task_name": self.task_name,
            "system": self.system,
            "date": now.strftime("%Y%m%d"),
            "status": "RUNNING",
            "started_at": now.isoformat(),
            "last_heartbeat_at": now.isoformat(),
            "finished_at": None,
            "elapsed_seconds": 0,
            "progress": {"current": 0, "total": total_items, "percent": 0.0, "current_item": ""},
            "api_usage": {"calls_used_this_task": 0, "daily_limit": 75000},
            "output_files": {},
            "error": None,
            "message": f"{self.task_name} started",
        }
        self._write_full(state)
        self._start_heartbeat()
        return state

    def heartbeat(self, current: int = 0, total: int = 0, item: str = "", api_calls: int = 0) -> dict:
        """更新心跳"""
        now = datetime.now(LOCAL_TZ)
        pct = round(current / max(total, 1) * 100, 1)
        self._progress = {"current": current, "total": total, "percent": pct, "current_item": item}
        self._api_calls = api_calls
        elapsed = int((now - self._started_at).total_seconds()) if self._started_at else 0
        state = {
            "task_name": self.task_name,
            "system": self.system,
            "date": now.strftime("%Y%m%d"),
            "status": "RUNNING",
            "started_at": self._started_at.isoformat() if self._started_at else None,
            "last_heartbeat_at": now.isoformat(),
            "finished_at": None,
            "elapsed_seconds": elapsed,
            "progress": self._progress,
            "api_usage": {"calls_used_this_task": api_calls, "daily_limit": 75000},
            "output_files": self._get_output_files(),
            "error": None,
            "message": f"processing {item}" if item else "running",
        }
        self._write_full(state)
        return state

    def finish(self, status: str = "DONE", error: str = "", output_files: dict[str, Any] | None = None) -> dict:
        """任务结束"""
        self.release_lock()
        if self._heartbeat_timer:
            self._heartbeat_timer.cancel()
        now = datetime.now(LOCAL_TZ)
        elapsed = int((now - self._started_at).total_seconds()) if self._started_at else 0
        state = {
            "task_name": self.task_name,
            "system": self.system,
            "date": now.strftime("%Y%m%d"),
            "status": status,
            "started_at": self._started_at.isoformat() if self._started_at else None,
            "last_heartbeat_at": now.isoformat(),
            "finished_at": now.isoformat(),
            "elapsed_seconds": elapsed,
            "progress": self._progress,
            "api_usage": {"calls_used_this_task": self._api_calls, "daily_limit": 75000},
            "output_files": output_files or self._get_output_files(),
            "error": error or None,
            "message": f"{status}: {error}" if error else f"{status}",
        }
        self._write_full(state)
        return state

    def is_timed_out(self) -> tuple[bool, str]:
        """检查超时。返回 (是否超时, 级别)"""
        if not self._started_at:
            return False, "NOT_STARTED"
        elapsed = (datetime.now(LOCAL_TZ) - self._started_at).total_seconds()
        if elapsed > self.timeout_hard_s:
            return True, "HARD_TIMEOUT"
        if elapsed > self.timeout_soft_s:
            return True, "SOFT_TIMEOUT"
        return False, "OK"

    def check_output_stale(self, output_path: str) -> bool:
        """检查输出文件是否早于任务启动时间（半成品保护）"""
        p = Path(output_path)
        if not p.exists():
            return True  # 不存在 = 不能读
        if self._started_at:
            mod_time = datetime.fromtimestamp(p.stat().st_mtime, tz=LOCAL_TZ)
            return mod_time < self._started_at
        return False

    def progress_summary(self) -> str:
        """统一进度推送格式"""
        elapsed = int((datetime.now(LOCAL_TZ) - self._started_at).total_seconds()) if self._started_at else 0
        p = self._progress
        return (
            f"【任务进度】\n"
            f"任务：{self.task_name}\n"
            f"状态：{'RUNNING' if elapsed < self.timeout_soft_s else 'DELAYED'}\n"
            f"已运行：{elapsed // 60}分钟\n"
            f"进度：{p.get('current', 0)}/{p.get('total', 0)} 场\n"
            f"API调用：{self._api_calls}\n"
            f"当前处理：{p.get('current_item', '-')}\n"
            f"输出文件：{self._get_output_files() or '尚未完成'}\n"
            f"下一步：{'继续等待' if elapsed < self.timeout_soft_s else '已标记延迟'}"
        )

    # ── internal ──

    def _write_full(self, state: dict) -> None:
        self._status_path.parent.mkdir(parents=True, exist_ok=True)
        self._status_path.write_text(json.dumps(state, ensure_ascii=False, indent=2))

    def _write_status(self, status: str, message: str = "") -> None:
        state = json.loads(self._status_path.read_text()) if self._status_path.exists() else {}
        state["status"] = status
        state["message"] = message
        state["last_heartbeat_at"] = datetime.now(LOCAL_TZ).isoformat()
        self._write_full(state)

    def _start_heartbeat(self) -> None:
        """启动心跳定时器"""

        def _beat():
            self.heartbeat(
                current=self._progress.get("current", 0),
                total=self._progress.get("total", 0),
                item=self._progress.get("current_item", ""),
                api_calls=self._api_calls,
            )
            self._heartbeat_timer = threading.Timer(self.heartbeat_interval_s, _beat)
            self._heartbeat_timer.daemon = True
            self._heartbeat_timer.start()

        self._heartbeat_timer = threading.Timer(self.heartbeat_interval_s, _beat)
        self._heartbeat_timer.daemon = True
        self._heartbeat_timer.start()

    def _get_output_files(self) -> dict:
        return {}


# ── 便捷工厂函数 ──

def v4_scan_watchdog(window: str) -> TaskWatchdog:
    return TaskWatchdog(
        task_name=f"v4_scan_{window}",
        system="V4",
        timeout_soft_s=1800,  # 30分钟
        timeout_hard_s=3600,  # 60分钟
    )


def v2_settle_watchdog() -> TaskWatchdog:
    return TaskWatchdog(
        task_name="v2_daily_settle",
        system="V2",
        timeout_soft_s=1800,
        timeout_hard_s=2700,
    )


def v2_pool_watchdog() -> TaskWatchdog:
    return TaskWatchdog(
        task_name="v2_daily_pool",
        system="V2",
        timeout_soft_s=1800,
        timeout_hard_s=2700,
    )


def v2_window_checker_watchdog(window: str) -> TaskWatchdog:
    return TaskWatchdog(
        task_name=f"v2_window_{window}",
        system="V2",
        timeout_soft_s=480,  # 8分钟
        timeout_hard_s=900,  # 15分钟
        heartbeat_interval_s=180,
    )


def v4_brief_watchdog() -> TaskWatchdog:
    return TaskWatchdog(
        task_name="v4_openclaw_brief",
        system="V4",
        timeout_soft_s=600,
        timeout_hard_s=1200,
    )


def v4_review_watchdog() -> TaskWatchdog:
    return TaskWatchdog(
        task_name="v4_daily_review",
        system="V4",
        timeout_soft_s=1800,
        timeout_hard_s=2700,
    )


def v4_snapshot_watchdog() -> TaskWatchdog:
    return TaskWatchdog(
        task_name="v4_live_snapshot",
        system="V4",
        timeout_soft_s=60,
        timeout_hard_s=120,
        heartbeat_interval_s=30,
    )
