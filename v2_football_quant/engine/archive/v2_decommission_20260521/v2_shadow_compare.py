#!/usr/bin/env python3
"""Phase D.3 — V2 DAILY_POOL Input Shadow Compare (read-only, no production impact)."""
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

SCHEMA_VERSION = "v2_shadow_compare.v1"


def _load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _today_str() -> str:
    return datetime.now(CN_TZ).strftime("%Y%m%d")


def _make_candidate_key(c: dict) -> str | None:
    """Create a unique candidate key from available fields."""
    fid = c.get("fixture_id")
    if not fid:
        return None
    home = c.get("home_team", c.get("home", "?"))
    away = c.get("away_team", c.get("away", "?"))
    return f"{fid}|{home}|{away}"


def collect_daily_pool_candidates(date_key: str) -> dict[str, Any]:
    pool_summary = STATUS_DIR / f"v2_daily_pool_summary_{date_key}.json"
    pool_push = STATUS_DIR / f"v2_daily_pool_push_{date_key}.json"
    missed_audit = AUDIT_DIR / f"v2_missed_lock_candidates_{date_key}.json"

    sources: list[str] = []
    candidates: list[dict] = []
    unknown_fields: set[str] = set()

    # Try pool_summary first
    s = _load_json(pool_summary)
    if s:
        sources.append(str(pool_summary))
        cs = s.get("candidates", s.get("all_candidates", []))
        candidates.extend(cs)

    # Try pool_push
    p = _load_json(pool_push)
    if p:
        sources.append(str(pool_push))
        cs = p.get("candidates", p.get("all_candidates", []))
        candidates.extend(cs)

    # Fall back to missed audit
    if not candidates and missed_audit.exists():
        sources.append(str(missed_audit))
        audit_data = _load_json(missed_audit, {})
        candidates = audit_data.get("candidates", [])

    # Deduplicate by fixture_id
    seen = set()
    deduped = []
    for c in candidates:
        fid = c.get("fixture_id")
        if fid and fid not in seen:
            seen.add(fid)
            deduped.append(c)

    # Check key fields
    for c in deduped:
        for fld in ["fixture_id", "home_team", "away_team", "league"]:
            if fld not in c:
                unknown_fields.add(f"candidate_missing_{fld}")

    key_quality = "strong" if not unknown_fields and deduped else ("partial" if deduped else "missing")

    return {
        "daily_pool_found": len(sources) > 0,
        "candidate_count": len(deduped),
        "candidate_key_quality": key_quality,
        "unknown_fields": sorted(unknown_fields),
        "evidence_sources": sources,
        "raw_candidates": deduped,
    }


def collect_window_checker_outputs(date_key: str) -> dict[str, Any]:
    notify = STATUS_DIR / f"v2_window_notify_{date_key}.json"
    latest = STATUS_DIR / "v2_window_latest.json"

    sources: list[str] = []
    unknown_fields: set[str] = set()

    data = _load_json(notify)
    if data:
        sources.append(str(notify))
    if latest.exists():
        sources.append(str(latest))

    new_locks = int(data.get("new_bet_locked", 0) or 0) if data else 0
    locks = data.get("new_locks", []) if data else []

    # Check lock fields
    for lk in locks:
        for fld in ["fixture_id", "lock_owner"]:
            if fld not in lk:
                unknown_fields.add(f"lock_missing_{fld}")

    return {
        "window_checker_found": notify.exists(),
        "new_locks_count": new_locks,
        "bet_locked_count": new_locks,
        "lock_key_quality": "strong" if not unknown_fields else "partial",
        "unknown_fields": sorted(unknown_fields),
        "evidence_sources": sources,
        "raw_locks": locks,
    }


def collect_daily_status_summary(date_key: str) -> dict[str, Any]:
    push = STATUS_DIR / f"v2_daily_status_push_{date_key}.json"
    data = _load_json(push, {})

    return {
        "daily_status_found": push.exists(),
        "official_bet_locked": int(data.get("official_bet_locked", 0) or 0),
        "missed_candidates": int(data.get("missed_candidates", 0) or 0),
        "evidence_sources": [str(push)] if push.exists() else [],
    }


def collect_missed_candidates(date_key: str) -> dict[str, Any]:
    audit = AUDIT_DIR / f"v2_missed_lock_candidates_{date_key}.json"
    data = _load_json(audit, {})

    return {
        "missed_found": audit.exists(),
        "missed_count": len(data.get("candidates", [])),
        "missed_raw": data.get("candidates", []),
        "evidence_sources": [str(audit)] if audit.exists() else [],
    }


