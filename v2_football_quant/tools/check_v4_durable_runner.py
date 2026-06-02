#!/usr/bin/env python3
"""Guard for V4 durable daily scan runner template and deployed modes."""
from __future__ import annotations

import argparse
import json
import plistlib
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "data/runtime/status"
RUNNER = ROOT / "tools/run_v4_durable_daily_scan.py"
SHELL = ROOT / "scripts/v4_daily_scan_runner.sh"
PLIST = ROOT / "deploy/launchd/com.openclaw.v4.daily_scan.plist.template"
DOC = ROOT / "docs/V4_DURABLE_RUNNER_PRODUCTION_GUARD_20260602.md"
OPENCLAW_JOBS = Path.home() / ".openclaw/cron/jobs.json"
INSTALLED_PLIST = Path.home() / "Library/LaunchAgents/com.openclaw.v4.daily_scan.plist"
LAUNCHD_LABEL = "com.openclaw.v4.daily_scan"


def _launchd_loaded() -> bool:
    try:
        cp = subprocess.run(
            ["launchctl", "list"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception:
        return False
    return LAUNCHD_LABEL in (cp.stdout + cp.stderr)


def _is_openclaw_read_only_status(payload_message: str) -> bool:
    text = payload_message or ""
    return (
        "tools/check_v4_durable_runner.py" in text
        and "engine/v4_scan_and_brief.py" not in text
        and "launchctl" in text
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["template", "deployed", "auto"], default="auto")
    args = parser.parse_args()

    checks: dict[str, bool] = {}
    runner = RUNNER.read_text(encoding="utf-8") if RUNNER.exists() else ""
    shell = SHELL.read_text(encoding="utf-8") if SHELL.exists() else ""
    doc = DOC.read_text(encoding="utf-8") if DOC.exists() else ""
    plist = plistlib.loads(PLIST.read_bytes()) if PLIST.exists() else {}
    try:
        jobs_obj = json.loads(OPENCLAW_JOBS.read_text(encoding="utf-8"))
    except Exception:
        jobs_obj = {}
    jobs = jobs_obj.get("jobs", []) if isinstance(jobs_obj, dict) else jobs_obj
    daily_jobs = [x for x in jobs if isinstance(x, dict) and x.get("name") == "V4_DAILY_SCAN_READONLY"]
    daily_job = daily_jobs[0] if len(daily_jobs) == 1 else {}
    payload = daily_job.get("payload", {}) if isinstance(daily_job, dict) else {}
    payload_message = str(payload.get("message") or "")
    launchd_loaded = _launchd_loaded()
    openclaw_read_only = _is_openclaw_read_only_status(payload_message)
    detected_mode = "deployed" if (launchd_loaded or openclaw_read_only or INSTALLED_PLIST.exists()) else "template"
    mode = detected_mode if args.mode == "auto" else args.mode

    checks["runner_exists"] = RUNNER.exists()
    checks["shell_exists"] = SHELL.exists()
    checks["launchd_template_exists"] = PLIST.exists()
    checks["doc_exists"] = DOC.exists()
    checks["single_flight_lock"] = "O_EXCL" in runner and "v4_durable_daily_scan.lock" in runner
    checks["atomic_status_write"] = "os.replace" in runner and ".tmp." in runner
    checks["heartbeat"] = "heartbeat_at" in runner and "HEARTBEAT_SECONDS" in runner
    checks["start_end_exit_code"] = all(x in runner for x in ["started_at", "ended_at", "scan_exit_code"])
    checks["log_path"] = "v4_durable_daily_scan_" in runner and "log_path" in runner
    checks["local_timeout"] = "timeout-seconds" in runner and "proc.terminate()" in runner
    checks["failure_separation"] = all(x in runner for x in ["scan_failure", "qq_failure", "qq_exit_code"])
    checks["catchup_is_status_only"] = all(x in runner for x in ["--detect-catchup", "NEED_MANUAL_CATCHUP", "auto_rerun"])
    checks["manual_oneshot_guarded"] = "--boss-approved-manual-oneshot" in runner
    checks["shell_calls_local_runner"] = "run_v4_durable_daily_scan.py" in shell and "--scheduled" in shell
    checks["launchd_runs_at_1200"] = plist.get("StartCalendarInterval") == {"Hour": 12, "Minute": 0}
    checks["launchd_calls_shell"] = any("scripts/v4_daily_scan_runner.sh" in str(x) for x in plist.get("ProgramArguments", []))
    checks["launchd_not_agentturn"] = "agentTurn" not in PLIST.read_text(encoding="utf-8") if PLIST.exists() else False
    checks["lifecycle_doc"] = all(x in doc for x in ["--mode template", "--mode deployed", "--mode auto"])
    checks["no_launchctl_in_submitted_files"] = "launchctl" not in runner and "launchctl" not in shell
    checks["no_openclaw_cron_mutation_in_submitted_files"] = "openclaw cron" not in runner and "openclaw cron" not in shell
    checks["openclaw_1200_job_singleton"] = len(daily_jobs) == 1
    checks["openclaw_1200_job_agentturn_status_shell"] = payload.get("kind") == "agentTurn"

    if mode == "template":
        checks["launchd_not_installed"] = not INSTALLED_PLIST.exists()
        checks["launchd_not_loaded"] = not launchd_loaded
        checks["openclaw_1200_template_isolated"] = daily_job.get("sessionTarget") == "isolated"
        checks["openclaw_1200_template_direct_scan"] = "engine/v4_scan_and_brief.py" in payload_message
        checks["template_mode_doc"] = "DEPLOY_APPROVAL_REQUIRED" in doc
        expected_launchd_loaded = False
        expected_isolated_dependency = True
        expected_next_action = "DEPLOY_APPROVAL_REQUIRED"
        openclaw_mode = "direct_scan_until_deploy"
    else:
        checks["launchd_installed"] = INSTALLED_PLIST.exists()
        checks["launchd_loaded"] = launchd_loaded
        checks["openclaw_1200_read_only_status_check"] = openclaw_read_only
        checks["openclaw_1200_not_direct_scan"] = "engine/v4_scan_and_brief.py" not in payload_message
        checks["deployed_mode_doc"] = "WAIT_NEXT_SCHEDULED_SCAN" in doc and "read-only status check" in doc
        expected_launchd_loaded = True
        expected_isolated_dependency = False
        expected_next_action = "WAIT_NEXT_SCHEDULED_SCAN"
        openclaw_mode = "read-only status check"

    blockers = [name for name, ok in checks.items() if not ok]
    result = {
        "schema_version": "v4_durable_runner_guard.v1",
        "mode": mode,
        "detected_mode": detected_mode,
        "conclusion": "PASS" if not blockers else "BLOCKER",
        "checks": checks,
        "blockers": blockers,
        "launchd_loaded": expected_launchd_loaded,
        "openclaw_1200_mode": openclaw_mode,
        "real_scan_ran": False,
        "isolated_session_dependency": expected_isolated_dependency,
        "next_action": expected_next_action,
    }
    STATUS.mkdir(parents=True, exist_ok=True)
    out = STATUS / "check_v4_durable_runner_result.json"
    tmp = out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(out)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not blockers else 2


if __name__ == "__main__":
    raise SystemExit(main())
