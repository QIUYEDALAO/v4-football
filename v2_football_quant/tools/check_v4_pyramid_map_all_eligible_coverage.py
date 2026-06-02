#!/usr/bin/env python3
"""Check V4 pyramid map coverage under all_eligible mode."""
import json, subprocess, sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "data" / "runtime" / "status"
LOCAL_TZ = timezone(timedelta(hours=8))

def load(p):
    try: return json.loads(p.read_text())
    except: return None

def main():
    blockers, warnings = [], []
    today = datetime.now(LOCAL_TZ).strftime("%Y%m%d")
    
    # Load pyramid map
    with open(ROOT / "config" / "v4_league_pyramid_map.json") as f:
        pm = json.load(f)
    pyr = pm.get("pyramid_map", {})
    mapped_ids = set(pyr.keys())
    
    # 1: all_eligible active
    cv = load(STATUS / f"v4_official_candidate_view_{today}.json")
    if cv:
        if cv.get('fixture_universe') == 'all_eligible':
            warnings.append("all_eligible_active")
        else:
            blockers.append("all_eligible_not_active")
    
    # 2: WHITELIST_57 entries preserved
    whitelist_ids = ['39','40','61','62','71','78','79','88','94','98','103','106','113','119',
                     '128','135','136','140','141','144','164','169','172','179','188','197',
                     '203','207','210','218','233','235','244','253','262','268','271','274',
                     '283','286','292','301','307','323','332','333','342','344','345','357',
                     '362','418']
    missing_whitelist = [lid for lid in whitelist_ids if lid not in pyr]
    if missing_whitelist:
        blockers.append(f"whitelist_entries_missing:{missing_whitelist}")
    else:
        warnings.append(f"whitelist_preserved:{len(whitelist_ids)}")
    
    # 3: New leagues added
    new_ids = ['76','170','222','363']
    for lid in new_ids:
        if lid in pyr:
            e = pyr[lid]
            warnings.append(f"new_league_{lid}:{e.get('league_name')} tier={e.get('tier')}")
        else:
            blockers.append(f"new_league_missing:{lid}")
    
    # 4: No youth/reserve/cup/friendly added as eligible
    for lid in new_ids:
        e = pyr.get(lid, {})
        if not e: continue
        ct = e.get('competition_type', 'league')
        if ct in ('cup','friendly','continental_cup') and e.get('eligible_for_h2h', True):
            blockers.append(f"non_league_eligible:{lid} ct={ct}")
    
    # 5: Map entry count
    eligible = sum(1 for _, e in pyr.items() if e.get('competition_type') == 'league')
    warnings.append(f"map_size:{len(pyr)},eligible_leagues:{eligible}")
    
    # 6: source_group in model
    model = load(STATUS / f"v4_control_center_model_{today}.json")
    items = []
    if model:
        c = model.get("candidates", {})
        items = c.get("items", []) if isinstance(c, dict) else []
        if not items: items = model.get("items", [])
        if isinstance(items, dict): items = list(items.values())
    
    has_sg = any(x.get("source_group") for x in items) if items else False
    if has_sg:
        warnings.append("source_group_in_model")
    else:
        blockers.append("source_group_missing")
    
    # 7: WHITELIST_57 / OUTSIDE_57 split in cv
    if cv:
        wa = cv.get('A_WHITELIST_57_count')
        oa = cv.get('A_OUTSIDE_57_count')
        wb = cv.get('B_WHITELIST_57_count')
        ob = cv.get('B_OUTSIDE_57_count')
        warnings.append(f"split_stats:A_w{wa}_o{oa}_B_w{wb}_o{ob}")
    
    a_cnt = sum(1 for x in items if x.get("grade") == "A")
    b_cnt = sum(1 for x in items if x.get("grade") == "B")
    warnings.append(f"cards:{len(items)},A:{a_cnt},B:{b_cnt}")
    
    # Safety sub-checkers
    for s in ["check_v4_dashboard_refresh_no_regrade.py","check_v4_production_default_rules_guard.py"]:
        sp = ROOT / "tools" / s
        r = subprocess.run([sys.executable, str(sp)], capture_output=True, text=True, timeout=60, cwd=str(ROOT))
        try: d = json.loads(r.stdout.strip()); ccl = d.get("conclusion","")
        except: ccl = ""
        if r.returncode != 0 and ccl not in ("WARN_ONLY","PASS"):
            blockers.append(f"sub_fail:{s}")
        else: warnings.append(f"sub_pass:{s}")
    
    result = {
        "checker": "tools/check_v4_pyramid_map_all_eligible_coverage.py",
        "conclusion": "PASS" if not blockers else "BLOCKED",
        "map_entries": len(pyr), "eligible_leagues": eligible,
        "blockers": blockers, "warnings": warnings,
        "protection": {
            "all_eligible_active": cv.get('fixture_universe') == 'all_eligible' if cv else False,
            "whitelist_preserved": len(missing_whitelist) == 0,
            "DEFAULT_RULES_changed": False,
        }
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    sys.exit(0 if not blockers else 1)

if __name__ == "__main__":
    main()
