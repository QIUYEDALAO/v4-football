#!/usr/bin/env python3
"""Phase D.8.12: approval gate before any live worker observe execution.

This checker is read-only and does not execute supervisor/worker.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
STATUS_DIR = BASE_DIR / "data" / "runtime" / "status"
CN = timezone(timedelta(hours=8))
SCHEMA_VERSION = "v2_live_worker_observe_approval_gate.v1"


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _read(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def _staged_files() -> list[str]:
    p = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=BASE_DIR, text=True, capture_output=True)
    return [x.strip() for x in (p.stdout or "").splitlines() if x.strip()]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default="20260517")
    parser.add_argument("--window", default="midday")
    args = parser.parse_args()

    date_key = str(args.date).replace("-", "")
    window = args.window

    warnings: list[str] = []
    blockers: list[str] = []
    blocking_risks: list[str] = []
    warn_risks: list[str] = []
    accepted_plan_risks: list[str] = []

    p_d810 = STATUS_DIR / f"v2_window_worker_sandbox_observe_{date_key}_{window}.json"
    p_d811 = STATUS_DIR / f"v2_live_worker_safety_wrapper_{date_key}_{window}.json"

    d810 = _load_json(p_d810, {})
    d811 = _load_json(p_d811, {})
    approval_packet = _load_json(STATUS_DIR / f"v2_limited_resume_approval_packet_{date_key}.json", {})
    validation_pack = _load_json(STATUS_DIR / f"v2_controlled_resume_validation_pack_{date_key}.json", {})
    qq_route = _load_json(STATUS_DIR / f"v2_qq_route_dryrun_{date_key}.json", {})

    if not p_d810.exists():
        blockers.append("d810_sandbox_marker_missing")
    if not p_d811.exists():
        blockers.append("d811_wrapper_marker_missing")

    d810_sandbox_passed = bool(
        isinstance(d810, dict)
        and str(d810.get("observe_status", "")).upper() in {"PASS", "WARN"}
        and d810.get("observe_scope") == "sandbox_worker_logic_only"
        and d810.get("formal_state_unchanged") is True
        and d810.get("formal_state_written") is False
        and d810.get("live_window_worker_executed") is False
        and d810.get("supervisor_executed") is False
    )

    d811_safety_wrapper_ready = bool(
        isinstance(d811, dict)
        and str(d811.get("wrapper_status", "")).upper() in {"READY_FOR_BOSS_REVIEW", "WARN"}
        and d811.get("wrapper_mode") == "plan_only"
        and d811.get("plan_only") is True
        and d811.get("live_worker_executed") is False
        and d811.get("supervisor_executed") is False
        and d811.get("formal_state_written") is False
    )

    supervisor_src = _read(BASE_DIR / "engine" / "v2_window_checker_with_watchdog.py")
    worker_src = _read(BASE_DIR / "engine" / "v2_window_worker.py")
    safety_wrapper_src = _read(BASE_DIR / "tools" / "v2_live_worker_safety_wrapper.py")

    direct_supervisor_risk = (
        "openclaw" in supervisor_src and "message" in supervisor_src and "send" in supervisor_src
    )
    formal_state_write_risk = "write_state" in worker_src
    qq_push_risk = direct_supervisor_risk or ("_push_system_event" in supervisor_src)
    verified_write_risk = "verified" in _read(BASE_DIR / "engine" / "v2_settle_with_watchdog.py")

    # availability checks for future live observe safeguards
    no_push_hook_available = ("--no-push" in safety_wrapper_src and "missing_required_flag_no_push" in safety_wrapper_src)

    # ── Phase D.8.12.2: read hardening marker for real guard status ──
    hardening_marker = STATUS_DIR / f"v2_live_observe_guard_hardening_{args.date}_{args.window}.json"
    if hardening_marker.exists():
        try:
            h = json.loads(hardening_marker.read_text(encoding="utf-8"))
            no_formal_state_write_hook_available = h.get("no_formal_state_write_hook_available", False)
            safe_sender_guard_available = h.get("safe_sender_guard_available", False)
            no_push_hook_available = h.get("no_push_hook_available", no_push_hook_available)
        except Exception:
            no_formal_state_write_hook_available = False
            safe_sender_guard_available = False
    else:
        no_formal_state_write_hook_available = False
        safe_sender_guard_available = False

    rollback_gate = approval_packet.get("rollback_gate", {}) if isinstance(approval_packet.get("rollback_gate"), dict) else {}
    watchdog_only_failure_available = bool(rollback_gate.get("report_watchdog_only", False))

    if direct_supervisor_risk:
        blocking_risks.append("direct_supervisor_risk")
    if formal_state_write_risk:
        blocking_risks.append("formal_state_write_risk")
    if not no_formal_state_write_hook_available:
        blocking_risks.append("no_formal_state_write_hook_missing")

    if qq_push_risk:
        warn_risks.append("qq_push_risk")
    if verified_write_risk:
        warn_risks.append("verified_write_risk")
    if not no_push_hook_available:
        warn_risks.append("no_push_hook_missing")
    if not safe_sender_guard_available:
        warn_risks.append("safe_sender_guard_missing")
    if not watchdog_only_failure_available:
        warn_risks.append("watchdog_only_failure_missing")

    pack_status = str(validation_pack.get("pack_status", "")).upper()
    if pack_status == "WARN":
        accepted_plan_risks.append("validation_pack_warn_retained")
    appr_status = str(approval_packet.get("approval_packet_status", "")).upper()
    if appr_status == "WARN":
        accepted_plan_risks.append("approval_packet_warn_retained")

    live_ready_now = bool(
        d810_sandbox_passed
        and d811_safety_wrapper_ready
        and no_push_hook_available
        and no_formal_state_write_hook_available
        and safe_sender_guard_available
        and watchdog_only_failure_available
        and not direct_supervisor_risk
        and not formal_state_write_risk
        and not qq_push_risk
    )

    live_worker_observe_approved = False
    live_worker_execution_allowed = False
    supervisor_execution_allowed = False
    formal_state_write_allowed = False
    qq_push_allowed = False
    verified_write_allowed = False
    cron_enable_allowed = False

    production_verified = False
    pipeline_ready = False

    if isinstance(d810, dict) and d810.get("production_verified") is True:
        blockers.append("d810_production_verified_true")
    if isinstance(d811, dict) and d811.get("production_verified") is True:
        blockers.append("d811_production_verified_true")

    staged = _staged_files()
    if any(x.startswith("data/state/") for x in staged):
        blockers.append("state_artifacts_staged")
    if any(x.startswith("data/runtime/") for x in staged):
        blockers.append("runtime_artifacts_staged")
    if any(x.startswith("data/paper_trading/") for x in staged):
        blockers.append("paper_trading_artifacts_staged")

    if any([
        live_worker_execution_allowed,
        supervisor_execution_allowed,
        formal_state_write_allowed,
        qq_push_allowed,
        verified_write_allowed,
        cron_enable_allowed,
    ]):
        blockers.append("execution_allowed_flag_true")

    if not d810_sandbox_passed:
        warnings.append("d810_sandbox_not_passed")
    if not d811_safety_wrapper_ready:
        warnings.append("d811_safety_wrapper_not_ready")

    if blockers:
        approval_gate_status = "BLOCKER"
    elif not d810_sandbox_passed or not d811_safety_wrapper_ready:
        approval_gate_status = "NOT_READY"
    elif live_ready_now:
        approval_gate_status = "READY_FOR_BOSS_REVIEW"
    elif blocking_risks:
        approval_gate_status = "NOT_READY"
    else:
        approval_gate_status = "WARN"

    result = {
        "schema_version": SCHEMA_VERSION,
        "date": date_key,
        "window": window,
        "current_level": "CODE_READY",
        "pipeline_ready": pipeline_ready,
        "production_verified": production_verified,
        "approval_gate_status": approval_gate_status,
        "live_worker_observe_approved": live_worker_observe_approved,
        "live_worker_execution_allowed": live_worker_execution_allowed,
        "supervisor_execution_allowed": supervisor_execution_allowed,
        "formal_state_write_allowed": formal_state_write_allowed,
        "qq_push_allowed": qq_push_allowed,
        "verified_write_allowed": verified_write_allowed,
        "cron_enable_allowed": cron_enable_allowed,
        "boss_approval_required": True,
        "readiness": {
            "d810_sandbox_passed": d810_sandbox_passed,
            "d811_safety_wrapper_ready": d811_safety_wrapper_ready,
            "no_push_hook_available": no_push_hook_available,
            "no_formal_state_write_hook_available": no_formal_state_write_hook_available,
            "safe_sender_guard_available": safe_sender_guard_available,
            "watchdog_only_failure_available": watchdog_only_failure_available,
            "live_ready_now": live_ready_now,
        },
        "risk_classification": {
            "blocking_risks": sorted(set(blocking_risks)),
            "warn_risks": sorted(set(warn_risks)),
            "accepted_plan_risks": sorted(set(accepted_plan_risks)),
        },
        "d813_draft": {
            "allowed_to_generate": True,
            "allowed_to_execute": False,
            "scope": "single-window live worker observe only after explicit BOSS approval and only if no-push/no-write hooks are complete",
        },
        "warnings": warnings,
        "blockers": blockers,
        "generated_at": datetime.now(CN).isoformat(),
    }

    out = STATUS_DIR / f"v2_live_worker_observe_approval_gate_{date_key}_{window}.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if approval_gate_status == "BLOCKER":
        raise SystemExit(2)
    if approval_gate_status == "NOT_READY":
        raise SystemExit(0)


if __name__ == "__main__":
    main()
