#!/usr/bin/env python3
"""Phase D.3 — V2 Shadow Compare Checker (read-only boundary verification)."""
import argparse, json, re, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

STATUS_DIR = Path(__file__).resolve().parent.parent / "data" / "runtime" / "status"
CN_TZ = timezone(timedelta(hours=8))

def _load(p): return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=False, help="YYYYMMDD")
    args = parser.parse_args()
    dk = args.date or datetime.now(CN_TZ).strftime("%Y%m%d")

    cmp_path = STATUS_DIR / f"v2_shadow_compare_{dk}.json"
    out = STATUS_DIR / f"v2_shadow_compare_check_{dk}.json"
    errs, warns = [], []

    if not cmp_path.exists():
        r = {"status": "BLOCKER", "baseline_exists": False, "errors": ["compare_marker_missing"], "date": dk}
        out.write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(r, ensure_ascii=False, indent=2)); raise SystemExit(2)

    m = _load(cmp_path)
    rep = m.get("report", {})

    for fld in ["production_dependency", "production_verified", "formal_v2_uses_cache", "shadow_affects_formal"]:
        if m.get(fld, True): errs.append(f"boundary_{fld}")
    for fld in ["no_api", "no_key_read", "no_push", "no_cron", "no_task_trigger", "no_bet_locked_write", "no_settlement_write"]:
        if not m.get(fld): errs.append(f"guard_{fld}")

    g = rep.get("guards", {})
    for fld in ["no_bet_locked_written", "no_qq_push", "no_settlement_write", "missed_not_promoted", "lock_owner_gap_preserved"]:
        if not g.get(fld, True): errs.append(f"guard_violation_{fld}")

    cmp = rep.get("compare", {})
    if cmp.get("candidate_to_lock_trace_quality") == "missing":
        warns.append("TRACE_MISSING")

    sec = re.findall(r"sk-[A-Za-z0-9]{20,}|x-apisports-key", json.dumps(m, ensure_ascii=False))
    if sec: errs.append("secret_detected")

    status = "FAIL" if errs else ("WARN" if warns else "PASS")
    r = {
        "status": status, "baseline_exists": True,
        "production_dependency": m.get("production_dependency", True),
        "production_verified": m.get("production_verified", True),
        "formal_v2_uses_cache": m.get("formal_v2_uses_cache", True),
        "shadow_affects_formal": m.get("shadow_affects_formal", True),
        "no_api": m.get("no_api", False), "no_push": m.get("no_push", False),
        "no_cron": m.get("no_cron", False), "no_task_trigger": m.get("no_task_trigger", False),
        "no_bet_locked_write": m.get("no_bet_locked_write", False),
        "no_settlement_write": m.get("no_settlement_write", False),
        "missed_not_promoted": g.get("missed_not_promoted", False),
        "lock_owner_gap_preserved": g.get("lock_owner_gap_preserved", False),
        "secret_safe": len(sec) == 0,
        "warnings": warns, "errors": errs,
        "date": dk, "generated_at": datetime.now(CN_TZ).isoformat(),
    }
    out.write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(r, ensure_ascii=False, indent=2))
    if status == "FAIL": raise SystemExit(1)

if __name__ == "__main__": main()
