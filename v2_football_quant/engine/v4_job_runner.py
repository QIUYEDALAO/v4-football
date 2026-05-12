from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
OPS_DIR = BASE_DIR / "data" / "ops"
JOB_RUNS_DIR = OPS_DIR / "job_runs"
HEARTBEATS_DIR = OPS_DIR / "heartbeats"
LOCKS_DIR = OPS_DIR / "locks"
LOGS_DIR = BASE_DIR / "logs" / "cron"

STATUS_ENUM = {"PENDING", "RUNNING", "SUCCESS", "FAILED", "STALE", "SKIPPED", "BLOCKED", "DEGRADED"}


def _now() -> str:
    return datetime.now().isoformat()


def _date_key() -> str:
    return datetime.now().strftime("%Y%m%d")


def _write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def _append_jsonl(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def run_job(job_name: str, tier: str, cmd: list[str], heartbeat_sec: int = 10) -> int:
    for d in (JOB_RUNS_DIR, HEARTBEATS_DIR, LOCKS_DIR, LOGS_DIR):
        d.mkdir(parents=True, exist_ok=True)

    date_key = _date_key()
    run_id = f"{date_key}_{datetime.now().strftime('%H%M%S')}_{job_name}"
    lock_path = LOCKS_DIR / f"{job_name}.lock"
    hb_path = HEARTBEATS_DIR / f"{job_name}.json"
    run_path = JOB_RUNS_DIR / f"{run_id}.json"
    runs_index = JOB_RUNS_DIR / f"job_runs_{date_key}.jsonl"
    log_path = LOGS_DIR / f"{job_name}_{datetime.now().strftime('%H%M%S')}.log"

    if lock_path.exists():
        info = {
            "job_run_id": run_id,
            "date": date_key,
            "job_name": job_name,
            "tier": tier,
            "status": "BLOCKED",
            "started_at": _now(),
            "ended_at": _now(),
            "error": "LOCK_EXISTS",
            "log_path": str(log_path),
        }
        _write_json(run_path, info)
        _append_jsonl(runs_index, info)
        return 2

    lock_path.write_text(run_id, encoding="utf-8")
    started = _now()
    base = {
        "job_run_id": run_id,
        "date": date_key,
        "job_name": job_name,
        "tier": tier,
        "status": "RUNNING",
        "started_at": started,
        "last_heartbeat_at": started,
        "log_path": str(log_path),
        "command": cmd,
    }
    _write_json(run_path, base)
    _write_json(hb_path, {"job_name": job_name, "status": "RUNNING", "job_run_id": run_id, "ts": started})

    with open(log_path, "a", encoding="utf-8") as lf:
        lf.write(f"[{_now()}] START {cmd}\n")
        proc = subprocess.Popen(cmd, cwd=str(BASE_DIR), stdout=lf, stderr=lf, text=True)
        last_hb = time.time()
        try:
            while proc.poll() is None:
                time.sleep(1)
                if time.time() - last_hb >= heartbeat_sec:
                    ts = _now()
                    _write_json(hb_path, {"job_name": job_name, "status": "RUNNING", "job_run_id": run_id, "ts": ts})
                    base["last_heartbeat_at"] = ts
                    _write_json(run_path, base)
                    last_hb = time.time()
        except KeyboardInterrupt:
            proc.send_signal(signal.SIGINT)
            proc.wait(timeout=10)

        code = proc.returncode if proc.returncode is not None else 1
        ended = _now()
        status = "SUCCESS" if code == 0 else "FAILED"
        base.update({"status": status, "ended_at": ended, "exit_code": code})
        _write_json(run_path, base)
        _append_jsonl(runs_index, base)
        _write_json(hb_path, {"job_name": job_name, "status": status, "job_run_id": run_id, "ts": ended})
        lf.write(f"[{ended}] END code={code}\n")

    try:
        lock_path.unlink()
    except FileNotFoundError:
        pass
    return 0 if code == 0 else 1


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-name", required=True)
    parser.add_argument("--tier", default="system")
    parser.add_argument("--heartbeat-sec", type=int, default=10)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()

    cmd = args.command
    if cmd and cmd[0] == "--":
        cmd = cmd[1:]
    if not cmd:
        raise SystemExit("Missing command after --")

    rc = run_job(args.job_name, args.tier, cmd, heartbeat_sec=args.heartbeat_sec)
    raise SystemExit(rc)


if __name__ == "__main__":
    main()
