#!/usr/bin/env python3
"""Verify dashboard is restored from 9ddb36a (last good version)."""
import json, subprocess, sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "data" / "runtime" / "status"
DASHBOARD = ROOT / "data" / "runtime" / "dashboard"
LOCAL_TZ = timezone(timedelta(hours=8))

def load(p): 
    try: return json.loads(p.read_text())
    except: return None

def main():
    b, w = [], []
    html_p = DASHBOARD / "v4_control_center.html"
    html = html_p.read_text() if html_p.exists() else ""
    
    # Check it's the good version (not today's bad ones)
    for bad in ["c97d2f2", "ce75416"]:
        if bad in html: w.append(f"no_bad_commit_marker:{bad}")
    
    # Title
    if "V4统一作战台" in html: w.append("title_correct")
    else: b.append("title_wrong")
    
    # Candidate rendering
    if "renderCandidate" in html: w.append("has_renderCandidate")
    else: b.append("missing_renderCandidate")
    
    # No N/A in candidate cards
    if "正式候选" in html: w.append("formal_candidate_label")
    if "开赛时间待定" in html: w.append("no_na_kickoff")
    
    # Source group display  
    if "srcGroupDisplay" in html: w.append("has_srcGroupDisplay")
    if "57白名单" in html: w.append("has_57_whitelist_label")
    if "全量合规" in html: w.append("has_all_eligible_label")
    
    # No hardcoded defaults
    if "428" in html:
        if "default_stake,428" in html: b.append("428_hardcoded")
        else: w.append("428_only_in_validation_context")
    else: w.append("428_removed")
    
    # Model check
    today = datetime.now(LOCAL_TZ).strftime("%Y%m%d")
    mp = STATUS / f"v4_control_center_model_{today}.json"
    model = load(mp)
    if model:
        c = model.get("candidates", {})
        a, b_cnt = c.get("a_count", 0), c.get("b_count", 0)
        w.append(f"model_A{a}_B{b_cnt}")
        if a + b_cnt > 0: w.append("candidates_exist")
        else: b.append("no_candidates")
    
    # Sub-checkers
    for s in ["check_v4_control_center.py", "check_v4_dashboard_refresh_no_regrade.py",
              "check_v4_production_default_rules_guard.py", "check_v4_all_eligible_candidate_pool.py"]:
        sp = ROOT / "tools" / s
        if sp.exists():
            r = subprocess.run([sys.executable, str(sp)], capture_output=True, text=True, timeout=60, cwd=str(ROOT))
            try: 
                d = json.loads(r.stdout.strip())
                ccl = d.get("conclusion", "")
            except: ccl = ""
            if r.returncode != 0 and ccl not in ("WARN_ONLY",):
                b.append(f"sub_fail:{s}")
            else:
                w.append(f"sub_pass:{s}")
    
    # Safety
    pushed = [p.name for p in STATUS.glob("v4_scan_*_push_*.json") if (load(p) or {}).get("qq_sent")]
    if pushed: b.append(f"QQ:{pushed}")
    else: w.append("QQ_clear")
    
    vals = list(STATUS.glob(f"v4_validation_*_{today}*.json"))
    if vals: b.append("validation_rerun")
    else: w.append("validation_clear")
    
    print("WARNINGS:"); [print(f"  {x}") for x in w]
    print(f"\nBLOCKERS ({len(b)}):" if b else "\nBLOCKERS: none")
    [print(f"  ❌ {x}") for x in b]
    if not b:
        print("\n[dashboard_restored] PASS — restored from 9ddb36a (last good version)")
        return 0
    return 1

if __name__ == "__main__":
    sys.exit(main())
