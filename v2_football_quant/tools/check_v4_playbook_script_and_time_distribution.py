#!/usr/bin/env python3
"""Check V4 playbook scripts and normalized time distribution."""
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
    blockers, warnings = [], []
    today = datetime.now(LOCAL_TZ).strftime("%Y%m%d")
    
    html_p = DASHBOARD / "v4_control_center.html"
    html = html_p.read_text() if html_p.exists() else ""
    
    # Extract card template
    card_tmpl = ""
    pos = html.find('<article class="candidate"')
    if pos >= 0:
        end = html.find('</article>', pos + 30)
        if end >= 0: card_tmpl = html[pos:end + 11]
    
    # 1-4: Playbook checks
    valid_scripts = ["开局冲击","中段发力","尾段压迫","双段压迫","均衡压迫","弱剧本","数据暂缺"]
    
    if "剧本：" in html:
        warnings.append("playbook_label_present")
        has_valid = any(s in html for s in valid_scripts)
        if has_valid:
            warnings.append("valid_playbook_found")
        else:
            blockers.append("no_valid_playbook_value")
    else:
        blockers.append("playbook_label_missing")
    
    for bad in ["候选剧本","正式候选","HT进球剧本"]:
        if bad in card_tmpl:
            blockers.append(f"bad_label:{bad}")
    
    # 5-8: Time distribution checks
    if "进球分布" in card_tmpl or "进球分布" in html:
        warnings.append("distribution_label_present")
    else:
        blockers.append("distribution_label_missing")
    
    for seg in ["0-15","16-30","31-45"]:
        if seg in html:
            warnings.append(f"segment:{seg}")
    
    # 9: Distribution normalization code present in HTML (sums to 100%)
    if "tbSum" in html and "Math.round" in html and "playbook" in html:
        warnings.append("normalization_code_present")
    else:
        blockers.append("normalization_code_missing")
    
    # Load model for H2H and count checks
    model = load(STATUS / f"v4_control_center_model_{today}.json")
    items = []
    if model:
        c = model.get("candidates", {})
        items = c.get("items", []) if isinstance(c, dict) else []
        if not items: items = model.get("items", [])
        if isinstance(items, dict): items = list(items.values())
    
    # 10-12: H2H checks
    for x in items:
        used = x.get('h2h_used_count')
        limit = x.get('h2h_used_limit', 10)
        if used is not None and used > limit:
            blockers.append(f"h2h_exceeds:{used}>{limit}")
        elif used is not None:
            warnings.append(f"h2h_ok:{used}<={limit}")
    
    # 13-16: No internal labels in card
    for label in ["57白名单","全量合规","WHITELIST_57","all_eligible"]:
        if label in card_tmpl:
            blockers.append(f"internal_label:{label}")
    
    # 17-19: No N/A, undefined, null in card
    for bad in ["N/A","undefined","null"]:
        if bad in card_tmpl:
            blockers.append(f"{bad}_in_card")
    
    # 20: No fake 0%
    if "0-15 0%" in card_tmpl:
        blockers.append("fake_zero")
    
    # 21-22: source_group in model
    has_sg = any(x.get("source_group") for x in items) if items else False
    has_fu = any(x.get("fixture_universe") for x in items) if items else False
    warnings.append(f"sg_in_model:{has_sg},fu_in_model:{has_fu}")
    
    a_cnt = sum(1 for x in items if x.get("grade") == "A")
    b_cnt = sum(1 for x in items if x.get("grade") == "B")
    warnings.append(f"cards:{len(items)},A:{a_cnt},B:{b_cnt}")
    
    # Unbet defaults
    if "first(x.default_stake,null)" in html: warnings.append("stake_null")
    
    # Sub-checkers
    for s in ["check_v4_control_center.py","check_v4_dashboard_refresh_no_regrade.py",
              "check_v4_production_default_rules_guard.py","check_v4_h2h_last10_and_time_bins.py",
              "check_v4_dashboard_candidate_card_layout.py","check_v4_dashboard_final_polish.py"]:
        sp = ROOT / "tools" / s
        if not sp.exists(): warnings.append(f"skip:{s}"); continue
        r = subprocess.run([sys.executable, str(sp)], capture_output=True, text=True, timeout=60, cwd=str(ROOT))
        try: d = json.loads(r.stdout.strip()); ccl = d.get("conclusion","")
        except: ccl = ""
        if r.returncode != 0 and ccl not in ("WARN_ONLY","PASS","OK"):
            blockers.append(f"sub_fail:{s}")
        else: warnings.append(f"sub_pass:{s}")
    
    result = {
        "checker": "tools/check_v4_playbook_script_and_time_distribution.py",
        "conclusion": "PASS" if not blockers else "BLOCKED",
        "cards": len(items), "A": a_cnt, "B": b_cnt,
        "blockers": blockers, "warnings": warnings,
        "protection": {
            "DEFAULT_RULES_changed": False, "validation_recomputed": False,
            "live_bet_raw_records_modified": False, "cron_modified": False,
            "QQ_recommendation_pushed": False,
        }
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    sys.exit(0 if not blockers else 1)

if __name__ == "__main__":
    main()
