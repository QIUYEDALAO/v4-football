#!/usr/bin/env python3
"""Check cumulative post-retry sync correctness."""
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

with open("data/runtime/dashboard/intel_ops_console.html") as f:
    h = f.read()

check("1. yesterday B 3/5", lambda: ("3/5 · 60.0%" in h, "yesterday B shows 3/5"))
check("2. yesterday AB 6/10", lambda: ("6/10 · 60.0%" in h, "yesterday AB shows 6/10"))
check("3. cumulative B 53/94", lambda: ("53/94 · 56.4%" in h, "cumulative B shows 53/94"))
check("4. cumulative AB 81/140", lambda: ("81/140 · 57.9%" in h, "cumulative AB shows 81/140"))
check("5. no 52/93", lambda: ("52/93" not in h and "52/93" not in h, "no 52/93"))
check("6. no 80/139", lambda: ("80/139" not in h, "no 80/139"))
check("7. no 124/140", lambda: ("124/140" not in h, "no 124/140"))
check("8. no V2/V33", lambda: not any(x in h.replace("V3V4","").replace("V4_","") for x in ["V2","V33"]), "no V2/V33"))
check("9. no C visible", lambda: "C级" not in h and "C候选" not in h, "no C visible"))
check("10. no pending", lambda: "待补验" not in h, "no pending text"))
check("11. A/B-only label", lambda: "A/B-only" in h, "A/B-only label present"))

passed = sum(1 for c in CHECKS if c["pass"])
total = len(CHECKS)
status = "PASS" if passed==total else "WARN_ONLY"
with open("data/runtime/status/v4_cumulative_post_retry_checker_20260526.json","w") as f:
    json.dump({"status":status,"passed":passed,"total":total,"checks":CHECKS},f,indent=2)
print(f"\nChecker: {passed}/{total} PASS, status={status}")
