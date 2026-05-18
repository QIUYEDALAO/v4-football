#!/usr/bin/env python3
"""Phase D.5 — V2 Settlement Shadow Guard (read-only boundary verification)."""
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
SCHEMA_VERSION = "v2_settlement_shadow_guard.v1"

def _load(p, d=None):
    if not p.exists(): return d
    try: return json.loads(p.read_text(encoding="utf-8"))
    except: return d

def _today(): return datetime.now(CN_TZ).strftime("%Y%m%d")

def _settle_evidence_quality(targets, has_lo, all_wc, has_ob):
    """Compute settlement evidence quality with not_applicable support."""
    if targets == 0: return "not_applicable", True, "no_settlement_targets"
    if has_lo:
        if not all_wc: return "strong", False, "non_window_checker_lock_owner_detected"
        return "strong", True, "all_targets_have_window_checker_lock_owner" if has_ob else "lock_owner_ok_but_missing_official_bet_locked"
    return "partial", True, "settlement_targets_exist_but_lock_owner_field_missing"

def collect_settle(dk: str) -> dict:
    vp = PAPER_DIR / f"verified_{dk}.json"; sp = STATUS_DIR / f"v2_settle_push_{dk}.json"
    ts = STATUS_DIR / "task_status_v2_daily_settle.json"
    sources, uf = [], set()
    data = _load(vp)
    if data: sources.append(str(vp))
    if sp.exists(): sources.append(str(sp))
    if ts.exists(): sources.append(str(ts))
    results = data.get("results", []) if data else []
    targets = len(results)
    has_lo = False; all_wc = True; has_ob = False
    for r in results:
        if "lock_owner" in r: has_lo = True
        if r.get("lock_owner") != "window_checker": all_wc = False
        if "official_bet_locked" in r: has_ob = True
        else: uf.add("missing_official_bet_locked")
    if not has_lo: uf.add("lock_owner_missing")
    if not has_ob and targets > 0: uf.add("official_bet_locked_missing")
    tkeys = [f"{r.get('fixture_id','?')}|{r.get('home','?')}|{r.get('away','?')}" for r in results]
    lo_eq, _, _ = _settle_evidence_quality(targets, has_lo, all_wc, has_ob)
    return {"verified_found": vp.exists(), "task_status_found": ts.exists(),
            "push_marker_found": sp.exists(), "settlement_targets": targets,
            "target_keys": tkeys, "target_keys_quality": "strong" if tkeys else ("not_applicable" if targets==0 else "partial"),
            "lock_owner_evidence_quality": lo_eq,
            "official_lock_evidence_quality": "strong" if has_ob else ("not_applicable" if targets==0 else "partial"),
            "unknown_fields": sorted(uf), "evidence_sources": sources}

def collect_ds(dk: str) -> dict:
    p = STATUS_DIR / f"v2_daily_status_push_{dk}.json"; d = _load(p, {})
    return {"marker_found": p.exists(), "official_bet_locked": int(d.get("official_bet_locked",0) or 0),
            "missed_candidates": int(d.get("missed_candidates",0) or 0),
            "evidence_sources": [str(p)] if p.exists() else []}

def collect_wc(dk: str) -> dict:
    notify = STATUS_DIR / f"v2_window_notify_{dk}.json"
    data = _load(notify); nl = int(data.get("new_bet_locked",0) or 0) if data else 0
    raw = data.get("new_locks",[]) if data else []
    has_lo = any("lock_owner" in lk for lk in raw)
    lo_eq = "not_applicable" if (nl==0 and not raw) else ("strong" if has_lo else "partial")
    return {"marker_found": notify.exists(), "new_locks_count": nl, "bet_locked_count": nl,
            "lock_owner_evidence_quality": lo_eq, "evidence_sources": [str(notify)] if notify.exists() else []}

def collect_mc(dk: str) -> dict:
    p = AUDIT_DIR / f"v2_missed_lock_candidates_{dk}.json"; d = _load(p, {})
    cs = d.get("candidates", [])
    ckeys = [f"{c.get('fixture_id','?')}|{c.get('home_team',c.get('home','?'))}|{c.get('away_team',c.get('away','?'))}" for c in cs]
    return {"audit_found": p.exists(), "count": len(cs), "candidate_keys": ckeys,
            "candidate_keys_quality": "strong" if cs else "missing", "evidence_sources": [str(p)] if p.exists() else []}

