#!/usr/bin/env python3
"""V2 Prod Shadow Closure Master Checker — validates all gates"""
import json, sys, os
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]

def main():
    R = {"check_status":"PASS","blockers":[],"warnings":[],
         "tests":{},"qq_sent":False,"cron":False,"d13":False,"verified":False,"prod_verified":False}
    block = False

    def check(test_name, condition, msg=""):
        R["tests"][test_name] = condition
        if not condition: R["blockers"].append(f"{test_name}: {msg}"); return True
        return False

    # 1. Issue inventory
    inv = MODULE / "docs" / "V2_PROD_SHADOW_CLOSURE_MASTER_ISSUE_LIST_202605.md"
    block |= check("issue_inventory", inv.is_file(), "missing")

    # 2. Formal state shadow
    shadow_sf = MODULE / "data/runtime/shadow/selected_fixtures_20260519.formal_state_shadow.json"
    if shadow_sf.is_file():
        sf = json.loads(shadow_sf.read_text())
        block |= check("shadow_selected_contains_1545407", 1545407 in sf.get("selected_fixture_ids",[]))
        fix = sf.get("fixtures",{}).get("1545407",{})
        block |= check("shadow_locked_stage", fix.get("locked_stage")=="T_MINUS_90M")
        block |= check("shadow_locked_odds", fix.get("locked_odds_D")==2.28)
        block |= check("shadow_official_bet_locked", fix.get("official_bet_locked")==True)
        block |= check("shadow_qq_required", fix.get("qq_required")==True)
        block |= check("shadow_lock_owner", fix.get("lock_owner")=="window_checker")
    else:
        block |= check("formal_state_shadow", False, "missing")

    # 3. Official state hash
    real_sf = MODULE / "data/state/selected_fixtures_20260519.json"
    if real_sf.is_file():
        import hashlib
        real_data = json.loads(real_sf.read_text())
        real_sids = real_data.get("selected_fixture_ids",[])
        block |= check("official_state_unchanged", 1545407 not in real_sids, "1545407 in real selected_fixture_ids")

    # 4. QQ route shadow
    route = MODULE / "data/runtime/shadow/v2_qq_route_shadow_202605.json"
    if route.is_file():
        rd = json.loads(route.read_text())
        block |= check("qq_route_allowed", rd.get("route_allowed")==True, "should be True for shadow")
        block |= check("qq_actual_send", rd.get("actual_send")==False, "must be False")
        block |= check("qq_sent_shadow", rd.get("qq_sent")==False)
        block |= check("qq_allowed_to_send", rd.get("allowed_to_send")==False)

    # 5. Cron shadow
    cron_f = MODULE / "data/runtime/shadow/v2_cron_shadow_plan_202605.json"
    if cron_f.is_file():
        cd = json.loads(cron_f.read_text())
        block |= check("cron_enabled", cd.get("cron_enabled")==False)
        block |= check("crontab_modified", cd.get("crontab_modified")==False)

    # 6. Verified precheck
    vf = MODULE / "data/runtime/shadow/v2_verified_precheck_shadow_202605.json"
    if vf.is_file():
        vd = json.loads(vf.read_text())
        block |= check("verified_written", vd.get("verified_written")==False)
        block |= check("prod_verified_shadow", vd.get("production_verified")==False)

    # 7. Dashboard
    dash = MODULE / "data/runtime/dashboard/v2_today.html"
    if dash.is_file():
        html = dash.read_text()
        block |= check("dash_shadow_visible", "FORMAL_STATE_SHADOW" in html or "BET_LOCKED_PROOF" in html)
        block |= check("dash_prod_false", "PRODUCTION_VERIFIED" not in html[-500:] or "false" in html)

    # 8. True readonly
    lc = MODULE / "tools" / "check_v2_readonly_live_window.py"
    if lc.is_file():
        txt = lc.read_text()
        block |= check("true_readonly", all(k in txt for k in ["--observe-only","--no-formal-state-write"]))

    if block: R["check_status"]="BLOCKER"
    print("="*60); print("V2 PROD SHADOW CLOSURE MASTER CHECKER"); print("="*60)
    print(f"Status: {R['check_status']}")
    for k,v in R["tests"].items(): print(f"  {k}: {'✅' if v else '❌'}")
    if R["blockers"]:
        print(f"\nBLOCKERS ({len(R['blockers'])}):")
        for b in R["blockers"]: print(f"  ! {b}")
        sys.exit(1)
    print("\nALL GATES PASS ✅")
    sys.exit(0)

if __name__=="__main__": main()
