#!/usr/bin/env python3
"""Intel Ops Display Enhancer — match lists, C/SKIP reasons, rolling stats"""
import json, sys, time
from datetime import date, timedelta
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]

def rolling_stats(attribution_dir, days, ref_date):
    """Compute rolling A+B HIT/MISS for N days before ref_date."""
    total_ab = 0; total_hit = 0; total_miss = 0
    for i in range(days):
        d = ref_date - timedelta(days=i+1)
        af = attribution_dir / f"v4_result_attribution_{d.strftime('%Y%m%d')}.jsonl"
        if af.is_file():
            rows = [json.loads(l) for l in af.read_text().split("\n") if l.strip()]
            for r in rows:
                if r.get("pre_grade") in ("A","B"):
                    total_ab += 1
                    if r.get("model_result") == "MODEL_HIT": total_hit += 1
                    elif r.get("model_result") == "MODEL_MISS": total_miss += 1
    return {"days": days, "AB": total_ab, "HIT": total_hit, "MISS": total_miss,
            "rate": f"{total_hit/total_ab*100:.1f}%" if total_ab > 0 else "N/A",
            "sufficient": total_ab >= 10}

def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--latest", action="store_true")
    p.add_argument("--rolling-windows", default="7,14,30")
    p.add_argument("--no-push", action="store_true")
    p.add_argument("--no-state-write", action="store_true")
    p.add_argument("--no-verified-write", action="store_true")
    args = p.parse_args()

    intel_dir = MODULE / "reports" / "intel_desk"
    jsons = sorted(intel_dir.glob("INTEL_DASHBOARD_20*.json"), reverse=True)
    if not jsons:
        print(json.dumps({"status":"DEGRADED","reason":"no dashboard JSON"})); return 1

    dash = json.loads(jsons[0].read_text())

    # V4 today match details from source
    v4_matches = []
    v4t = dash.get("v4_today", {}) or {}
    src_file = v4t.get("source_file", "")
    if src_file and not v4t.get("source_mode") == "SOURCE_MISSING":
        sf = MODULE / src_file
        v4_matches.append({"source_file": src_file, "source_mode": v4t.get("source_mode"),
                          "source_freshness": v4t.get("source_freshness"),
                          "total": v4t.get("total_matches"),
                          "A": v4t.get("A_count"), "B": v4t.get("B_count"),
                          "C": v4t.get("C_count"), "SKIP": v4t.get("SKIP_count")})

    # Rolling stats
    archive = MODULE / "data" / "v4_archive"
    ref = date.fromisoformat(dash.get("date", time.strftime("%Y-%m-%d"))[:10].replace("/","-"))
    rolling = {}
    for w in [int(x) for x in args.rolling_windows.split(",")]:
        rolling[str(w)] = rolling_stats(archive, w, ref)

    result = {"status":"DONE","date":dash.get("date"),
              "v4_matches": v4_matches, "rolling": rolling,
              "qq_sent": False, "state_written": False, "verified_written": False,
              "proof_executed": False}
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0

if __name__=="__main__": sys.exit(main())
