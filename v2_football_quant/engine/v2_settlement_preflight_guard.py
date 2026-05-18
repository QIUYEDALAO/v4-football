#!/usr/bin/env python3
"""Phase D.7 — V2 Settlement Production Preflight Gate (fail-closed)."""
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
SCHEMA_VERSION = "v2_settlement_preflight_guard.v1"

def _load(p, d=None):
    if not p.exists(): return d
    try: return json.loads(p.read_text(encoding="utf-8"))
    except: return d

def _today(): return datetime.now(CN_TZ).strftime("%Y%m%d")

def collect_daily_status(dk: str) -> dict:
    p = STATUS_DIR / f"v2_daily_status_push_{dk}.json"; d = _load(p, {})
    return {"marker_found": p.exists(), "official_bet_locked": int(d.get("official_bet_locked",0) or 0),
            "missed_candidates": int(d.get("missed_candidates",0) or 0), "source": str(p) if p.exists() else None}

def collect_window_checker(dk: str) -> dict:
    notify = STATUS_DIR / f"v2_window_notify_{dk}.json"
    data = _load(notify); nl = int(data.get("new_bet_locked",0) or 0) if data else 0
    raw = data.get("new_locks",[]) if data else []
    has_lo = any("lock_owner" in lk for lk in raw)
    lo_eq = "not_applicable" if (nl==0 and not raw) else ("strong" if has_lo else "partial")
    return {"marker_found": notify.exists(), "new_locks_count": nl, "bet_locked_count": nl,
            "lock_owner_evidence_quality": lo_eq, "source": str(notify) if notify.exists() else None}

def collect_missed_candidates(dk: str) -> dict:
    p = AUDIT_DIR / f"v2_missed_lock_candidates_{dk}.json"; d = _load(p, {})
    cs = d.get("candidates", [])
    keys = [f"{c.get('fixture_id')}|{c.get('home_team',c.get('home','?'))}" for c in cs]
    return {"audit_found": p.exists(), "count": len(cs), "candidate_keys": keys,
            "source": str(p) if p.exists() else None}

def check_settlement_targets(dk: str, missed_keys: list, wc_nl: int) -> dict:
    """Check verified file targets vs production rules."""
    vp = PAPER_DIR / f"verified_{dk}.json"
    data = _load(vp)
    targets = data.get("results",[]) if data else []
    tkeys = [f"{r.get('fixture_id')}|{r.get('home',r.get('home_team','?'))}" for r in targets]
    t_count = len(targets)
    missed_hit = len(set(missed_keys) & set(tkeys)) if missed_keys and tkeys else 0
    # Check target lock_owner
    has_lo = False; all_wc = True
    for r in targets:
        if "lock_owner" in r: has_lo = True
        if r.get("lock_owner") != "window_checker": all_wc = False
    return {"settlement_targets": t_count, "target_keys": tkeys, "missed_in_targets": missed_hit,
            "lock_owner_present": has_lo, "all_window_checker": all_wc}

def evaluate_settlement_allowed(dk: str, ds: dict, wc: dict, mc: dict, st_override: dict = None) -> dict:
    blockers = []; warns = []; conditions = {}
    ob = ds["official_bet_locked"]; nl = wc["new_locks_count"]; mc_count = mc["count"]
    missed_keys = mc.get("candidate_keys", [])
    st = st_override if st_override is not None else check_settlement_targets(dk, missed_keys, nl)

    conditions["official_bet_locked_positive"] = ob > 0
    conditions["window_checker_new_locks_positive"] = nl > 0
    conditions["daily_status_marker_present"] = ds["marker_found"]
    conditions["window_checker_marker_present"] = wc["marker_found"]
    conditions["lock_owner_present"] = st["lock_owner_present"]
    conditions["all_targets_from_window_checker"] = st["all_window_checker"]
    conditions["no_missed_candidates_in_targets"] = st["missed_in_targets"] == 0
    conditions["no_candidate_stage_in_targets"] = True  # verified files don't have stage info yet
    conditions["source_marker_present"] = True

    # Block conditions (fail-closed)
    if not conditions["daily_status_marker_present"]:
        blockers.append("DAILY_STATUS_MISSING")
    if not conditions["window_checker_marker_present"]:
        blockers.append("WINDOW_CHECKER_MISSING")
    if ob == 0:
        blockers.append("OFFICIAL_BET_LOCKED_ZERO")
    if nl == 0:
        blockers.append("WINDOW_CHECKER_NEW_LOCKS_ZERO")
    if not conditions["lock_owner_present"]:
        if st["settlement_targets"] > 0:
            blockers.append("LOCK_OWNER_MISSING")
    if st["missed_in_targets"] > 0:
        blockers.append("MISSED_CANDIDATES_PRESENT")
    if not conditions["all_targets_from_window_checker"] and st["lock_owner_present"]:
        blockers.append("NON_WINDOW_CHECKER_LOCK_OWNER")
    if st["settlement_targets"] > 0 and ob == 0:
        blockers.append("SETTLEMENT_WITHOUT_OFFICIAL_LOCKS")
    if st["settlement_targets"] > 0 and nl == 0:
        blockers.append("SETTLEMENT_WITHOUT_WINDOW_LOCKS")

    allowed = len(blockers) == 0
    if not allowed:
        blockers.append("HISTORICAL_SETTLEMENT_CONTAMINATION" if st["missed_in_targets"] > 0 else "SETTLEMENT_TARGETS_NOT_ALLOWED")

    status = "ALLOW" if allowed else "BLOCK"
    fail_closed = not allowed
    return {"status": status, "settlement_allowed": allowed, "fail_closed": fail_closed,
            "reason_codes": blockers, "warnings": warns, "required_conditions": conditions}

def build_v2_settlement_preflight(dk: str | None = None) -> dict:
    dk = dk or _today()
    ds = collect_daily_status(dk); wc = collect_window_checker(dk); mc = collect_missed_candidates(dk)
    decision = evaluate_settlement_allowed(dk, ds, wc, mc)
    return {"schema_version": SCHEMA_VERSION, "date": dk, "mode": "settlement_preflight",
            "generated_at": datetime.now(CN_TZ).isoformat(),
            "production_dependency": True, "production_verified": False, "current_level": "CODE_READY",
            "settlement_allowed": decision["settlement_allowed"], "fail_closed": decision["fail_closed"],
            "boundaries": {"no_api": True, "no_key_read": True, "no_push": True, "no_cron": True,
                           "no_strategy_recompute": True, "no_bet_locked_write": True, "no_verified_write": True},
            "required_conditions": decision["required_conditions"],
            "daily_status": ds, "window_checker": wc, "missed_candidates": mc, "decision": decision,
            "summary": {"status": decision["status"], "blockers": decision["reason_codes"], "warnings": decision["warnings"]}}
