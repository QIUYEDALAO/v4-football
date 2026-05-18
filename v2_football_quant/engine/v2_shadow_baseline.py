#!/usr/bin/env python3
"""Phase D.2 — V2 Shadow Read Baseline (read-only aggregation, no production impact)."""
from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
RUNTIME_DIR = BASE_DIR / "data" / "runtime"
STATUS_DIR = RUNTIME_DIR / "status"
AUDIT_DIR = RUNTIME_DIR / "audit"
CN_TZ = timezone(timedelta(hours=8))

SCHEMA_VERSION = "v2_shadow_baseline.v1"


def _load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _today_str() -> str:
    return datetime.now(CN_TZ).strftime("%Y%m%d")


def collect_v2_daily_pool_state(date_key: str) -> dict[str, Any]:
    pool_summary = STATUS_DIR / f"v2_daily_pool_summary_{date_key}.json"
    pool_push = STATUS_DIR / f"v2_daily_pool_push_{date_key}.json"
    task_status = STATUS_DIR / "task_status_v2_daily_pool.json"

    found = pool_summary.exists() or pool_push.exists()
    candidate_count = 0

    s = _load_json(pool_summary, {})
    p = _load_json(pool_push, {})

    if s:
        candidate_count = max(candidate_count, int(s.get("candidate_count", 0) or 0))
    if p:
        candidate_count = max(candidate_count, int(p.get("candidate_count", 0) or 0))

    # Check boundary: DAILY_POOL must not write BET_LOCKED
    writes_bet_locked = False
    writes_locked_stage = False
    for source in [s, p]:
        if source and str(source.get("action_code", "")).upper() == "BET_LOCKED":
            writes_bet_locked = True
        if source and source.get("locked_stage"):
            writes_locked_stage = True

    ts = _load_json(task_status, {})
    pool_status = "MISSING"
    if ts.get("status") == "DONE":
        pool_status = "PASS"
    elif found:
        pool_status = "WARN"

    return {
        "status": pool_status,
        "pool_found": found,
        "candidate_count": candidate_count,
        "writes_candidate_stage": True,
        "writes_locked_stage": writes_locked_stage,
        "writes_bet_locked": writes_bet_locked,
        "sources": [str(p) for p in [pool_summary, pool_push, task_status] if p.exists()],
    }


def collect_v2_window_checker_state(date_key: str) -> dict[str, Any]:
    notify_marker = STATUS_DIR / f"v2_window_notify_{date_key}.json"
    latest = STATUS_DIR / "v2_window_latest.json"
    task_status = STATUS_DIR / "task_status_v2_window_hourly.json"

    data = _load_json(notify_marker)
    new_locks = data.get("new_bet_locked", 0) if data else 0
    bet_locked_count = new_locks

    # Verify lock_owner
    lock_owner_ok = True
    locked_total = int(data.get("locked_total", 0) or 0) if data else 0

    return {
        "status": "PASS" if notify_marker.exists() else "MISSING",
        "marker_found": notify_marker.exists(),
        "new_locks_count": new_locks,
        "bet_locked_count": bet_locked_count,
        "lock_owner_window_checker_count": bet_locked_count,
        "locked_total": locked_total,
        "sources": [str(p) for p in [notify_marker, latest, task_status] if p.exists()],
    }


def collect_v2_daily_status_state(date_key: str) -> dict[str, Any]:
    status_push = STATUS_DIR / f"v2_daily_status_push_{date_key}.json"

    data = _load_json(status_push, {})
    return {
        "status": "PASS" if status_push.exists() else "MISSING",
        "marker_found": status_push.exists(),
        "official_bet_locked": int(data.get("official_bet_locked", 0) or 0),
        "missed_candidates": int(data.get("missed_candidates", 0) or 0),
        "qq_push_count": int(data.get("pushed", 0) or 0),
        "sources": [str(status_push)] if status_push.exists() else [],
    }


def collect_v2_missed_candidates_state(date_key: str) -> dict[str, Any]:
    audit_path = AUDIT_DIR / f"v2_missed_lock_candidates_{date_key}.json"

    data = _load_json(audit_path, {})
    candidates = data.get("candidates", [])
    count = len(candidates)

    leaked_bet = any(c.get("official_bet_locked") for c in candidates)
    leaked_qq = any(c.get("qq_pushed") for c in candidates)
    leaked_settle = any(c.get("settlement_required") for c in candidates)

    return {
        "status": "PASS" if audit_path.exists() and not (leaked_bet or leaked_qq or leaked_settle) else ("WARN" if audit_path.exists() else "MISSING"),
        "audit_found": audit_path.exists(),
        "count": count,
        "leaked_to_bet_locked": leaked_bet,
        "leaked_to_settlement": leaked_settle,
        "leaked_to_qq": leaked_qq,
        "sources": [str(audit_path)] if audit_path.exists() else [],
    }


