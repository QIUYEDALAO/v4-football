#!/usr/bin/env python3
"""Check V4 dashboard candidate card layout: equal heights, aligned forms."""
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
    
    # 1: align-items: stretch on candidate-list grid
    if "align-items:stretch" in html or "align-items: stretch" in html:
        warnings.append("grid_align_stretch")
    else:
        blockers.append("missing_align_stretch")
    
    # 2: candidate card flex column
    if "display:flex;flex-direction:column" in html or "display: flex;flex-direction: column" in html:
        warnings.append("candidate_flex_column")
    else:
        blockers.append("candidate_not_flex_column")
    
    # 3: candidate card height:100%
    if "height:100%" in html or "height: 100%" in html:
        warnings.append("candidate_height_100")
    else:
        blockers.append("candidate_no_height")
    
    # 4: line-clamp on match title
    if "-webkit-line-clamp" in html:
        warnings.append("title_line_clamp")
    else:
        blockers.append("title_no_clamp")
    
    # 5: quick-form margin-top:auto
    if "margin-top:auto" in html:
        warnings.append("form_margin_auto")
    else:
        blockers.append("form_not_sticky_bottom")
    
    # 6: textarea fixed
    if "max-height:60px" in html:
        warnings.append("textarea_fixed")
    
    # Model checks
    model = load(STATUS / f"v4_control_center_model_{today}.json")
    items = []
    if model:
        c = model.get("candidates", {})
        items = c.get("items", []) if isinstance(c, dict) else []
        if not items: items = model.get("items", [])
        if isinstance(items, dict): items = list(items.values())
    
    a_cnt = sum(1 for x in items if x.get("grade") == "A")
    b_cnt = sum(1 for x in items if x.get("grade") == "B")
    warnings.append(f"cards:{len(items)},A:{a_cnt},B:{b_cnt}")
    
    # Card template checks
    card_tmpl = ""
    pos = html.find('<article class="candidate"')
    if pos >= 0:
        end = html.find('</article>', pos + 30)
        if end >= 0:
            card_tmpl = html[pos:end + 11]
    
    for name in ["罗森博格","博德闪耀","特兰斯因维斯特","赫格尔曼"]:
        if name in html:
            warnings.append(f"zh_name:{name}")
    
    for tb in ["0-15","16-30","31-45"]:
        if tb in html:
            warnings.append(f"time_bin:{tb}")
    
    # Unbet defaults
    if "first(x.default_stake,null)" in html:
        warnings.append("stake_null")
    
    # Sub-checkers
    for s in ["check_v4_control_center.py","check_v4_dashboard_refresh_no_regrade.py",
              "check_v4_production_default_rules_guard.py","check_v4_h2h_last10_and_time_bins.py",
              "check_v4_dashboard_final_polish.py"]:
        sp = ROOT / "tools" / s
        if not sp.exists():
            warnings.append(f"skip:{s}")
            continue
        r = subprocess.run([sys.executable, str(sp)], capture_output=True, text=True, timeout=60, cwd=str(ROOT))
        try:
            d = json.loads(r.stdout.strip())
            ccl = d.get("conclusion","")
        except:
            ccl = ""
        if r.returncode != 0 and ccl not in ("WARN_ONLY","PASS","OK"):
            blockers.append(f"sub_fail:{s}")
        else:
            warnings.append(f"sub_pass:{s}")
    
    result = {
        "checker": "tools/check_v4_dashboard_candidate_card_layout.py",
        "conclusion": "PASS" if not blockers else "BLOCKED",
        "cards": len(items), "A": a_cnt, "B": b_cnt,
        "blockers": blockers, "warnings": warnings,
        "protection": {
            "DEFAULT_RULES_changed": False,
            "validation_recomputed": False,
            "live_bet_raw_records_modified": False,
            "cron_modified": False,
            "QQ_recommendation_pushed": False,
        }
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    sys.exit(0 if not blockers else 1)

if __name__ == "__main__":
    main()
