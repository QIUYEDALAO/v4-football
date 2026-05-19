#!/usr/bin/env python3
"""V4 Today Source Resolver Checker — validates no hardcoding"""
import json, re, subprocess, sys
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]
RESOLVER = MODULE / "tools" / "v4_today_source_resolver.py"

def main():
    R = {"check_status":"PASS","help_ok":False,"resolver_exists":RESOLVER.is_file(),
         "today_parse_ok":False,"source_missing_ok":False,"hardcoded_free":False,
         "blockers":[],"warnings":[]}
    block = False
    if not RESOLVER.is_file(): R["blockers"].append("resolver missing"); _finish(R,True)

    r = subprocess.run(["python3",str(RESOLVER),"--help"],capture_output=True,text=True,timeout=30,cwd=str(MODULE))
    R["help_ok"] = "--date" in r.stdout

    # Test with 2026-05-19 (has source)
    r = subprocess.run(["python3",str(RESOLVER),"--date","2026-05-19","--no-push","--no-state-write","--no-verified-write"],capture_output=True,text=True,timeout=30,cwd=str(MODULE))
    try:
        d = json.loads(r.stdout.strip().split("\n")[0])
        R["today_parse_ok"] = True
        if d.get("hardcoded"): R["blockers"].append("hardcoded=true!"); block = True
        if d["source_mode"] == "SOURCE_MISSING": R["warnings"].append("05-19 source missing (unexpected)")
        if d.get("qq_sent"): R["blockers"].append("qq_sent=true"); block = True
        grades = [d.get(f"{k}_count") for k in ["A","B","C","SKIP"]]
        R["grades_05_19"] = {"A":grades[0],"B":grades[1],"C":grades[2],"SKIP":grades[3]}
        if not d.get("C_observation_only"): R["warnings"].append("C observation_only false")
        if not d.get("SKIP_not_recommendation"): R["warnings"].append("SKIP not_recommendation false")
    except Exception as e: R["blockers"].append(f"05-19 parse: {e}"); block = True

    # Test with 2026-05-20 (no source)
    r = subprocess.run(["python3",str(RESOLVER),"--date","2026-05-20","--no-push","--no-state-write","--no-verified-write"],capture_output=True,text=True,timeout=30,cwd=str(MODULE))
    try:
        d = json.loads(r.stdout.strip().split("\n")[0])
        R["source_missing_ok"] = True
        if d.get("hardcoded"): R["blockers"].append("hardcoded=true on missing date!"); block = True
        if d.get("total_matches") is not None: R["blockers"].append(f"total={d['total_matches']} on missing date (should be null)"); block = True
        if d.get("source_mode") != "SOURCE_MISSING": R["warnings"].append(f"Expected SOURCE_MISSING, got {d['source_mode']}")
        if d.get("blocker_reason") != "V4_TODAY_SOURCE_MISSING": R["warnings"].append(f"Blocker reason mismatch: {d.get('blocker_reason')}")
    except Exception as e: R["blockers"].append(f"05-20 parse: {e}"); block = True

    # Grep for hardcoded V4 today in tools
    for fp in ["tools/intel_ops_refresh.py","tools/intel_desk_builder.py"]:
        tf = MODULE / fp
        if tf.is_file():
            txt = tf.read_text()
            if re.search(r'"total":\s*5', txt) and re.search(r'"A":\s*0', txt):
                R["blockers"].append(f"{fp}: HARDCODED v4 today (total=5 A=0)"); block = True
    R["hardcoded_free"] = not block or "HARDCODED" not in str(R["blockers"])

    _finish(R,block)

def _finish(R,block):
    import re
    if block: R["check_status"]="BLOCKER"
    elif R["warnings"]: R["check_status"]="WARN"
    print("="*50); print("V4 TODAY SOURCE RESOLVER CHECKER"); print("="*50)
    print(f"Status: {R['check_status']}")
    for k in ["resolver_exists","help_ok","today_parse_ok","source_missing_ok","hardcoded_free"]:
        print(f"  {k}: {R[k]}")
    if R.get("grades_05_19"): print(f"  05-19 grades: {R['grades_05_19']}")
    if R["blockers"]: print(f"\nBLOCKERS ({len(R['blockers'])}):"); [print(f"  ! {b}") for b in R["blockers"]]; sys.exit(1)
    if R["warnings"]: print(f"\nWARNINGS ({len(R['warnings'])}):"); [print(f"  ~ {w}") for w in R["warnings"]]
    md = MODULE/"data"/"runtime"/"status"; md.mkdir(parents=True,exist_ok=True)
    (md/"v4_today_source_resolver_check.json").write_text(json.dumps(R,indent=2,ensure_ascii=False))
    sys.exit(0)

if __name__=="__main__": main()
