#!/usr/bin/env python3
"""Phase D.2.1 — V2 Shadow Read Baseline (evidence-hardened, read-only aggregation)."""
from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
RUNTIME_DIR = BASE_DIR / "data" / "runtime"
STATUS_DIR = RUNTIME_DIR / "status"
AUDIT_DIR = RUNTIME_DIR / "audit"
PAPER_DIR = BASE_DIR / "data" / "paper_trading"
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

    sources: list[str] = []
    found = False
    candidate_count = 0
    writes_bet_locked = False
    writes_locked_stage = False
    unknown_fields: list[str] = []

    for path in [pool_summary, pool_push]:
        data = _load_json(path)
        if data:
            found = True
            sources.append(str(path))
            candidate_count = max(candidate_count, int(data.get("candidate_count", 0) or 0))
            # Check for BET_LOCKED in pool output
            candidates = data.get("candidates", data.get("all_candidates", []))
            for c in (candidates or [])[:50]:
                ac = str(c.get("action_code", c.get("action", ""))).upper()
                if ac == "BET_LOCKED":
                    writes_bet_locked = True
                if c.get("locked_stage"):
                    writes_locked_stage = True
                if c.get("official_bet_locked") is True:
                    writes_bet_locked = True
                # Collect unknown fields
                if "lock_owner" not in c:
                    unknown_fields.append("lock_owner_missing_in_candidates")

    if task_status.exists():
        sources.append(str(task_status))

    evidence_quality = "strong" if found and not unknown_fields else ("partial" if found else "missing")
    unknown_fields = sorted(set(unknown_fields))

    return {
        "status": "PASS" if (found and not writes_bet_locked and not writes_locked_stage) else ("FAIL" if (writes_bet_locked or writes_locked_stage) else "MISSING"),
        "pool_found": found,
        "candidate_count": candidate_count,
        "writes_candidate_stage": True,
        "writes_locked_stage": writes_locked_stage,
        "writes_bet_locked": writes_bet_locked,
        "evidence_sources": sources,
        "evidence_quality": evidence_quality,
        "unknown_fields": unknown_fields,
        "assumptions": [],
    }


def collect_v2_window_checker_state(date_key: str) -> dict[str, Any]:
    notify_marker = STATUS_DIR / f"v2_window_notify_{date_key}.json"
    latest = STATUS_DIR / "v2_window_latest.json"
    task_status = STATUS_DIR / "task_status_v2_window_hourly.json"

    sources: list[str] = []
    unknown_fields: list[str] = []
    assumptions: list[str] = []

    data = _load_json(notify_marker)
    if data:
        sources.append(str(notify_marker))

    new_locks = int(data.get("new_bet_locked", 0) or 0) if data else 0
    locked_total = int(data.get("locked_total", 0) or 0) if data else 0

    # Check for explicit lock_owner
    locks = data.get("new_locks", []) if data else []
    wc_locks = 0
    has_lock_owner_field = False
    for lock in (locks or []):
        if "lock_owner" in lock:
            has_lock_owner_field = True
            if lock.get("lock_owner") == "window_checker":
                wc_locks += 1

    if not has_lock_owner_field and new_locks > 0:
        unknown_fields.append("lock_owner_missing_in_window_notify")
        assumptions.append("all_bet_locked_assumed_window_checker_by_design")

    for p in [latest, task_status]:
        if p.exists():
            sources.append(str(p))

    evidence_quality = "strong" if (notify_marker.exists() and not unknown_fields) else ("partial" if notify_marker.exists() else "missing")

    return {
        "status": "PASS" if notify_marker.exists() else "MISSING",
        "marker_found": notify_marker.exists(),
        "new_locks_count": new_locks,
        "bet_locked_count": new_locks,
        "lock_owner_window_checker_count": wc_locks if has_lock_owner_field else new_locks,
        "locked_total": locked_total,
        "evidence_sources": sources,
        "evidence_quality": evidence_quality,
        "unknown_fields": unknown_fields,
        "assumptions": assumptions,
    }


def collect_v2_daily_status_state(date_key: str) -> dict[str, Any]:
    status_push = STATUS_DIR / f"v2_daily_status_push_{date_key}.json"

    data = _load_json(status_push, {})
    sources = [str(status_push)] if status_push.exists() else []
    unknown_fields: list[str] = []

    ob_locked = int(data.get("official_bet_locked", 0) or 0)
    missed = int(data.get("missed_candidates", 0) or 0)
    qq_count = int(data.get("pushed", 0) or 0)

    if "official_bet_locked" not in data and status_push.exists():
        unknown_fields.append("official_bet_locked_missing")

    evidence_quality = "strong" if (status_push.exists() and not unknown_fields) else ("partial" if status_push.exists() else "missing")

    return {
        "status": "PASS" if status_push.exists() else "MISSING",
        "marker_found": status_push.exists(),
        "official_bet_locked": ob_locked,
        "missed_candidates": missed,
        "qq_push_count": qq_count,
        "evidence_sources": sources,
        "evidence_quality": evidence_quality,
        "unknown_fields": unknown_fields,
        "assumptions": [],
    }