def compare_settlement_guard(dk: str) -> dict:
    st = collect_settle(dk); ds = collect_ds(dk); wc = collect_wc(dk); mc = collect_mc(dk)
    notes = []
    targets = st["settlement_targets"]; ob = ds["official_bet_locked"]; nl = wc["new_locks_count"]
    zlzs = (targets == 0 and ob == 0)

    # ── Numeric conflict checks (cannot be true when numbers contradict) ──
    t_match_ob = None
    if targets == ob:
        t_match_ob = True
    elif ob == 0 and targets > 0:
        t_match_ob = False
        notes.append("SETTLEMENT_TARGETS_EXCEED_OFFICIAL_LOCKS")
    elif targets == 0 and ob > 0:
        t_match_ob = False
        notes.append("OFFICIAL_LOCKS_EXCEED_SETTLEMENT_TARGETS")

    wl_match = None
    if targets == nl:
        wl_match = True
    elif targets > 0 and nl == 0:
        wl_match = False
        notes.append("SETTLEMENT_TARGETS_EXCEED_WINDOW_LOCKS")
    elif nl > 0 and targets == 0:
        wl_match = False
        notes.append("WINDOW_LOCKS_EXCEED_SETTLEMENT_TARGETS")

    # ── missed candidates cross-reference ──
    mckeys = set(mc.get("candidate_keys", []))
    stkeys = set(st.get("target_keys", []))
    missed_absent = None
    if mckeys and stkeys:
        intersection = mckeys & stkeys
        missed_absent = len(intersection) == 0
        if not missed_absent:
            notes.append(f"MISSED_CANDIDATE_IN_SETTLEMENT_TARGETS:{len(intersection)}_matches")

    # ── lock_owner semantics ──
    lo_eq = st["lock_owner_evidence_quality"]
    has_lo = "lock_owner_missing" not in st.get("unknown_fields", [])
    only_wc = None
    if lo_eq == "not_applicable" or targets == 0:
        only_wc = None
    elif lo_eq == "partial":
        only_wc = None  # can't verify, field missing → null not true
    elif lo_eq == "strong" and has_lo:
        only_wc = True
    else:
        only_wc = None

    # ── official_lock_only ──
    ob_eq = st["official_lock_evidence_quality"]
    official_only = None
    if lo_eq == "not_applicable" or targets == 0:
        official_only = None
    elif t_match_ob is False:
        official_only = False
    elif t_match_ob is True and ob_eq == "strong":
        official_only = True
    else:
        official_only = None  # can't verify

    # ── gap semantics ──
    eq, gap_preserved, gap_reason = _settle_evidence_quality(targets, has_lo, True, True)
    sg_warn = lo_eq in ("partial", "missing")

    return {"settlement_targets_match_official_locks": t_match_ob,
            "settlement_targets_match_window_locks": wl_match,
            "missed_candidates_absent_from_settlement": missed_absent,
            "only_window_checker_locks": only_wc,
            "official_lock_only": official_only,
            "zero_lock_zero_settlement_consistent": zlzs,
            "settlement_evidence_quality": lo_eq,
            "settlement_gap_preserved": gap_preserved,
            "settlement_gap_is_warning": sg_warn,
            "settlement_gap_reason": gap_reason, "notes": notes}

def build_v2_settlement_shadow_guard(dk: str | None = None) -> dict:
    dk = dk or _today()
    st = collect_settle(dk); ds = collect_ds(dk); wc = collect_wc(dk); mc = collect_mc(dk)
    cmp = compare_settlement_guard(dk)
    warns = []; errs = []
    lo_eq = st["lock_owner_evidence_quality"]
    ob_eq = st["official_lock_evidence_quality"]
    if lo_eq == "partial": warns.append("SETTLE_LOCK_OWNER_EVIDENCE_PARTIAL")
    elif lo_eq == "missing": warns.append("SETTLE_LOCK_OWNER_EVIDENCE_MISSING")
    if ob_eq == "partial": warns.append("SETTLE_OFFICIAL_LOCK_EVIDENCE_PARTIAL")
    if cmp["missed_candidates_absent_from_settlement"] is False: errs.append("MISSED_IN_SETTLEMENT")
    if cmp["settlement_targets_match_official_locks"] is False: errs.append("SETTLEMENT_TARGETS_OFFICIAL_LOCKS_CONFLICT")
    if cmp["settlement_targets_match_window_locks"] is False: errs.append("SETTLEMENT_TARGETS_WINDOW_LOCKS_CONFLICT")
    if cmp["official_lock_only"] is False: errs.append("OFFICIAL_LOCK_ONLY_CONFLICT")
    if cmp["only_window_checker_locks"] is False: errs.append("NON_WINDOW_CHECKER_IN_SETTLEMENT")
    if st["settlement_targets"] > 0 and not st["verified_found"]: warns.append("SETTLE_VERIFIED_MISSING")
    overall = "FAIL" if errs else ("WARN" if warns else "PASS")
    report = {"schema_version": SCHEMA_VERSION, "date": dk, "mode": "settlement_shadow_guard",
              "generated_at": datetime.now(CN_TZ).isoformat(), "production_dependency": False, "production_verified": False,
              "formal_v2_uses_cache": False, "shadow_affects_formal": False,
              "boundaries": {"no_api": True, "no_key_read": True, "no_push": True, "no_cron": True,
                             "no_task_trigger": True, "no_settlement_rerun": True, "no_verified_write": True,
                             "no_strategy_recompute": True, "no_bet_locked_write": True, "no_settlement_write": True},
              "settlement": st, "daily_status": ds, "window_checker": wc, "missed_candidates": mc,
              "compare": cmp,
              "guards": {"no_settlement_rerun": True, "no_verified_write": True, "no_bet_locked_written": True,
                         "no_qq_push": True, "no_settlement_write": True, "missed_not_settled": cmp["missed_candidates_absent_from_settlement"] is not False,
                         "formal_link_untouched": True},
              "summary": {"overall_status": overall, "pass_count": sum([st["verified_found"], ds["marker_found"], wc["marker_found"], mc["audit_found"]]),
                          "warn_count": len(warns), "fail_count": len(errs), "missing_count": 0, "blocker_count": 0},
              "warnings": warns, "errors": errs}
    return report
