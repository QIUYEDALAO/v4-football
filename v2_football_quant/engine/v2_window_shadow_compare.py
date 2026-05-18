#!/usr/bin/env python3
"""Phase D.4 — V2 window_checker Shadow Compare (read-only, no task re-run)."""
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
SCHEMA_VERSION = "v2_window_shadow_compare.v1"

def _load(p, d=None):
    if not p.exists(): return d
    try: return json.loads(p.read_text(encoding="utf-8"))
    except: return d

def _today(): return datetime.now(CN_TZ).strftime("%Y%m%d")

def collect_window_checker_marker(dk: str) -> dict:
    notify = STATUS_DIR / f"v2_window_notify_{dk}.json"
    latest = STATUS_DIR / "v2_window_latest.json"
    sources, uf = [], set()
    data = _load(notify)
    if data: sources.append(str(notify))
    if latest.exists(): sources.append(str(latest))

    new_locks = int(data.get("new_bet_locked", 0) or 0) if data else 0
    locks = data.get("new_locks", []) if data else []
    wc_count = 0
    for lk in locks:
        if "lock_owner" in lk:
            if lk.get("lock_owner") == "window_checker": wc_count += 1
        else: uf.add("lock_owner_missing")
    skip = data.get("skip_reason", data.get("window_status", "")) if data else ""
    eq = "strong" if (notify.exists() and not uf) else ("partial" if notify.exists() else "missing")
    return {"marker_found": notify.exists(), "latest_found": latest.exists(),
            "task_status": data.get("status", "UNKNOWN") if data else "MISSING",
            "skip_reason": skip, "new_locks_count": new_locks, "bet_locked_count": new_locks,
            "lock_owner_window_checker_count": wc_count,
            "lock_owner_evidence_quality": eq, "unknown_fields": sorted(uf), "evidence_sources": sources,
            "status": "PASS" if (notify.exists() and not uf) else ("WARN" if notify.exists() else "MISSING")}

def collect_ds(dk: str) -> dict:
    p = STATUS_DIR / f"v2_daily_status_push_{dk}.json"
    d = _load(p, {})
    return {"marker_found": p.exists(), "official_bet_locked": int(d.get("official_bet_locked", 0) or 0),
            "missed_candidates": int(d.get("missed_candidates", 0) or 0),
            "qq_push_count": int(d.get("pushed", 0) or 0), "evidence_sources": [str(p)] if p.exists() else []}

def collect_mc(dk: str) -> dict:
    p = AUDIT_DIR / f"v2_missed_lock_candidates_{dk}.json"
    d = _load(p, {})
    cs = d.get("candidates", [])
    return {"audit_found": p.exists(), "count": len(cs),
            "promoted_to_bet_locked": any(c.get("official_bet_locked") for c in cs),
            "pushed_to_qq": any(c.get("qq_pushed") for c in cs),
            "sent_to_settlement": any(c.get("settlement_required") for c in cs),
            "evidence_sources": [str(p)] if p.exists() else []}

def collect_settle(dk: str) -> dict:
    vp = PAPER_DIR / f"verified_{dk}.json"
    sp = STATUS_DIR / f"v2_settle_push_{dk}.json"
    ts = STATUS_DIR / "task_status_v2_daily_settle.json"
    sources, uf = [], set()
    data = _load(vp)
    if data: sources.append(str(vp))
    if sp.exists(): sources.append(str(sp))
    if ts.exists(): sources.append(str(ts))
    targets = len(data.get("results", [])) if data else 0
    has_lo = False; all_wc = True
    for r in (data.get("results", []) if data else []):
        if "lock_owner" in r:
            has_lo = True
            if r.get("lock_owner") != "window_checker": all_wc = False
        else: uf.add("lock_owner_missing")
    if not has_lo and targets > 0: uf.add("lock_owner_unavailable")
    only_wc = None
    if not sources: only_wc = None; eq = "missing"
    elif targets == 0: only_wc = True; eq = "partial"
    elif not has_lo: only_wc = True; eq = "partial"
    elif all_wc: only_wc = True; eq = "strong"
    else: only_wc = False; eq = "partial"
    return {"evidence_found": bool(sources), "settlement_targets": targets, "only_window_checker_locks": only_wc,
            "evidence_quality": eq, "unknown_fields": sorted(uf), "evidence_sources": sources}

