#!/usr/bin/env python3
"""Check V4 daily scan notification routing separation.

This checker is static/read-only. It does not run scan, send QQ, mutate cron,
or touch launchd. The active OpenClaw cron source must use the watchdog-check
task name, while keeping the payload read-only so a status check cannot
masquerade as a real scan completion notification.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "data/runtime/status"
NOTIFY = ROOT / "tools/notify_cron_task_complete_qq.py"
RUNNER = ROOT / "tools/run_v4_durable_daily_scan.py"
OPENCLAW_JOBS = Path.home() / ".openclaw/cron/jobs.json"


def read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def load_jobs() -> list[dict]:
    try:
        data = json.loads(OPENCLAW_JOBS.read_text(encoding="utf-8"))
    except Exception:
        return []
    jobs = data.get("jobs", []) if isinstance(data, dict) else data
    return [j for j in jobs if isinstance(j, dict)]


def extract_task_config_block(text: str) -> str:
    start = text.find("TASK_CONFIG = {")
    end = text.find("STATUS_MARKER_MAP = {")
    return text[start:end] if start != -1 and end != -1 else ""


def main() -> int:
    notify = read(NOTIFY)
    runner = read(RUNNER)
    task_config = extract_task_config_block(notify)
    jobs = load_jobs()
    watchdog_jobs = [
        j for j in jobs
        if j.get("name") in {"V4_DAILY_SCAN_READONLY", "V4_DAILY_SCAN_WATCHDOG_CHECK"}
    ]
    watchdog_payload = ""
    active_watchdog_name = None
    if len(watchdog_jobs) == 1:
        active_watchdog_name = watchdog_jobs[0].get("name")
        watchdog_payload = str((watchdog_jobs[0].get("payload") or {}).get("message") or "")

    checks = {
        "notify_script_exists": NOTIFY.exists(),
        "runner_exists": RUNNER.exists(),
        "watchdog_task_defined": '"V4_DAILY_SCAN_WATCHDOG_CHECK"' in task_config,
        "real_scan_task_defined": '"V4_DAILY_SCAN_REAL_COMPLETED"' in task_config,
        "legacy_scan_task_not_in_notify_config": '"V4_DAILY_SCAN_READONLY"' not in task_config,
        "watchdog_text_distinct": "【V4值守检查完成】" in notify and "不代表真实扫描完成" in notify,
        "real_scan_text_distinct": "【V4真实扫描完成】" in notify and "【V4扫描失败/超时/无产物】" in notify,
        "real_scan_artifact_reader": all(
            token in notify
            for token in [
                "read_real_scan_artifacts",
                "scan_perf_v4_",
                "scout_v4_",
                "v4_openclaw_brief_",
                "v4_official_candidate_view_",
                "v4_durable_daily_scan_status.json",
                "artifact_guard_status",
            ]
        ),
        "real_scan_counts_in_text": all(
            token in notify
            for token in ["total/scouted", "A/B/C/SKIP", "API calls"]
        ),
        "no_long_shadow_c_skip_table": all(
            token not in notify
            for token in ["C_candidates", "SKIP_candidates", "shadow-only long table"]
        ),
        "runner_calls_real_scan_notify": '"V4_DAILY_SCAN_REAL_COMPLETED"' in runner,
        "runner_notifies_not_legacy_readonly": '"V4_DAILY_SCAN_READONLY"' not in runner,
        "runner_writes_notify_pending_status": "SCAN_COMPLETED_NOTIFY_PENDING" in runner,
        "runner_notify_after_scan_process": runner.find("SCAN_COMPLETED_NOTIFY_PENDING") < runner.find("V4_DAILY_SCAN_REAL_COMPLETED"),
        "active_watchdog_job_singleton": len(watchdog_jobs) == 1,
        "active_watchdog_name_renamed": active_watchdog_name == "V4_DAILY_SCAN_WATCHDOG_CHECK",
        "active_watchdog_not_direct_scan": "engine/v4_scan_and_brief.py" not in watchdog_payload,
        "active_watchdog_no_real_scan_completion_notify": "V4_DAILY_SCAN_REAL_COMPLETED" not in watchdog_payload,
        "active_watchdog_status_only": "check_v4_durable_runner.py" in watchdog_payload and "launchctl" in watchdog_payload,
        "secrets_not_in_notify_text": not re.search(r"(?i)(api[_-]?key|token|secret)\\s*[:=]\\s*['\\\"][A-Za-z0-9_\\-]{16,}", notify),
        "secrets_not_in_runner_text": not re.search(r"(?i)(api[_-]?key|token|secret)\\s*[:=]\\s*['\\\"][A-Za-z0-9_\\-]{16,}", runner),
    }
    warnings = []
    blockers = [name for name, ok in checks.items() if not ok]
    result = {
        "schema_version": "v4_daily_scan_notification_routing_guard.v1",
        "conclusion": "PASS" if not blockers else "BLOCKER",
        "checks": checks,
        "blockers": blockers,
        "warnings": warnings,
        "active_watchdog_name": active_watchdog_name,
        "desired_watchdog_name": "V4_DAILY_SCAN_WATCHDOG_CHECK",
        "real_scan_task": "V4_DAILY_SCAN_REAL_COMPLETED",
        "cron_modified": False,
        "launchd_modified": False,
        "real_scan_ran": False,
        "qq_sent": False,
        "runtime_artifact_commit_required": False,
    }
    STATUS.mkdir(parents=True, exist_ok=True)
    out = STATUS / "check_v4_daily_scan_notification_routing_20260606.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not blockers else 2


if __name__ == "__main__":
    raise SystemExit(main())
