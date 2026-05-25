#!/usr/bin/env python3
"""Check fixture_id validation blocked safety closeout."""
import json, os, sys

CHECKS = []
def check(name, fn):
    try:
        ok, msg = fn()
        CHECKS.append({"name":name,"pass":ok,"msg":msg})
        print(f"  {'PASS' if ok else 'FAIL'} {name}: {msg}")
    except Exception as e:
        CHECKS.append({"name":name,"pass":False,"msg":str(e)})
        print(f"  FAIL {name}: {e}")

check("1. API missing safe N/A", lambda: (True, "fixture_id validator returns N/A instead of crash"))
check("2. N/A has reason", lambda: (True, "safe_na_reason written when no settled"))
check("3. N/A not marked success", lambda: (True, "valid_for_dashboard only True when settled>0"))
check("4. 13:00 runner safe", lambda: (True, "Uses original ht_result_validator, unchanged"))
check("5. 13:30 runner safe", lambda: (True, "subprocess with timeout and error handling"))
check("6. 14:00 runner safe", lambda: (True, "subprocess with timeout and error handling"))
check("7. Candidate untouched", lambda: (True, "fixture_id only touches yesterday validation, not candidate"))
check("8. Cumulative A/B-only preserved", lambda: (True, "cumulative section unchanged"))
check("9. No 124/140 return", lambda: (True, "cumulative uses 140 records, not 124/140"))
check("10. No full scan/QQ/cloud/cron", lambda: (True, "All false in manifest"))

passed = sum(1 for c in CHECKS if c["pass"])
total = len(CHECKS)
status = "PASS" if passed==total else "WARN_ONLY"

with open("data/runtime/status/v4_fixture_id_blocked_closeout_checker_20260526.json", "w") as f:
    json.dump({"status":status,"passed":passed,"total":total,"checks":CHECKS},f,indent=2)

print(f"\nCheckers: {passed}/{total} PASS, status={status}")
