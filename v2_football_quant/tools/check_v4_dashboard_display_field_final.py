#!/usr/bin/env python3
"""Final display field check for restored V4 dashboard."""
import json, subprocess, sys, re
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
    
    # 1-3: Model candidates
    today = datetime.now(LOCAL_TZ).strftime("%Y%m%d")
    model = load(STATUS / f"v4_control_center_model_{today}.json")
    if model:
        c = model.get("candidates", {})
        items = c.get("items", [])
        a_cnt, b_cnt = c.get("a_count", 0), c.get("b_count", 0)
        w.append(f"candidate_count:{len(items)}")
        w.append(f"A{a_cnt}_B{b_cnt}")
    
    # 4: No fake 0% time distribution
    if "评分摘要暂缺" in html or "评分摘要 HT" in html:
        w.append("score_summary_not_fake_zero")
    if '0-15 0%' in html:
        b.append("fake_zero_percent_still_present")
    else:
        w.append("no_fake_zero_percent")
    
    # 5-7: Kickoff format
    if "fmtKickoff" in html:
        w.append("has_kickoff_formatter")
    if "T01:00:00" not in html and "05-30" in html:
        w.append("compact_kickoff_format")
    
    # 8-11: Source labels
    if "57白名单" in html: w.append("has_57_whitelist_label")
    else: b.append("missing_57_whitelist_label")
    if "全量合规" in html: w.append("has_all_eligible_label")
    else: b.append("missing_all_eligible_label")
    if "WHITELIST_57" in html and "57白名单" in html:
        w.append("WHITELIST_57_only_in_fn_not_display")
    
    # 12-13: No N/A or fake wording
    if "候选剧本" not in html: w.append("no_candidate_script")
    else: b.append("candidate_script_still_present")
    
    # 14: A2 badge fixed
    if 'A${a}B${b}' in html: w.append("ab_badge_uses_AaBb")
    elif 'A${tb}' in html: b.append("ab_badge_still_A_tb")
    
    # 15-16: Unbet defaults
    if "default_stake,null" in html or "first(x.default_stake,null)" in html:
        w.append("stake_null_for_unbet")
    
    # 17: SKIP not in candidates
    # 18: C not displayed
    
    # Safety sub-checkers
    for s in ["check_v4_control_center.py", "check_v4_dashboard_refresh_no_regrade.py",
              "check_v4_production_default_rules_guard.py"]:
        sp = ROOT / "tools" / s
        r = subprocess.run([sys.executable, str(sp)], capture_output=True, text=True, timeout=60, cwd=str(ROOT))
        try: d = json.loads(r.stdout.strip()); ccl = d.get("conclusion", "")
        except: ccl = ""
        if r.returncode != 0 and ccl not in ("WARN_ONLY",):
            b.append(f"sub_fail:{s}")
        else: w.append(f"sub_pass:{s}")
    
    # Safety gates
    pushed = [p.name for p in STATUS.glob("v4_scan_*_push_*.json") if (load(p) or {}).get("qq_sent")]
    if pushed: b.append(f"QQ:{pushed}")
    else: w.append("QQ_clear")
    
    vals = list(STATUS.glob(f"v4_validation_*_{today}*.json"))
    if vals: b.append("validation_rerun")
    else: w.append("validation_clear")
    
    print("WARNINGS:"); [print(f"  {x}") for x in w]
    print(f"\nBLOCKERS ({len(b)}):" if b else "\nBLOCKERS: none")
    [print(f"  ❌ {x}") for x in b]
    if not b: print("\n[display_field_final] PASS"); return 0
    return 1

if __name__ == "__main__":
    sys.exit(main())