def compare_window_outputs(dk: str) -> dict:
    wc = collect_window_checker_marker(dk)
    ds = collect_ds(dk)
    mc = collect_mc(dk)
    notes = []
    # Consistency checks
    nl = wc["new_locks_count"]; ob = ds["official_bet_locked"]; mcc = ds["missed_candidates"]
    nv_consistent = (nl == ob) or (nl == 0 and ob == 0)
    ob_matches = (nl == ob)
    missed_matches = (mcc == mc["count"])
    skip_consistent = None
    if nl == 0 and mc["count"] > 0: skip_consistent = True  # skip reason explains zero locks
    elif nl > 0 and mc["count"] == 0: skip_consistent = True
    lg_preserved = wc["lock_owner_evidence_quality"] != "strong"
    lg_warning = bool(wc["unknown_fields"])
    if not nv_consistent: notes.append("NEW_LOCKS_VS_DAILY_STATUS_MISMATCH")
    if not missed_matches: notes.append("MISSED_COUNT_MISMATCH")
    return {"new_locks_vs_daily_status_consistent": nv_consistent, "official_bet_locked_matches_new_locks": ob_matches,
            "missed_count_matches_status": missed_matches, "skip_reason_consistent": skip_consistent,
            "lock_owner_gap_preserved": lg_preserved, "lock_owner_gap_is_warning": lg_warning, "notes": notes}

def build_v2_window_shadow_compare(dk: str | None = None) -> dict:
    dk = dk or _today()
    wc = collect_window_checker_marker(dk); ds = collect_ds(dk)
    mc = collect_mc(dk); st = collect_settle(dk)
    cmp = compare_window_outputs(dk)
    warns = []; errs = []
    if not wc["marker_found"]: warns.append("WC_NOTIFY_MISSING")
    if wc["lock_owner_evidence_quality"] != "strong": warns.append(f"WC_LOCK_OWNER_{wc['lock_owner_evidence_quality'].upper()}")
    if st["evidence_quality"] != "strong": warns.append(f"SETTLE_EVIDENCE_{st['evidence_quality'].upper()}")
    if not cmp["new_locks_vs_daily_status_consistent"]:
        (warns if wc["lock_owner_evidence_quality"] == "partial" else errs).append("NEW_LOCKS_DS_CONFLICT" if wc["lock_owner_evidence_quality"] != "partial" else "NEW_LOCKS_DS_PARTIAL")
    if mc["promoted_to_bet_locked"]: errs.append("MISSED_PROMOTED")
    if mc["pushed_to_qq"]: errs.append("MISSED_QQ")
    if mc["sent_to_settlement"]: errs.append("MISSED_SETTLED")
    overall = "FAIL" if errs else ("WARN" if warns else "PASS")
    report = {"schema_version": SCHEMA_VERSION, "date": dk, "mode": "window_checker_shadow_compare",
              "generated_at": datetime.now(CN_TZ).isoformat(), "production_dependency": False, "production_verified": False,
              "formal_v2_uses_cache": False, "shadow_affects_formal": False,
              "boundaries": {"no_api": True, "no_key_read": True, "no_push": True, "no_cron": True,
                             "no_task_trigger": True, "no_window_checker_rerun": True, "no_strategy_recompute": True,
                             "no_bet_locked_write": True, "no_settlement_write": True},
              "window_checker": wc, "daily_status": ds, "missed_candidates": mc, "settlement_guard": st,
              "compare": cmp,
              "guards": {"no_window_checker_rerun": True, "no_bet_locked_written": True, "no_qq_push": True,
                         "no_settlement_write": True, "missed_not_promoted": not mc["promoted_to_bet_locked"], "formal_link_untouched": True},
              "summary": {"overall_status": overall, "pass_count": sum([wc["marker_found"], ds["marker_found"], mc["audit_found"]]),
                          "warn_count": len(warns), "fail_count": len(errs), "missing_count": 0, "blocker_count": 0},
              "warnings": warns, "errors": errs}
    return report
