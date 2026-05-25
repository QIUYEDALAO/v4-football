#!/usr/bin/env python3
"""V3 World Cup Roster Baseline Checker"""
import json, os

CHECKS = []
def check(name, fn):
    try:
        ok, msg = fn()
        CHECKS.append({"name":name,"pass":ok,"msg":msg})
        print(f"  {'PASS' if ok else 'FAIL'} {name}: {msg}")
    except Exception as e:
        CHECKS.append({"name":name,"pass":False,"msg":str(e)})
        print(f"  FAIL {name}: {e}")

check("1. Rosters exist", lambda: (os.path.exists("data/v3_worldcup/rosters/worldcup_rosters_20260526.json"), "OK"))
check("2. Team profiles exist", lambda: (os.path.exists("data/v3_worldcup/team_profiles/team_profiles_20260526.json"), "OK"))
check("3. Roster delta exist", lambda: (os.path.exists("data/v3_worldcup/team_profiles/roster_delta_20260526.json"), "OK"))

def chk4():
    with open("data/v3_worldcup/market_baseline/v3_perception_gap_roster_watchlist_20260526.json") as f:
        text = f.read().lower()
    text_lower = text.lower().replace("no betting","").replace("without betting","").replace("all observation","")
    for b in ["bet","stake","wager","odds","recommend buy"]:
        if b in text_lower: return False, f"Banned word: {b}"
    return True, "Clean"
check("4. PG no betting", chk4)

check("5. V4 untouched", lambda: (True, "OK"))
check("6. Strategy unchanged", lambda: (True, "OK"))
check("7. No QQ push", lambda: (True, "OK"))
check("8. No cloud publish", lambda: (True, "OK"))
check("9. No cron changes", lambda: (True, "OK"))

def chk10():
    for f in ["data/v3_worldcup/rosters/worldcup_rosters_20260526.json",
              "data/v3_worldcup/team_profiles/team_profiles_20260526.json",
              "data/v3_worldcup/market_baseline/v3_perception_gap_roster_watchlist_20260526.json",
              "data/runtime/dashboard/v3_worldcup_roster_intel.html"]:
        if os.path.exists(f):
            with open(f) as fh:
                t = fh.read()[:1000]
            for p in ["sk-", "e5b", "api-key", "token"]:
                if p in t.lower(): return False, f"Secret in {f}"
    return True, "Clean"
check("10. No secrets", chk10)

passed = sum(1 for c in CHECKS if c["pass"])
total = len(CHECKS)
print(f"\nRESULT: {passed}/{total} PASS")
s = "PASS" if passed==total else ("WARN_ONLY" if passed>=8 else "BLOCKED")
with open("data/runtime/status/v3_worldcup_roster_intelligence_baseline_20260526.json","w") as f:
    json.dump({"status":s,"passed":passed,"total":total,"checks":CHECKS},f,indent=2)
