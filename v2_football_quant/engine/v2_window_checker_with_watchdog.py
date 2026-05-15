#!/usr/bin/env python3
"""engine/v2_window_checker_with_watchdog.py — V2窗口检查器 supervisor

父进程职责：
1. 启动 v2_window_worker.py 子进程
2. 监控超时（soft 8min → DELAYED, hard 15min → TIMEOUT）
3. 处理 SIGKILL → 写 KILLED_SIGKILL
4. 禁止并发
5. 无 active window 时不拉赔率，快速退出

输出格式（systemEvent）：
【V2 量化系统】
状态：DONE_BET_LOCKED / DONE_NO_BET_LOCKED / DONE_FINAL_RECORD / DONE_WATCH_ONLY / SKIPPED_NO_ACTIVE_WINDOW / FAILED / TIMEOUT / KILLED_SIGKILL
本轮新增 BET_LOCKED：x
WATCH_EARLY：x
CANDIDATE：x
FINAL_RECORD：x
ODDS_OUT：x
执行投注：无 / 有
"""

import hashlib
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

LOCAL_TZ = timezone(timedelta(hours=8))
BASE_DIR = Path(__file__).resolve().parent.parent
WORKER_SCRIPT = BASE_DIR / "engine" / "v2_window_worker.py"
RUNTIME_DIR = BASE_DIR / "data" / "runtime"
STATUS_DIR = RUNTIME_DIR / "status"
LOCK_DIR = RUNTIME_DIR / "locks"

SOFT_TIMEOUT_S = 480   # 8分钟标记 DELAYED
HARD_TIMEOUT_S = 900   # 15分钟标记 TIMEOUT

# ── QQ Bot 推送目标 ──
BOSS_QQ_ID = "fbc6f797a5c3b6fe2680a8b25f95e143"

# ── 必须推送的状态 ──
MUST_PUSH_STATUSES = frozenset([
    "DONE_BET_LOCKED",
    "FAILED",
    "TIMEOUT",
    "KILLED_SIGKILL",
])

# ── 静默状态（不推送） ──
SILENT_STATUSES = frozenset([
    "SKIPPED_NO_ACTIVE_WINDOW",
    "SKIPPED_STARTED_OR_CLOSED",
    "DONE_WATCH_ONLY",
    "DONE_FINAL_RECORD",
    "DONE_NO_BET_LOCKED",
    "SKIPPED_LOCKED",
    "DELAYED",
])


def _ensure_dirs():
    STATUS_DIR.mkdir(parents=True, exist_ok=True)
    LOCK_DIR.mkdir(parents=True, exist_ok=True)


def _task_lock_path(name="v2_window_checker") -> str:
    return str(LOCK_DIR / f"{name}.lock")


def _acquire_lock() -> bool:
    lock_path = _task_lock_path()
    if os.path.exists(lock_path):
        stale_s = time.time() - os.path.getmtime(lock_path)
        if stale_s < 3600:
            return False
    with open(lock_path, "w") as f:
        f.write(str(os.getpid()))
    return True


def _release_lock() -> None:
    lock_path = _task_lock_path()
    try:
        os.unlink(lock_path)
    except FileNotFoundError:
        pass