def _compute_lg_preserved(pool: dict, wc: dict, ds: dict) -> bool:
    """lock_owner_gap_preserved: true means gap is reported, not that evidence is complete."""
    # If there's lock_owner evidence and it's NOT window_checker → not preserved (violation)
    # Otherwise the gap IS preserved (i.e., we're aware and reporting it)
    raw_locks = wc.get("raw_locks", [])
    for lk in raw_locks:
        if "lock_owner" in lk and lk.get("lock_owner") != "window_checker":
            return False  # violation detected
    return True  # gap preserved (no violation found, even if evidence missing)


def _compute_lg_is_warning(pool: dict, wc: dict, ds: dict) -> bool:
    """Returns True if lock_owner gap deserves a warning."""
    raw_locks = wc.get("raw_locks", [])
    if wc.get("new_locks_count", 0) > 0 and raw_locks:
        for lk in raw_locks:
            if "lock_owner" not in lk:
                return True  # locks exist but no lock_owner field
    # Also warn if pool candidates have unknown_fields about lock_owner
    if any("lock_owner" in f for f in pool.get("unknown_fields", [])):
        return True
    if any("lock_owner" in f for f in wc.get("unknown_fields", [])):
        return True
    return False


def _compute_lg_evidence_quality(pool: dict, wc: dict, ds: dict) -> str:
    """lock_owner evidence quality: strong/partial/missing."""
    raw_locks = wc.get("raw_locks", [])
    has_locks = wc.get("new_locks_count", 0) > 0
    if not has_locks and not raw_locks:
        return "partial"  # no locks to verify, no evidence needed
    has_lock_owner_fields = all("lock_owner" in lk for lk in raw_locks) if raw_locks else False
    if has_lock_owner_fields:
        return "strong"
    if raw_locks:
        return "partial"  # locks exist but missing lock_owner field
    if wc.get("window_checker_found"):
        return "partial"  # checker ran but no lock detail
    return "missing"


def compare_candidates_to_outputs(date_key: str) -> dict[str, Any]:
    notes: list[str] = []

    pool = collect_daily_pool_candidates(date_key)
    wc = collect_window_checker_outputs(date_key)
    ds = collect_daily_status_summary(date_key)
    mc = collect_missed_candidates(date_key)

    candidate_count = pool["candidate_count"]
    locks_count = wc["bet_locked_count"]
    missed_count = ds["missed_candidates"]
    official_bet = ds["official_bet_locked"]

    # Build candidate keys
    candidate_keys = {}
    for c in pool.get("raw_candidates", []):
        k = _make_candidate_key(c)
        if k:
            candidate_keys[k] = c

    # Build lock keys
    lock_keys = {}
    for lk in wc.get("raw_locks", []):
        fid = lk.get("fixture_id")
        if fid:
            lock_keys[fid] = lk

    # Build missed keys
    missed_keys = {}
    for m in mc.get("missed_raw", []):
        k = _make_candidate_key(m)
        if k:
            missed_keys[k] = m

    # Compare
    matched = 0
    locked_from_candidates = 0
    missed_from_candidates = len(missed_keys)
    unmatched_locks = max(0, locks_count - locked_from_candidates)
    unmatched_missed = len(set(missed_keys.keys()) - set(candidate_keys.keys()))

    # Can't trace due to missing candidate keys
    if not candidate_keys:
        notes.append("no_candidate_keys_available_cannot_trace")
    if not lock_keys:
        notes.append("no_lock_keys_available")

    # Reconcile
    if candidate_keys and lock_keys:
        for ck in candidate_keys:
            fid = int(ck.split("|")[0])
            if fid in lock_keys:
                matched += 1
                locked_from_candidates += 1

    # Trace quality
    trace_quality = "strong" if (candidate_keys and lock_keys) else ("partial" if candidate_keys else "missing")
    if not candidate_keys and not lock_keys:
        notes.append("full_trace_unavailable_both_sides_no_keys")

    # Guard checks
    guards = {
        "no_bet_locked_written": True,
        "no_qq_push": True,
        "no_settlement_write": True,
        "missed_not_promoted": True,
        "lock_owner_gap_preserved": _compute_lg_preserved(pool, wc, ds),
        "lock_owner_gap_is_warning": _compute_lg_is_warning(pool, wc, ds),
        "lock_owner_evidence_quality": _compute_lg_evidence_quality(pool, wc, ds),
    }

    # Missed check
    missed_raw = mc.get("missed_raw", [])
    for m in missed_raw:
        if m.get("official_bet_locked") is True:
            guards["missed_not_promoted"] = False
        if m.get("qq_pushed") is True:
            guards["no_qq_push"] = False
        if m.get("settlement_required") is True:
            guards["no_settlement_write"] = False

    errors: list[str] = []
    warnings: list[str] = []

    if not pool["daily_pool_found"]:
        warnings.append("DAILY_POOL_CANDIDATES_MISSING")
    if not wc["window_checker_found"]:
        warnings.append("WINDOW_CHECKER_OUTPUT_MISSING")
    if pool["candidate_key_quality"] == "missing":
        warnings.append("CANDIDATE_KEYS_MISSING")
    if trace_quality == "partial":
        warnings.append("TRACE_PARTIAL")
    if not guards["missed_not_promoted"]:
        errors.append("MISSED_CANDIDATES_PROMOTED")
    if not guards["no_qq_push"]:
        errors.append("MISSED_CANDIDATES_QQ_PUSHED")

    pass_count = sum([1 for g in [pool["daily_pool_found"], wc["window_checker_found"], ds["daily_status_found"], candidate_count >= 0]])
    fail_count = len(errors)
    overall = "FAIL" if errors else ("WARN" if warnings else "PASS")

    return {
        "matched_candidates": matched,
        "locked_from_candidates": locked_from_candidates,
        "missed_from_candidates": missed_from_candidates,
        "unmatched_locks": unmatched_locks,
        "unmatched_missed": unmatched_missed,
        "missing_candidate_keys": 0 if candidate_keys else candidate_count,
        "candidate_to_lock_trace_quality": trace_quality,
        "notes": list(set(notes)),
    }


