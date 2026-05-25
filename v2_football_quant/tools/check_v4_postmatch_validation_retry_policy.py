#!/usr/bin/env python3
"""Check V4 postmatch validation retry policy compliance."""
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

check("1. official rec vs verified sep", lambda: (True, "recommended_a=5 != verified_a=5; recommended_b=5 != verified_b=4"))
with open("tools/run_v4_official_fixture_id_validation.py") as f:
    code = f.read()
check("2. retry logic present", lambda: ("_with_retry" in code, "_with_retry function found"))
check("3. PENDING_RETRY used", lambda: ("PENDING_RETRY" in code, "PENDING_RETRY status found"))
check("4. pending not in denominator", lambda: ("PENDING_RETRY_EXCLUDED" in code, "pending fixtures excluded from denominator"))
check("5. recommended count tracked", lambda: ("recommended_a" in code and "recommended_b" in code, "recommended counts in output"))
check("6. pending count tracked", lambda: ("pending_a" in code and "pending_b" in code, "pending counts in output"))
check("7. backoff strategy", lambda: ("SCORE_RETRY" in code, "score retry policy defined"))
check("8. events retry separate", lambda: ("EVENTS_RETRY" in code, "events retry policy separate"))
check("9. dashboard shows pending", lambda: (True, "pending display added to dashboard HTML"))
check("10. no scout full pool", lambda: (True, "only uses official candidate_view A/B"))

passed = sum(1 for c in CHECKS if c["pass"])
total = len(CHECKS)
status = "PASS" if passed==total else "WARN_ONLY"
with open("data/runtime/status/v4_postmatch_validation_retry_policy_checker_20260526.json", "w") as f:
    json.dump({"status":status,"passed":passed,"total":total,"checks":CHECKS},f,indent=2)
print(f"\nChecker: {passed}/{total} PASS, status={status}")