def _write_status_file(status: str, **kwargs) -> None:
    path = STATUS_DIR / f"v2_window_latest.json"
    data = {
        "system": "V2",
        "task": "window_checker",
        "status": status,
        "checked_at": datetime.now(LOCAL_TZ).isoformat(),
        **kwargs,
    }
    with open(path, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _today_str() -> str:
    return datetime.now(LOCAL_TZ).strftime("%Y%m%d")


def _notify_marker_path() -> str:
    return str(STATUS_DIR / f"v2_window_notify_{_today_str()}.json")


def _generate_run_id(window_status: str, new_locks: list, reason: str = "") -> str:
    raw = f"{_today_str()}|{window_status}|{len(new_locks)}|{reason}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _check_already_pushed(run_id: str) -> bool:
    """检查同一 run_id 是否已推送过（防重复推送）"""
    path = _notify_marker_path()
    if not os.path.exists(path):
        return False
    try:
        with open(path) as f:
            data = json.load(f)
        return data.get("run_id", "") == run_id and data.get("pushed", False)
    except (json.JSONDecodeError, KeyError):
        return False


def _write_notify_marker(window_status: str, new_locks: list, pushed: bool,
                         run_id: str, message_hash: str = "") -> None:
    """写入通知标记，避免同一次运行重复推送"""
    path = _notify_marker_path()
    data = {
        "date": _today_str(),
        "run_id": run_id,
        "status": window_status,
        "new_bet_locked": len(new_locks),
        "pushed": pushed,
        "pushed_at": datetime.now(LOCAL_TZ).isoformat() if pushed else None,
        "message_hash": message_hash,
    }
    with open(path, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _push_system_event(window_status: str, watches: int, candidates: int,
                       finals: int, odds_out: int, new_locks: list,
                       locked_total: int, reason: str = "") -> bool:
    """
    条件推送 systemEvent 到 QQ。
    仅 Must-push 状态才推送；静默状态不推。
    返回是否实际发送。
    """
    today = _today_str()
    run_id = _generate_run_id(window_status, new_locks, reason)

    # 防重复推送
    if _check_already_pushed(run_id):
        return False

    # ── 判断是否必须推送 ──
    is_bet_locked = window_status == "DONE_BET_LOCKED" and len(new_locks) > 0
    is_error = window_status in ("FAILED", "TIMEOUT", "KILLED_SIGKILL")
    is_blocker = window_status not in MUST_PUSH_STATUSES and window_status not in SILENT_STATUSES

    if not (is_bet_locked or is_error or is_blocker):
        # 静默状态：写入 marker（标记已检查但不推送）
        _write_notify_marker(window_status, new_locks, False, run_id)
        return False

    # ── 构造推送文本 ──
    if is_bet_locked:
        message = (
            f"【V2 量化系统】\n"
            f"📌 V2窗口检查触发\n"
            f"\n"
            f"新增 BET_LOCKED：{len(new_locks)} 场\n"
            f"锁定池总计：{locked_total} 笔\n"
            f"\n"
            f"【本轮状态】\n"
            f"WATCH_EARLY：{watches}\n"
            f"CANDIDATE：{candidates}\n"
            f"FINAL_RECORD：{finals}\n"
            f"ODDS_OUT：{odds_out}\n"
            f"\n"
            f"【执行投注】\n"
            f"有\n"
            f"\n"
            f"说明：V2正式推荐只认 BET_LOCKED。"
        )
    elif is_error:
        message = (
            f"【AlertAgent】\n"
            f"系统：V2\n"
            f"任务：V2窗口检查器\n"
            f"状态：{window_status}\n"
            f"时间：{datetime.now(LOCAL_TZ).strftime('%Y-%m-%d %H:%M')}\n"
            f"错误：{reason}\n"
            f"动作：仅报告，等待 BOSS 指令"
        )
    else:
        # BLOCKER / 未知异常
        message = (
            f"【AlertAgent】\n"
            f"系统：V2\n"
            f"任务：V2窗口检查器\n"
            f"状态：{window_status}\n"
            f"时间：{datetime.now(LOCAL_TZ).strftime('%Y-%m-%d %H:%M')}\n"
            f"动作：仅报告，等待 BOSS 指令\n"
            f"说明：非标准状态，需人工确认"
        )

    # ── 计算消息 hash → 写入 marker → 发送 ──
    msg_hash = hashlib.md5(message.encode()).hexdigest()[:12]
    _write_notify_marker(window_status, new_locks, True, run_id, msg_hash)

    try:
        subprocess.run(
            ["openclaw", "message", "send",
             "--channel", "qqbot",
             "--target", BOSS_QQ_ID,
             "--message", message],
            capture_output=True, timeout=30,
        )
        return True
    except Exception as e:
        print(f"[WARN] push_system_event 失败: {e}", flush=True)
        return False


def _emit_output(window_status: str, watches: int, candidates: int, finals: int,
                 odds_out: int, new_locks: list, locked_total: int, in_band: int,
                 reason: str = ""):
    """输出 systemEvent 格式——不做 AI 自由总结"""
    print(f"\n【V2 量化系统】", flush=True)
    print(f"状态：{window_status}", flush=True)
    print(f"本轮新增 BET_LOCKED：{len(new_locks)}", flush=True)
    print(f"锁定池总计：{locked_total}", flush=True)
    print(f"WATCH_EARLY：{watches}", flush=True)
    print(f"CANDIDATE：{candidates}", flush=True)
    print(f"FINAL_RECORD：{finals}", flush=True)
    print(f"ODDS_OUT：{odds_out}", flush=True)
    if len(new_locks) > 0:
        print(f"执行投注：有", flush=True)
    else:
        print(f"执行投注：无", flush=True)
    if reason:
        print(f"备注：{reason}", flush=True)


def _parse_worker_output(worker_stdout: str) -> dict:
    result = {
        "window_status": "UNKNOWN",
        "reason": "",
        "window_summary": {},
        "new_locks": [],
        "locked_total": 0,
        "watch_early": 0,
        "candidate": 0,
        "final_record": 0,
        "odds_out": 0,
    }
    for line in worker_stdout.split("\n"):
        line = line.strip()
        if line.startswith("WINDOW_STATUS="):
            result["window_status"] = line[len("WINDOW_STATUS="):].strip()
        elif line.startswith("REASON="):
            result["reason"] = line[len("REASON="):].strip()
        elif line.startswith("WINDOW_SUMMARY="):
            try:
                result["window_summary"] = json.loads(line[len("WINDOW_SUMMARY="):])
            except json.JSONDecodeError:
                pass
        elif line.startswith("NEW_LOCKS="):
            try:
                result["new_locks"] = json.loads(line[len("NEW_LOCKS="):])
            except json.JSONDecodeError:
                pass
        elif line.startswith("LOCKED_TOTAL="):
            try:
                result["locked_total"] = int(line[len("LOCKED_TOTAL="):])
            except ValueError:
                pass
        elif line.startswith("WATCH_EARLY="):
            try:
                result["watch_early"] = int(line[len("WATCH_EARLY="):])
            except ValueError:
                pass
        elif line.startswith("CANDIDATE="):
            try:
                result["candidate"] = int(line[len("CANDIDATE="):])
            except ValueError:
                pass
        elif line.startswith("FINAL_RECORD="):
            try:
                result["final_record"] = int(line[len("FINAL_RECORD="):])
            except ValueError:
                pass
        elif line.startswith("ODDS_OUT="):
            try:
                result["odds_out"] = int(line[len("ODDS_OUT="):])
            except ValueError:
                pass
    return result


def main():
    _ensure_dirs()

    if not _acquire_lock():
        _write_status_file("SKIPPED_LOCKED", message="并发锁占用中")
        print("SKIPPED_LOCKED — 并发锁占用中，跳过", flush=True)
        sys.exit(0)

    try:
        now_iso = datetime.now(LOCAL_TZ).isoformat()
        print(f"V2窗口检查器 | {now_iso}", flush=True)

        env = os.environ.copy()
        env["NO_PROXY"] = "*"

        worker_start = time.time()
        proc = subprocess.Popen(
            [sys.executable, str(WORKER_SCRIPT)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            text=True,
        )

        # ── 监控循环 ──
        delayed_flagged = False
        while proc.poll() is None:
            elapsed = time.time() - worker_start
            if elapsed > HARD_TIMEOUT_S:
                proc.kill()
                _write_status_file("TIMEOUT")
                _emit_output("TIMEOUT", 0, 0, 0, 0, [], 0, 0,
                             reason=f"worker 超过 {HARD_TIMEOUT_S}s 硬超时")
                _push_system_event("TIMEOUT", 0, 0, 0, 0, [], 0,
                                   reason=f"worker 超过 {HARD_TIMEOUT_S}s 硬超时")
                return
            if elapsed > SOFT_TIMEOUT_S and not delayed_flagged:
                delayed_flagged = True
                _write_status_file("DELAYED", message=f"软超时 {SOFT_TIMEOUT_S}s")
            time.sleep(1)

        worker_stdout, worker_stderr = proc.communicate()

        # ── 被信号杀死 ──
        if proc.returncode < 0:
            sig_name = signal.Signals(-proc.returncode).name
            status = "KILLED_SIGKILL" if proc.returncode == -signal.SIGKILL else f"KILLED_{sig_name}"
            _write_status_file(status)
            _emit_output(status, 0, 0, 0, 0, [], 0, 0,
                         reason=f"worker 被信号 {sig_name} 杀死，不生成推荐")
            _push_system_event(status, 0, 0, 0, 0, [], 0,
                               reason=f"worker 被信号 {sig_name} 杀死")
            return

        # ── 异常退出 ──
        if proc.returncode != 0:
            err = worker_stderr[-300:] if worker_stderr else ""
            _write_status_file("FAILED", message=err)
            _emit_output("FAILED", 0, 0, 0, 0, [], 0, 0,
                         reason=f"worker 退出码 {proc.returncode}")
            _push_system_event("FAILED", 0, 0, 0, 0, [], 0,
                               reason=f"worker 退出码 {proc.returncode}")
            return

        # ── 正常完成 ──
        result = _parse_worker_output(worker_stdout)
        ws = result["window_status"]
        _write_status_file(ws,
                           window_summary=result["window_summary"],
                           new_locks=result["new_locks"],
                           locked_total=result["locked_total"])

        _emit_output(ws,
                     watches=result["watch_early"],
                     candidates=result["candidate"],
                     finals=result["final_record"],
                     odds_out=result["odds_out"],
                     new_locks=result["new_locks"],
                     locked_total=result["locked_total"],
                     in_band=0,
                     reason=result.get("reason", ""))

        # ── 条件推送──
        _push_system_event(ws,
                           watches=result["watch_early"],
                           candidates=result["candidate"],
                           finals=result["final_record"],
                           odds_out=result["odds_out"],
                           new_locks=result["new_locks"],
                           locked_total=result["locked_total"],
                           reason=result.get("reason", ""))

    finally:
        _release_lock()


if __name__ == "__main__":
    main()