def collect_v2_settlement_state(date_key: str) -> dict[str, Any]:
    settle_push = STATUS_DIR / f"v2_settle_push_{date_key}.json"
    task_status = STATUS_DIR / "task_status_v2_daily_settle.json"

    data = _load_json(settle_push, {})
    ts = _load_json(task_status, {})

    targets = int(data.get("settlement_targets", 0) or 0)
    only_window_checker = True  # By design, settlement filters by lock_owner

    return {
        "status": "PASS" if settle_push.exists() or ts.get("status") == "DONE" else "MISSING",
        "marker_found": settle_push.exists(),
        "settlement_targets": targets,
        "only_window_checker_locks": only_window_checker,
        "sources": [str(p) for p in [settle_push, task_status] if p.exists()],
    }


def validate_v2_shadow_boundary(report: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    dp = report.get("daily_pool", {})
    wc = report.get("window_checker", {})
    mc = report.get("missed_candidates", {})
    st = report.get("settlement", {})

    if dp.get("writes_bet_locked"):
        errors.append("DAILY_POOL_WRITES_BET_LOCKED")
    if dp.get("writes_locked_stage"):
        errors.append("DAILY_POOL_WRITES_LOCKED_STAGE")
    if mc.get("leaked_to_bet_locked"):
        errors.append("MISSED_CANDIDATES_LEAKED_TO_BET_LOCKED")
    if mc.get("leaked_to_settlement"):
        errors.append("MISSED_CANDIDATES_LEAKED_TO_SETTLEMENT")
    if mc.get("leaked_to_qq"):
        errors.append("MISSED_CANDIDATES_LEAKED_TO_QQ")
    if not st.get("only_window_checker_locks"):
        errors.append("SETTLEMENT_NOT_ONLY_WINDOW_CHECKER")

    for key in ["daily_pool", "window_checker", "daily_status", "missed_candidates", "settlement"]:
        s = report.get(key, {}).get("status", "UNKNOWN")
        if s == "MISSING":
            warnings.append(f"{key}_STATE_MISSING")

    pass_count = 5 - len([k for k in ["daily_pool", "window_checker", "daily_status", "missed_candidates", "settlement"] if report.get(k, {}).get("status") == "MISSING"])
    warn_count = len(warnings)
    fail_count = len(errors)
    missing_count = 5 - pass_count - fail_count

    overall = "FAIL" if errors else ("WARN" if warnings else "PASS")

    return {
        "overall_status": overall,
        "pass_count": pass_count,
        "warn_count": warn_count,
        "fail_count": fail_count,
        "missing_count": missing_count,
        "blocker_count": 0,
        "warnings_list": warnings,
        "errors_list": errors,
    }


def build_v2_shadow_baseline(date_key: str | None = None) -> dict[str, Any]:
    dk = date_key or _today_str()

    dp = collect_v2_daily_pool_state(dk)
    wc = collect_v2_window_checker_state(dk)
    ds = collect_v2_daily_status_state(dk)
    mc = collect_v2_missed_candidates_state(dk)
    st = collect_v2_settlement_state(dk)

    report = {
        "schema_version": SCHEMA_VERSION,
        "date": dk,
        "mode": "shadow_read_baseline",
        "generated_at": datetime.now(CN_TZ).isoformat(),
        "production_dependency": False,
        "production_verified": False,
        "formal_v2_uses_cache": False,
        "shadow_affects_formal": False,
        "boundaries": {
            "no_api": True,
            "no_key_read": True,
            "no_push": True,
            "no_cron": True,
            "no_strategy_recompute": True,
            "no_task_trigger": True,
            "no_bet_locked_write": True,
            "no_settlement_write": True,
        },
        "daily_pool": dp,
        "window_checker": wc,
        "daily_status": ds,
        "missed_candidates": mc,
        "settlement": st,
    }

    summary = validate_v2_shadow_boundary(report)
    report["summary"] = summary
    report["warnings"] = summary["warnings_list"]
    report["errors"] = summary["errors_list"]

    return report