def build_v2_shadow_compare(date_key: str | None = None) -> dict[str, Any]:
    dk = date_key or _today_str()

    pool = collect_daily_pool_candidates(dk)
    wc = collect_window_checker_outputs(dk)
    ds = collect_daily_status_summary(dk)
    mc = collect_missed_candidates(dk)
    compare = compare_candidates_to_outputs(dk)

    errors: list[str] = []
    warnings: list[str] = []
    compare["errors"] = errors  # Placeholder for validation

    # Build report
    report = {
        "schema_version": SCHEMA_VERSION,
        "date": dk,
        "mode": "daily_pool_input_shadow_compare",
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
            "no_task_trigger": True,
            "no_bet_locked_write": True,
            "no_settlement_write": True,
            "no_strategy_recompute": True,
        },
        "inputs": {
            "daily_pool_found": pool["daily_pool_found"],
            "candidate_count": pool["candidate_count"],
            "candidate_key_quality": pool["candidate_key_quality"],
            "unknown_fields": pool["unknown_fields"],
            "evidence_sources": pool["evidence_sources"],
        },
        "outputs": {
            "window_checker_found": wc["window_checker_found"],
            "new_locks_count": wc["new_locks_count"],
            "bet_locked_count": wc["bet_locked_count"],
            "daily_status_found": ds["daily_status_found"],
            "official_bet_locked": ds["official_bet_locked"],
            "missed_candidates": ds["missed_candidates"],
            "evidence_sources": wc["evidence_sources"] + ds["evidence_sources"],
        },
        "compare": compare,
        "guards": {
            "no_bet_locked_written": True,
            "no_qq_push": True,
            "no_settlement_write": True,
            "missed_not_promoted": True,
            "lock_owner_gap_preserved": _compute_lg_preserved(pool, wc, ds),
            "lock_owner_gap_is_warning": _compute_lg_is_warning(pool, wc, ds),
            "lock_owner_evidence_quality": _compute_lg_evidence_quality(pool, wc, ds),
        },
    }

    # Validate guards
    raw_mc = mc.get("missed_raw", [])
    for m in raw_mc:
        if m.get("official_bet_locked") is True:
            report["guards"]["missed_not_promoted"] = False
        if m.get("qq_pushed") is True:
            report["guards"]["no_qq_push"] = False
        if m.get("settlement_required") is True:
            report["guards"]["no_settlement_write"] = False

    # Warnings/errors
    all_warnings = compare.get("notes", []) + [w for w in [
        "DAILY_POOL_CANDIDATES_MISSING" if not pool["daily_pool_found"] else None,
        "WINDOW_CHECKER_OUTPUT_MISSING" if not wc["window_checker_found"] else None,
        "CANDIDATE_KEYS_PARTIAL" if pool["candidate_key_quality"] == "partial" else None,
        "TRACE_PARTIAL" if compare.get("candidate_to_lock_trace_quality") == "partial" else None,
    ] if w is not None]

    all_errors = []
    for m in raw_mc:
        if m.get("official_bet_locked") is True:
            all_errors.append("MISSED_PROMOTED_TO_BET_LOCKED")

    pass_count = sum([pool["daily_pool_found"], wc["window_checker_found"], ds["daily_status_found"]])
    fail_count = len(all_errors)
    overall = "FAIL" if all_errors else ("WARN" if all_warnings else "PASS")

    report["summary"] = {
        "overall_status": overall,
        "pass_count": pass_count,
        "warn_count": len(all_warnings),
        "fail_count": fail_count,
        "missing_count": 0,
        "blocker_count": 0,
    }
    report["warnings"] = all_warnings
    report["errors"] = all_errors

    return report
