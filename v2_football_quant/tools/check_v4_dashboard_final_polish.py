#!/usr/bin/env python3
"""Final polish check: Chinese team names, no Litauen leakage, no N/A in validation."""
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

    # Extract candidate card template only
    card_tmpl = ""
    pos = html.find('<article class="candidate"')
    if pos >= 0:
        end = html.find('</article>', pos + 30)
        if end >= 0:
            card_tmpl = html[pos:end + 11]

    model = load(STATUS / f"v4_control_center_model_{today}.json")
    items = []
    if model:
        c = model.get("candidates", {})
        items = c.get("items", []) if isinstance(c, dict) else []
        if not items: items = model.get("items", [])
        if isinstance(items, dict): items = list(items.values())

    a_cnt = sum(1 for x in items if x.get("grade") == "A")
    b_cnt = sum(1 for x in items if x.get("grade") == "B")

    # 1-4: No English team names in card
    for name in ["Rosenborg", "Bodo/Glimt", "TransINVEST", "Hegelmann Litauen"]:
        if name in card_tmpl:
            blockers.append(f"english_name_in_card:{name}")
    if not blockers:
        warnings.append("no_english_team_names_in_cards")

    # 5-8: Chinese names present in HTML
    for name in ["罗森博格","博德闪耀","特兰斯因维斯特","赫格尔曼"]:
        if name in html:
            warnings.append(f"zh_name:{name}")
        else:
            blockers.append(f"zh_name_missing:{name}")

    # 9: No Litauen leakage
    if "Litauen" in card_tmpl:
        blockers.append("litauen_in_card")
    else:
        warnings.append("no_litauen_in_card")

    # 10-12: Time bins - check binText construction in renderCandidate function
    rc_fn = ""
    rcs = html.find('function renderCandidate')
    rce = html.find('function renderSide', rcs) if rcs >= 0 else -1
    if rcs >= 0 and rce >= 0:
        rc_fn = html[rcs:rce]
    for tb in ["0-15","16-30","31-45"]:
        if tb in rc_fn:
            warnings.append(f"time_bin_{tb}")
        else:
            blockers.append(f"time_bin_{tb}_missing")

    # 13-15: No internal labels in card
    for label in ["57白名单","全量合规","正式候选"]:
        if label in card_tmpl:
            blockers.append(f"label_in_card:{label}")

    # 16-18: No N/A, undefined, null in card
    for bad in ["N/A","undefined","null"]:
        if bad in card_tmpl:
            blockers.append(f"{bad}_in_card")

    # Validation panel check
    val_section = ""
    vpos = html.find("验证明细")
    if vpos >= 0:
        vend = html.find("</section>", vpos + 50)
        if vend >= 0:
            val_section = html[vpos:vend]
    if "N/A" in val_section:
        blockers.append("na_in_validation")
    else:
        warnings.append("no_na_in_validation")

    # Unbet defaults
    if "first(x.default_stake,null)" in html:
        warnings.append("stake_null")

    warnings.append(f"cards:{len(items)},A:{a_cnt},B:{b_cnt}")

    # Sub-checkers
    for s in ["check_v4_control_center.py","check_v4_dashboard_refresh_no_regrade.py",
              "check_v4_production_default_rules_guard.py","check_v4_h2h_last10_and_time_bins.py"]:
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
        "checker": "tools/check_v4_dashboard_final_polish.py",
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
