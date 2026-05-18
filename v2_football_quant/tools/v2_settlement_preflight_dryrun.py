#!/usr/bin/env python3
"""Phase D.7 — Preflight Dry-Run."""
import argparse, json, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from engine.v2_settlement_preflight_guard import build_v2_settlement_preflight
SD = Path(__file__).resolve().parent.parent / "data" / "runtime" / "status"
CN = timezone(timedelta(hours=8))
def main():
    p=argparse.ArgumentParser(); p.add_argument("--date", required=False); a=p.parse_args()
    dk=a.date or datetime.now(CN).strftime("%Y%m%d"); r=build_v2_settlement_preflight(dk)
    o=SD/f"v2_settlement_preflight_{dk}.json"; o.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding="utf-8")
    d=r["decision"]
    print(json.dumps({"date":dk,"settlement_allowed":d["settlement_allowed"],"status":d["status"],
                       "blockers":d["reason_codes"],"marker":str(o)},ensure_ascii=False,indent=2))
    if not d["settlement_allowed"]: raise SystemExit(1)
if __name__=="__main__": main()
