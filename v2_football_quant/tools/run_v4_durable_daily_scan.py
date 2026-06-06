#!/usr/bin/env python3
"""Run the daily V4 scan outside OpenClaw's isolated session lifecycle."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STATUS_DIR = ROOT / "data/runtime/status"
LOG_DIR = ROOT / "data/runtime/logs"
STATUS_PATH = STATUS_DIR / "v4_durable_daily_scan_status.json"
LOCK_PATH = STATUS_DIR / "v4_durable_daily_scan.lock"
TZ = timezone(timedelta(hours=8))
HEARTBEAT_SECONDS = 30
SCHEDULED_HOUR = 12
SCHEDULED_MINUTE = 0


def now() -> datetime:
    return datetime.now(TZ)


def iso(dt: datetime | None = None) -> str:
    return (dt or now()).isoformat()


def atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def load_status() -> dict[str, Any]:
    try:
        return json.loads(STATUS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def base_status(date_key: str) -> dict[str, Any]:
    prior = load_status()
    return {
        "schema_version": "v4_durable_daily_scan_status.v1",
        "updated_at": iso(),
        "runner_mode": "template_only",
        "runner_installed": False,
        "launchd_template_present": True,
        "launchd_loaded": prior.get("launchd_loaded", False),
        "isolated_session_dependency": True,
        "openclaw_status_only_target": True,
        "next_action": "DEPLOY_APPROVAL_REQUIRED",
        "scheduled_time": "12:00 Asia/Shanghai",
        "scan_date": date_key,
        "state": prior.get("state", "TEMPLATE_ONLY"),
        "active_lock": LOCK_PATH.exists(),
        "lock_path": str(LOCK_PATH.relative_to(ROOT)),
        "heartbeat_at": prior.get("heartbeat_at"),
        "heartbeat_age_seconds": prior.get("heartbeat_age_seconds"),
        "last_scheduled_scan": prior.get("last_scheduled_scan"),
        "last_completed_scan": prior.get("last_completed_scan"),
        "last_exit_code": prior.get("last_exit_code"),
        "scan_exit_code": prior.get("scan_exit_code"),
        "qq_exit_code": prior.get("qq_exit_code"),
        "scan_failure": prior.get("scan_failure", False),
        "qq_failure": prior.get("qq_failure", False),
        "catch_up_required": prior.get("catch_up_required", False),
        "catch_up_status": prior.get("catch_up_status", "NOT_REQUIRED"),
        "log_path": prior.get("log_path"),
        "timeout_seconds": prior.get("timeout_seconds"),
        "scan_command": prior.get("scan_command"),
        "auto_rerun": False,
        "manual_oneshot_requires_boss_approval": True,
        "QQ_push": False,
        "cron_modified": False,
    }


def acquire_lock() -> bool:
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(LOCK_PATH, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except FileExistsError:
        return False
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(json.dumps({"pid": os.getpid(), "acquired_at": iso()}, ensure_ascii=False))
    return True


def release_lock() -> None:
    try:
        LOCK_PATH.unlink()
    except FileNotFoundError:
        pass


def scheduled_deadline(date_key: str) -> datetime:
    return datetime.strptime(date_key, "%Y%m%d").replace(
        hour=SCHEDULED_HOUR,
        minute=SCHEDULED_MINUTE,
        second=0,
        microsecond=0,
        tzinfo=TZ,
    )


def detect_catchup(date_key: str) -> int:
    status = base_status(date_key)
    deadline = scheduled_deadline(date_key)
    completed = str(status.get("last_completed_scan") or "")
    completed_today = completed.startswith(date_key)
    catchup = now() >= deadline and not completed_today
    status.update({
        "updated_at": iso(),
        "state": "NEED_MANUAL_CATCHUP" if catchup else status.get("state", "TEMPLATE_ONLY"),
        "catch_up_required": catchup,
        "catch_up_status": "NEED_MANUAL_CATCHUP" if catchup else "NOT_REQUIRED",
        "auto_rerun": False,
        "QQ_push": False,
    })
    atomic_write(STATUS_PATH, status)
    print(json.dumps(status, ensure_ascii=False, indent=2))
    return 0


def run_scan(args: argparse.Namespace) -> int:
    date_key = args.date
    status = base_status(date_key)
    if not acquire_lock():
        status.update({
            "updated_at": iso(),
            "state": "SKIPPED_ACTIVE_LOCK",
            "active_lock": True,
            "catch_up_required": True,
            "catch_up_status": "NEED_MANUAL_CATCHUP",
            "auto_rerun": False,
        })
        atomic_write(STATUS_PATH, status)
        print(json.dumps(status, ensure_ascii=False, indent=2))
        return 3

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / f"v4_durable_daily_scan_{date_key}_{now().strftime('%H%M%S')}.log"
    command = [
        sys.executable,
        "-u",
        str(ROOT / "engine/v4_scan_and_brief.py"),
        "--date",
        date_key,
        "--no-push",
    ]
    started = now()
    status.update({
        "updated_at": iso(started),
        "state": "RUNNING",
        "active_lock": True,
        "runner_mode": "durable_local_process",
        "runner_installed": True,
        "launchd_loaded": status.get("launchd_loaded", False),
        "isolated_session_dependency": False,
        "next_action": "MONITOR_STATUS_ONLY",
        "last_scheduled_scan": date_key if args.scheduled else status.get("last_scheduled_scan"),
        "started_at": iso(started),
        "heartbeat_at": iso(started),
        "heartbeat_age_seconds": 0,
        "log_path": str(log_path.relative_to(ROOT)),
        "timeout_seconds": args.timeout_seconds,
        "scan_command": command,
        "scan_failure": False,
        "qq_failure": False,
        "catch_up_required": False,
        "catch_up_status": "NOT_REQUIRED",
    })
    atomic_write(STATUS_PATH, status)

    scan_rc = 1
    qq_rc: int | None = None
    try:
        with log_path.open("a", encoding="utf-8") as log:
            proc = subprocess.Popen(command, cwd=str(ROOT), stdout=log, stderr=subprocess.STDOUT, text=True)
            deadline = time.monotonic() + args.timeout_seconds
            timed_out = False
            while proc.poll() is None:
                if time.monotonic() >= deadline:
                    proc.terminate()
                    try:
                        proc.wait(timeout=15)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait()
                    timed_out = True
                    scan_rc = 124
                    break
                status.update({
                    "updated_at": iso(),
                    "heartbeat_at": iso(),
                    "heartbeat_age_seconds": 0,
                    "active_lock": True,
                })
                atomic_write(STATUS_PATH, status)
                time.sleep(HEARTBEAT_SECONDS)
            else:
                scan_rc = int(proc.returncode or 0)
            if proc.poll() is not None and not timed_out:
                scan_rc = int(proc.returncode or 0)

        notify_duration = int((now() - started).total_seconds())
        notify_pending_state = {
            **status,
            "updated_at": iso(),
            "state": "FAILED" if scan_rc != 0 else "SCAN_COMPLETED_NOTIFY_PENDING",
            "active_lock": True,
            "scan_exit_code": scan_rc,
            "last_exit_code": scan_rc,
            "scan_failure": scan_rc != 0,
            "ended_at": iso(),
            "duration_seconds": notify_duration,
            "last_completed_scan": date_key if scan_rc == 0 else status.get("last_completed_scan"),
            "catch_up_required": scan_rc != 0,
            "catch_up_status": "NEED_MANUAL_CATCHUP" if scan_rc != 0 else "NOT_REQUIRED",
        }
        atomic_write(STATUS_PATH, notify_pending_state)

        if args.notify:
            notify_cmd = [
                sys.executable,
                str(ROOT / "tools/notify_cron_task_complete_qq.py"),
                "--task",
                "V4_DAILY_SCAN_REAL_COMPLETED",
                "--date",
                date_key,
                "--exit-code",
                str(scan_rc),
                "--duration",
                str(notify_duration),
            ]
            qq_rc = subprocess.run(notify_cmd, cwd=str(ROOT), timeout=120).returncode
    finally:
        release_lock()

    ended = now()
    scan_failed = scan_rc != 0
    qq_failed = qq_rc not in (None, 0)
    status.update({
        "updated_at": iso(ended),
        "state": "FAILED" if scan_failed else ("QQ_FAILED_SCAN_OK" if qq_failed else "COMPLETED"),
        "active_lock": False,
        "heartbeat_at": iso(ended),
        "heartbeat_age_seconds": 0,
        "ended_at": iso(ended),
        "last_completed_scan": date_key if not scan_failed else status.get("last_completed_scan"),
        "last_exit_code": scan_rc,
        "scan_exit_code": scan_rc,
        "qq_exit_code": qq_rc,
        "scan_failure": scan_failed,
        "qq_failure": qq_failed,
        "catch_up_required": scan_failed,
        "catch_up_status": "NEED_MANUAL_CATCHUP" if scan_failed else "NOT_REQUIRED",
        "QQ_push": bool(args.notify),
    })
    atomic_write(STATUS_PATH, status)
    print(json.dumps(status, ensure_ascii=False, indent=2))
    return scan_rc


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=now().strftime("%Y%m%d"))
    parser.add_argument("--scheduled", action="store_true")
    parser.add_argument("--detect-catchup", action="store_true")
    parser.add_argument("--manual-oneshot", action="store_true")
    parser.add_argument("--boss-approved-manual-oneshot", action="store_true")
    parser.add_argument("--notify", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=7200)
    args = parser.parse_args()

    if args.detect_catchup:
        return detect_catchup(args.date)
    if args.manual_oneshot and not args.boss_approved_manual_oneshot:
        print("BLOCKED: manual oneshot requires --boss-approved-manual-oneshot", file=sys.stderr)
        return 2
    if not args.scheduled and not args.manual_oneshot:
        print("BLOCKED: choose --scheduled, --detect-catchup, or --manual-oneshot", file=sys.stderr)
        return 2
    return run_scan(args)


if __name__ == "__main__":
    raise SystemExit(main())