def collect_v2_missed_candidates_state(date_key: str) -> dict[str, Any]:
    audit_path = AUDIT_DIR / f"v2_missed_lock_candidates_{date_key}.json"

    data = _load_json(audit_path, {})
    sources = [str(audit_path)] if audit_path.exists() else []
    unknown_fields: list[str] = []

    candidates = data.get("candidates", [])
    count = len(candidates)

    leaked_bet = False
    leaked_qq = False
    leaked_settle = False

    for c in candidates:
        if c.get("official_bet_locked") is True:
            leaked_bet = True
        if c.get("qq_pushed") is True:
            leaked_qq = True
        if c.get("settlement_required") is True:
            leaked_settle = True
        # Check field completeness
        for fld in ["official_bet_locked", "qq_pushed", "settlement_required"]:
            if fld not in c:
                unknown_fields.append(f"candidate_missing_{fld}")

    unknown_fields = sorted(set(unknown_fields))
    evidence_quality = "strong" if (audit_path.exists() and not unknown_fields) else ("partial" if audit_path.exists() else "missing")

    return {
        "status": "PASS" if (audit_path.exists() and not (leaked_bet or leaked_qq or leaked_settle)) else ("WARN" if audit_path.exists() and not (leaked_bet or leaked_qq or leaked_settle) else "FAIL"),
        "audit_found": audit_path.exists(),
        "count": count,
        "leaked_to_bet_locked": leaked_bet,
        "leaked_to_settlement": leaked_settle,
        "leaked_to_qq": leaked_qq,
        "evidence_sources": sources,
        "evidence_quality": evidence_quality,
        "unknown_fields": unknown_fields,
        "assumptions": [],
    }


def collect_v2_settlement_state(date_key: str) -> dict[str, Any]:
    settle_push = STATUS_DIR / f"v2_settle_push_{date_key}.json"
    task_status = STATUS_DIR / "task_status_v2_daily_settle.json"
    verified_path = PAPER_DIR / f"verified_{date_key}.json"

    sources: list[str] = []
    unknown_fields: list[str] = []
    assumptions: list[str] = []

    # Read settlement markers
    sp_data = _load_json(settle_push)
    if sp_data:
        sources.append(str(settle_push))

    if task_status.exists():
        sources.append(str(task_status))

    # Read verified file for settlement targets
    verified = _load_json(verified_path)
    targets = 0
    has_lock_owner = False
    all_wc = True
    non_wc_fixtures: list[int] = []

    if verified:
        sources.append(str(verified_path))
        results = verified.get("results", [])
        targets = len(results)
        for r in results:
            if "lock_owner" in r:
                has_lock_owner = True
                if r.get("lock_owner") != "window_checker":
                    all_wc = False
                    non_wc_fixtures.append(r.get("fixture_id", 0))
            else:
                unknown_fields.append("lock_owner_missing_in_verified")

    # Evidence quality assessment
    if not sources:
        only_window_checker = False  # can't verify
        evidence_quality = "missing"
        assumptions.append("no_settlement_evidence_available")
    elif targets == 0:
        only_window_checker = True
        evidence_quality = "partial"
        assumptions.append("no_targets_to_verify_settlement_empty")
    elif not has_lock_owner:
        only_window_checker = True  # can't disprove
        evidence_quality = "partial"
        assumptions.append("lock_owner_field_missing_all_settled_assumed_safe")
        unknown_fields.append("lock_owner_unavailable")
    elif not all_wc:
        only_window_checker = False
        evidence_quality = "partial"  # evidence says FAIL but not fully verified
        assumptions.append(f"non_window_checker_settlements_detected:{len(non_wc_fixtures)}")
    else:
        only_window_checker = True
        evidence_quality = "strong"

    status = "PASS" if (only_window_checker and evidence_quality != "missing") else ("WARN" if (evidence_quality == "partial" and only_window_checker) else ("WARN" if targets == 0 else "FAIL"))

    return {
        "status": status,
        "marker_found": settle_push.exists() or verified_path.exists(),
        "settlement_targets": targets,
        "has_lock_owner_evidence": has_lock_owner,
        "only_window_checker_locks": only_window_checker,
        "evidence_sources": sources,
        "evidence_quality": evidence_quality,
        "unknown_fields": sorted(set(unknown_fields)),
        "assumptions": assumptions,
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
    if st.get("evidence_quality") == "missing":
        warnings.append("SETTLEMENT_EVIDENCE_MISSING")
    if "lock_owner_field_missing" in str(st.get("assumptions", [])):
        warnings.append("SETTLEMENT_LOCK_OWNER_FIELD_MISSING")

    # Evidence quality warnings
    for key in ["daily_pool", "window_checker", "daily_status", "missed_candidates", "settlement"]:
        s = report.get(key, {}).get("status", "UNKNOWN")
        eq = report.get(key, {}).get("evidence_quality", "missing")
        uf = report.get(key, {}).get("unknown_fields", [])
        if s == "MISSING":
            warnings.append(f"{key}_STATE_MISSING")
        if eq == "missing":
            warnings.append(f"{key}_EVIDENCE_MISSING")
        elif eq == "partial":
            warnings.append(f"{key}_EVIDENCE_PARTIAL")
        if uf:
            warnings.append(f"{key}_UNKNOWN_FIELDS:{','.join(uf[:2])}")

    pass_count = sum(1 for k in ["daily_pool", "window_checker", "daily_status", "missed_candidates", "settlement"] if report.get(k, {}).get("status") not in ("MISSING", "FAIL"))
    fail_count = len(errors)
    missing_count = 5 - pass_count - fail_count

    overall = "FAIL" if errors else ("WARN" if warnings else "PASS")

    return {
        "overall_status": overall,
        "pass_count": pass_count,
        "warn_count": len(warnings),
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
