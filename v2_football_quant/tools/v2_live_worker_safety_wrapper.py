#!/usr/bin/env python3
"""Phase D.8.11: V2 live worker safety wrapper (plan-only).

This tool does NOT execute live worker or supervisor.
It only generates a guarded plan marker for future D.8.12 approval gate.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
STATUS_DIR = BASE_DIR / "data" / "runtime" / "status"
CN = timezone(timedelta(hours=8))
SCHEMA_VERSION = "v2_live_worker_safety_wrapper.v1"
SECRET_PAT = re.compile(r"APIFOOTBALL_KEY|OPENCLAW_APIFOOTBALL_KEY|x-apisports-key|sk-[A-Za-z0-9]{20,}")


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def _staged_files() -> list[str]:
    p = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=BASE_DIR, text=True, capture_output=True)
    return [x.strip() for x in (p.stdout or "").splitlines() if x.strip()]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default="20260517")
    parser.add_argument("--window", default="midday", choices=["midday"])
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--no-push", action="store_true")
    parser.add_argument("--no-formal-state-write", action="store_true")
    parser.add_argument("--no-verified-write", action="store_true")
    parser.add_argument("--no-supervisor", action="store_true")
    args = parser.parse_args()

    date_key = str(args.date).replace("-", "")
    window = args.window

    warnings: list[str] = []
    blockers: list[str] = []
    risks: list[str] = []

    # required hard flags
    if not args.plan_only:
        blockers.append("missing_required_flag_plan_only")
    if not args.no_push:
        blockers.append("missing_required_flag_no_push")
    if not args.no_formal_state_write:
        blockers.append("missing_required_flag_no_formal_state_write")
    if not args.no_verified_write:
        blockers.append("missing_required_flag_no_verified_write")
    if not args.no_supervisor:
        blockers.append("missing_required_flag_no_supervisor")

    # validate upstream evidence (read-only)
    d810 = _load_json(STATUS_DIR / f"v2_window_worker_sandbox_observe_{date_key}_{window}.json", {})
    if not d810:
        warnings.append("d810_sandbox_observe_marker_missing")
    else:
        if d810.get("observe_scope") != "sandbox_worker_logic_only":
            warnings.append("d810_observe_scope_not_sandbox_worker_logic_only")
        if d810.get("formal_state_unchanged") is not True:
            warnings.append("d810_formal_state_unchanged_not_true")

    # risk scanning (read-only)
    supervisor_src = _read_text(BASE_DIR / "engine" / "v2_window_checker_with_watchdog.py")
    worker_src = _read_text(BASE_DIR / "engine" / "v2_window_worker.py")

    if "openclaw" in supervisor_src and "message" in supervisor_src and "send" in supervisor_src:
        risks.append("supervisor_direct_qq_push_path_exists")
    else:
        warnings.append("supervisor_push_path_not_detected_by_simple_scan")

    if "write_state" in worker_src:
        risks.append("worker_formal_state_write_path_exists")
    else:
        warnings.append("worker_write_state_path_not_detected")

    for field_name in ("official_bet_locked", "qq_required", "settlement_required"):
        if field_name in worker_src:
            risks.append(f"worker_field_write_{field_name}")
        else:
            warnings.append(f"worker_field_write_{field_name}_not_detected")

    # enforce this wrapper does not execute anything
    live_worker_executed = False
    supervisor_executed = False
    production_resume_executed = False
    formal_state_written = False
    qq_sent = False
    verified_written = False
    cron_modified = False
    api_called = False
    key_read = False

    staged = _staged_files()
    if any(x.startswith("data/state/") for x in staged):
        blockers.append("state_artifacts_staged")
    if any(x.startswith("data/runtime/") for x in staged):
        blockers.append("runtime_artifacts_staged")
    if any(x.startswith("data/paper_trading/") for x in staged):
        blockers.append("paper_trading_artifacts_staged")

    # static secret safety scan (source files only)
    static_text = "\n".join([supervisor_src, worker_src])
    if SECRET_PAT.search(static_text):
        warnings.append("secret_pattern_detected_in_scanned_sources")

    future_live_observe_plan = {
        "allowed_future_scope": "single_window_only",
        "supervisor_allowed": False,
        "no_push_required": True,
        "no_formal_state_write_required": True,
        "no_verified_write_required": True,
        "preflight_required": True,
        "watchdog_required": True,
        "boss_approval_required": True,
        "next_gate": "D.8.12_LIVE_WORKER_OBSERVE_APPROVAL",
    }

    if blockers:
        wrapper_status = "BLOCKER"
    elif any([
        live_worker_executed,
        supervisor_executed,
        qq_sent,
        verified_written,
        cron_modified,
        formal_state_written,
        api_called,
        key_read,
    ]):
        wrapper_status = "FAIL"
    elif warnings:
        wrapper_status = "WARN"
    else:
        wrapper_status = "READY_FOR_BOSS_REVIEW"

    result = {
        "schema_version": SCHEMA_VERSION,
        "date": date_key,
        "window": window,
        "wrapper_status": wrapper_status,
        "wrapper_mode": "plan_only",
        "plan_only": True,
        "live_worker_executed": live_worker_executed,
        "supervisor_executed": supervisor_executed,
        "production_resume_executed": production_resume_executed,
        "formal_state_written": formal_state_written,
        "qq_sent": qq_sent,
        "verified_written": verified_written,
        "cron_modified": cron_modified,
        "api_called": api_called,
        "key_read": key_read,
        "production_verified": False,
        "pipeline_ready": False,
        "future_live_observe_plan": future_live_observe_plan,
        "risks": sorted(set(risks)),
        "warnings": warnings,
        "blockers": blockers,
        "generated_at": datetime.now(CN).isoformat(),
    }

    out_path = STATUS_DIR / f"v2_live_worker_safety_wrapper_{date_key}_{window}.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if wrapper_status == "BLOCKER":
        raise SystemExit(2)
    if wrapper_status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
