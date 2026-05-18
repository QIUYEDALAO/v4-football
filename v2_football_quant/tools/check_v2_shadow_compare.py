#!/usr/bin/env python3
"""Phase D.3.1 — V2 Shadow Compare Checker (guard-hardened, read-only)."""
import argparse, json, re, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

STATUS_DIR = Path(__file__).resolve().parent.parent / "data" / "runtime" / "status"
ENGINE_DIR = Path(__file__).resolve().parent.parent / "engine"
CN_TZ = timezone(timedelta(hours=8))

FORBIDDEN_PATTERNS = [
    (r'\bor\s+True\b', "tautology_or_true"),
    (r'all\(pool\.get', "tautology_all_pool_get"),
    (r'\bhardcoded\b', "hardcoded_phrase"),
    (r'\bby_design\b', "by_design_phrase"),
    (r'\bassumed_safe\b', "assumed_safe_phrase"),
]

def _load(p): return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=False, help="YYYYMMDD")
    args = parser.parse_args()
    dk = args.date or datetime.now(CN_TZ).strftime("%Y%m%d")

    cmp_path = STATUS_DIR / f"v2_shadow_compare_{dk}.json"
    out = STATUS_DIR / f"v2_shadow_compare_check_{dk}.json"
    errs, warns = [], []

    # Static source check
    src_path = ENGINE_DIR / "v2_shadow_compare.py"
    if src_path.exists():
        src = src_path.read_text(encoding="utf-8")
        for pat, label in FORBIDDEN_PATTERNS:
            if re.search(pat, src):
                errs.append(f"src_forbidden_pattern:{label}")

    if not cmp_path.exists():
        r = {"status": "BLOCKER", "exists": False, "errors": ["compare_marker_missing"], "date": dk}
        out.write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(r, ensure_ascii=False, indent=2)); raise SystemExit(2)

    m = _load(cmp_path)
    rep = m.get("report", {})

    for fld in ["production_dependency", "production_verified", "formal_v2_uses_cache", "shadow_affects_formal"]:
        if m.get(fld, True): errs.append(f"boundary_{fld}")
    for fld in ["no_api", "no_key_read", "no_push", "no_cron", "no_task_trigger", "no_bet_locked_write", "no_settlement_write"]:
        if not m.get(fld): errs.append(f"guard_{fld}")

    g = rep.get("guards", {})
    for fld in ["no_bet_locked_written", "no_qq_push", "no_settlement_write", "missed_not_promoted"]:
        if not g.get(fld, True): errs.append(f"guard_violation_{fld}")

    # lock_owner evidence checks
    lg_preserved = g.get("lock_owner_gap_preserved")
    lg_warning = g.get("lock_owner_gap_is_warning")
    lg_quality = g.get("lock_owner_evidence_quality", "missing")

    if lg_preserved is None:
        errs.append("LG_PRESERVED_FIELD_MISSING")
    if lg_warning is None:
        errs.append("LG_IS_WARNING_FIELD_MISSING")
    if not lg_quality or lg_quality not in ("strong", "partial", "missing"):
        errs.append("LG_EVIDENCE_QUALITY_INVALID")

    # Evidence quality enforcement
    if lg_quality != "strong":
        warns.append(f"LOCK_OWNER_EVIDENCE_{lg_quality.upper()}")
    if lg_warning and not lg_preserved:
        errs.append("LOCK_OWNER_GAP_NOT_PRESERVED")

    # Trace quality
    cmp = rep.get("compare", {})
    trace_q = cmp.get("candidate_to_lock_trace_quality", "missing")
    if trace_q != "strong":
        warns.append(f"TRACE_QUALITY_{trace_q.upper()}")

    # Compare-specific boundary
    outputs = rep.get("outputs", {})
    if outputs.get("bet_locked_count", 0) > 0:
        warns.append("NONZERO_BET_LOCKED_OUTPUT")

    # Secret scan
    sec = re.findall(r"sk-[A-Za-z0-9]{20,}|x-apisports-key", json.dumps(m, ensure_ascii=False))
    if sec: errs.append("secret_detected")

    status = "FAIL" if errs else ("WARN" if warns else "PASS")
    r = {
        "status": status,
        "exists": True,
        "production_dependency": m.get("production_dependency", True),
        "production_verified": m.get("production_verified", True),
        "formal_v2_uses_cache": m.get("formal_v2_uses_cache", True),
        "shadow_affects_formal": m.get("shadow_affects_formal", True),
        "no_api": m.get("no_api", False), "no_push": m.get("no_push", False),
        "no_cron": m.get("no_cron", False), "no_task_trigger": m.get("no_task_trigger", False),
        "no_bet_locked_write": m.get("no_bet_locked_write", False),
        "no_settlement_write": m.get("no_settlement_write", False),
        "missed_not_promoted": g.get("missed_not_promoted", False),
        "lock_owner_gap_preserved": lg_preserved,
        "lock_owner_gap_is_warning": lg_warning,
        "lock_owner_evidence_quality": lg_quality,
        "trace_quality": trace_q,
        "secret_safe": len(sec) == 0,
        "src_clean": len([e for e in errs if e.startswith("src_")]) == 0,
        "warnings": warns, "errors": errs,
        "date": dk, "generated_at": datetime.now(CN_TZ).isoformat(),
    }
    out.write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(r, ensure_ascii=False, indent=2))
    if status == "FAIL": raise SystemExit(1)

if __name__ == "__main__": main()
