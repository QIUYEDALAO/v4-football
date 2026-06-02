#!/usr/bin/env python3
"""Audit pyramid_unknown leagues in V4 all_eligible scans and suggest map entries."""
import json
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "data" / "runtime" / "status"

def load(p):
    try: return json.loads(p.read_text())
    except: return None

def main():
    # Load pyramid map
    with open(ROOT / "config" / "v4_league_pyramid_map.json") as f:
        pm = json.load(f)
    pyr = pm.get("pyramid_map", {})
    mapped_ids = set(pyr.keys())
    print(f"Pyramid map covers {len(mapped_ids)} league IDs")
    
    # Check latest candidate_view for pyramid_unknown trace
    cv_files = sorted(STATUS.glob("v4_official_candidate_view_*.json"))
    if not cv_files:
        print("No candidate_view found")
        return
    
    cv = load(cv_files[-1])
    print(f"\nLatest candidate_view: {cv_files[-1].name}")
    print(f"  WHITELIST_57 A: {cv.get('A_WHITELIST_57_count', '?')}, B: {cv.get('B_WHITELIST_57_count', '?')}")
    print(f"  OUTSIDE_57 A: {cv.get('A_OUTSIDE_57_count', '?')}, B: {cv.get('B_OUTSIDE_57_count', '?')}")
    
    # Check for pyramid_unknown in factors
    for label in ['A_candidates', 'B_candidates']:
        candidates = cv.get(label, [])
        for c in (candidates or []):
            if isinstance(c, dict):
                f = c.get('factors', {})
                if isinstance(f, dict):
                    unk = f.get('pyramid_unknown_count', 0)
                    excl = f.get('excluded_reasons', {})
                    if unk > 0 or excl.get('pyramid_unknown', 0) > 0:
                        print(f"\n  {label} candidate: {c.get('home_cn','?')} vs {c.get('away_cn','?')}")
                        print(f"    pyramid_unknown_count: {unk}")
                        print(f"    excluded_reasons: {excl}")
    
    # Check scan progress for remaining unknown
    prog_files = sorted(STATUS.glob("v4_outside57_progress_*.json"))
    if prog_files:
        prog = load(prog_files[-1])
        scanned = prog.get('done_count', 0)
        print(f"\nLast scan: {prog_files[-1].name}, scanned={scanned}")
    
    print(f"\nMapped league IDs ({len(mapped_ids)}):")
    print(f"  {sorted(mapped_ids, key=int)}")

if __name__ == "__main__":
    main()
