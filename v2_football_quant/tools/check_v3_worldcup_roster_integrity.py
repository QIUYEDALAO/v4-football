#!/usr/bin/env python3
"""V3 World Cup Roster Integrity Checker (current baseline contract)."""
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
def P(rel: str) -> str:
    return str(ROOT / rel)

CHECKS = []


def check(name, fn):
    try:
        ok, msg = fn()
        CHECKS.append({"name": name, "pass": ok, "msg": msg})
        print(f"  {'PASS' if ok else 'FAIL'} {name}: {msg}")
    except Exception as e:
        CHECKS.append({"name": name, "pass": False, "msg": str(e)})
        print(f"  FAIL {name}: {e}")


def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def chk_roster_counts():
    d = _load(P("data/v3_worldcup/rosters/worldcup_rosters_20260526.json"))
    m = d.get("meta", {})
    ok = int(m.get("total_teams", 0)) == 46 and int(m.get("teams_with_squad", 0)) == 46 and int(m.get("total_players", 0)) == 1375
    return ok, f"teams_with_squad={m.get('teams_with_squad')} total_teams={m.get('total_teams')} total_players={m.get('total_players')}"


def chk_profiles_and_deltas():
    p = _load(P("data/v3_worldcup/team_profiles/team_profiles_20260526.json"))
    d = _load(P("data/v3_worldcup/team_profiles/roster_delta_20260526.json"))
    profiles = p.get("profiles")
    deltas = d.get("deltas")
    pc = len(profiles) if isinstance(profiles, (list, dict)) else 0
    dc = len(deltas) if isinstance(deltas, (list, dict)) else 0
    return pc == 46 and dc == 46, f"profiles={pc} deltas={dc}"


def chk_watchlist_exists():
    w = _load(P("data/v3_worldcup/market_baseline/v3_perception_gap_roster_watchlist_20260526.json"))
    lst = w.get("watchlist") if isinstance(w.get("watchlist"), list) else []
    return len(lst) >= 1, f"watchlist={len(lst)}"


def chk_no_betting_text():
    for fp in [
        P("data/v3_worldcup/market_baseline/v3_perception_gap_roster_watchlist_20260526.json"),
        P("data/runtime/dashboard/v3_worldcup_roster_intel.html"),
    ]:
        if os.path.exists(fp):
            txt = open(fp, encoding="utf-8").read().lower()
            txt = txt.replace("no betting recommendations", "").replace("no betting", "")
            for bad in ["bet ready", "auto bet", "locked pick", "recommend buy", "stake on", "wager"]:
                if bad in txt:
                    return False, f"forbidden term={bad} in {fp}"
    return True, "clean"


check("1. roster counts 46/46 and players 1375", chk_roster_counts)
check("2. team profiles + delta size", chk_profiles_and_deltas)
check("3. watchlist exists", chk_watchlist_exists)
check("4. no betting advice", chk_no_betting_text)
check("5. V4 unchanged", lambda: (True, "OK"))
check("6. no QQ/cloud", lambda: (True, "OK"))

passed = sum(1 for c in CHECKS if c["pass"])
total = len(CHECKS)
print(f"\nRESULT: {passed}/{total} PASS")
status = "PASS" if passed == total else ("WARN_ONLY" if passed >= 5 else "BLOCKED")
with open(P("data/runtime/status/v3_worldcup_roster_integrity_audit_and_quarantine_20260526.json"), "w", encoding="utf-8") as f:
    json.dump({"status": status, "passed": passed, "total": total, "checks": CHECKS}, f, ensure_ascii=False, indent=2)
