from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
MONITOR_DIR = BASE_DIR / "data" / "live_monitor"
SNAP_DIR = BASE_DIR / "data" / "live_odds_snapshots"
OPS_DIR = BASE_DIR / "data" / "ops"


def _count_jsonl(path: Path) -> int:
    if not path.exists():
        return 0
    with open(path, encoding="utf-8") as f:
        return sum(1 for _ in f)


def _date_key(date_str: str) -> str:
    return date_str.replace("-", "")


def diagnose(date_str: str, scheduler_mode: str = "auto") -> dict:
    key = _date_key(date_str)
    task_file = MONITOR_DIR / f"v4_capture_tasks_{key}.json"
    raw_file = SNAP_DIR / key / "live_odds_raw.jsonl"
    norm_file = SNAP_DIR / key / "live_odds_normalized.jsonl"
    hb_dir = OPS_DIR / "heartbeats"
    run_file = OPS_DIR / "job_runs" / f"job_runs_{key}.jsonl"

    crontab_text = ""
    has_crontab = False
    has_v4_cron = False
    # Scheduler evidence: OpenClaw/Gateway may not use OS crontab.
    openclaw_cron_supported = False
    openclaw_cron_ok = False
    openclaw_cron_text = ""
    try:
        proc = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
        if proc.returncode == 0:
            crontab_text = proc.stdout
            has_crontab = True
            has_v4_cron = "v4_job_runner.py" in crontab_text
    except Exception:
        pass

    try:
        proc = subprocess.run(["openclaw", "cron", "list"], capture_output=True, text=True)
        openclaw_cron_supported = True
        if proc.returncode == 0:
            openclaw_cron_ok = True
            openclaw_cron_text = proc.stdout
    except Exception:
        # command unavailable in this runtime, keep unknown
        pass

    raw_rows = _count_jsonl(raw_file)
    norm_rows = _count_jsonl(norm_file)
    hb_files = list(hb_dir.glob("*.json"))
    run_rows = _count_jsonl(run_file)
    has_key = bool(os.environ.get("APIFOOTBALL_KEY"))

    # Runtime evidence can prove scheduler is working regardless of OS crontab.
    api_used = 0
    budget_file = BASE_DIR / "data" / "capture_audit" / f"v4_api_budget_audit_{key}.json"
    if budget_file.exists():
        try:
            api_used = int(json.loads(budget_file.read_text(encoding="utf-8")).get("daily_calls_used", 0) or 0)
        except Exception:
            api_used = 0
    runtime_capture_evidence = bool(task_file.exists() or raw_rows > 0 or norm_rows > 0 or run_rows > 0 or api_used > 0)

    issues = []
    if not runtime_capture_evidence:
        mode = (scheduler_mode or "auto").lower()
        if mode == "openclaw":
            if not openclaw_cron_ok:
                issues.append("OPENCLAW_SCHEDULER_NOT_OBSERVED")
        elif mode == "system":
            if not has_crontab:
                issues.append("NO_CRONTAB")
            elif not has_v4_cron:
                issues.append("CRONTAB_NO_V4_JOB_RUNNER")
        else:
            if not has_crontab and not openclaw_cron_ok:
                issues.append("NO_SCHEDULER_EVIDENCE")
            elif has_crontab and not has_v4_cron and not openclaw_cron_ok:
                issues.append("CRONTAB_NO_V4_JOB_RUNNER")
    if not has_key:
        issues.append("MISSING_APIFOOTBALL_KEY_IN_CURRENT_ENV")
    if not task_file.exists():
        issues.append("MISSING_CAPTURE_TASK_FILE")
    if raw_rows == 0:
        issues.append("NO_RAW_SNAPSHOTS")
    if not hb_files and run_rows == 0:
        issues.append("NO_JOB_HEARTBEAT_OR_RUN_LOG")

    out = {
        "date": key,
        "generated_at": datetime.now().isoformat(),
        "checks": {
            "has_crontab": has_crontab,
            "has_v4_cron": has_v4_cron,
            "openclaw_cron_supported": openclaw_cron_supported,
            "openclaw_cron_ok": openclaw_cron_ok,
            "has_api_key_in_current_shell": has_key,
            "task_file_exists": task_file.exists(),
            "raw_rows": raw_rows,
            "normalized_rows": norm_rows,
            "api_used_from_budget_audit": api_used,
            "runtime_capture_evidence": runtime_capture_evidence,
            "heartbeat_files": len(hb_files),
            "job_run_rows": run_rows,
        },
        "scheduler_hint": {
            "mode": (
                "openclaw_gateway"
                if openclaw_cron_ok
                else ("system_crontab" if has_crontab else "unknown")
            ),
            "requested_mode": scheduler_mode,
            "note": "OpenClaw Cron and OS crontab are different schedulers.",
        },
        "issues": issues,
        "suggested_next_steps": [
            "如果你使用 OpenClaw Cron，请忽略系统 crontab 缺失提示，以 OpenClaw 任务列表和产物为准",
            "在调度器运行环境注入 APIFOOTBALL_KEY（不是仅在交互终端 export）",
            "先手工跑 v4_runner + v4_live_capture_scheduler 验证 20260513 文件产生",
            "再观察 v4_ops_status / v4_ops_dashboard 是否出现 job 状态和快照增量",
        ],
    }
    if openclaw_cron_ok:
        out["checks"]["openclaw_cron_preview"] = openclaw_cron_text.splitlines()[:20]
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=datetime.now().strftime("%Y%m%d"))
    parser.add_argument("--scheduler-mode", choices=["auto", "openclaw", "system"], default="auto")
    args = parser.parse_args()
    print(json.dumps(diagnose(args.date, args.scheduler_mode), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
