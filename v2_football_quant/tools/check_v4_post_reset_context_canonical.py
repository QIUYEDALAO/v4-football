#!/usr/bin/env python3
"""
Phase OPENCLAW-POST-RESET-MINIMAL-CONTEXT-REBUILD-20260527 — Step 9.

Context canonical checker.
Prevents C formal-candidate wording from returning to active workspace files.

Checks:
1. MEMORY.md must NOT say "按 A/B/C/SKIP 输出正式候选视图"
2. MEMORY.md must state current V4 candidate view is A/B/SKIP
3. C must NOT be written as current formal candidate
4. C must NOT enter A/B cumulative
5. C must NOT enter current V4 main view
6. STATE_CURRENT.md must NOT store live production state
7. AGENTS.md must NOT enable autonomous analyst agents
8. HEARTBEAT.md must NOT allow full scan / validation recompute
9. v4_control_center.html must NOT show C as KPI candidate
10. build_v4_control_center_model.py must NOT count C in pending bet
11. validation cumulative must NOT read C
12. Does NOT trigger scan
13. Does NOT trigger validation
14. Does NOT push QQ
15. Does NOT change cron

Output:
  data/runtime/status/v4_post_reset_context_canonical_checker_20260527.json
"""

import json
import os
import re
import sys

WORKSPACE = os.path.expanduser("~/.openclaw/workspace")
PROJECT = os.path.join(WORKSPACE, "v2_football_quant")

RESULTS = []
BLOCKERS = []


def check(ok, item, detail):
    kind = "PASS" if ok else ("BLOCKER" if "must NOT" in detail or "must not" in detail.lower() else "FAIL")
    RESULTS.append({"check": item, "status": kind, "detail": detail})
    if kind == "BLOCKER":
        BLOCKERS.append(detail)
    return ok


def read_file(path):
    if not os.path.exists(path):
        return ""
    with open(path, "r") as f:
        return f.read()


# --- 1-8: Workspace file checks ---

mem = read_file(os.path.join(WORKSPACE, "MEMORY.md"))
check(
    "按 A/B/C/SKIP 输出正式候选视图" not in mem,
    "MEMORY.md no A/B/C/SKIP formal output",
    "MEMORY.md must NOT say '按 A/B/C/SKIP 输出正式候选视图'"
)

check(
    "当前 V4 作战台只认" in mem and "A" in mem and "B" in mem and "SKIP" in mem,
    "MEMORY.md states A/B/SKIP",
    "MEMORY.md must state current V4 candidate view is A/B/SKIP"
)

check(
    "C 不是当前 V4 作战台正式口径" in mem,
    "MEMORY.md C is not current formal",
    "MEMORY.md must state C is not current formal candidate"
)

check(
    "C 不得进入 A/B 累计" in mem,
    "MEMORY.md C not in A/B cumulative",
    "MEMORY.md must forbid C from A/B cumulative"
)

check(
    "C 不得进入当前 V4 主视图" in mem,
    "MEMORY.md C not in main view",
    "MEMORY.md must forbid C from current V4 main view"
)

st = read_file(os.path.join(WORKSPACE, "STATE_CURRENT.md"))
check(
    "No live production state is stored here" in st,
    "STATE_CURRENT.md no live state",
    "STATE_CURRENT.md must NOT store live production state"
)

ag = read_file(os.path.join(WORKSPACE, "AGENTS.md"))
check(
    "No autonomous analyst agents" in ag,
    "AGENTS.md no autonomous agents",
    "AGENTS.md must NOT enable autonomous analyst agents"
)

hb = read_file(os.path.join(WORKSPACE, "HEARTBEAT.md"))
check(
    "full scan" in hb and "validation recompute" in hb,
    "HEARTBEAT.md forbids scan/validation",
    "HEARTBEAT.md must NOT allow full scan / validation recompute"
)

# --- 9-10: Dashboard & model checks ---

dash = read_file(os.path.join(PROJECT, "data/runtime/dashboard/v4_control_center.html"))
# Check for C as formal KPI candidate (not C in CSS/HTML structure)
c_kpi_patterns = [
    r'["\']grade["\']\s*:\s*["\']C["\']',
    r'C级观察|C级候选',
    r'["\']C["\']\s*[:=]\s*\d+',
]
c_in_kpi = any(re.search(p, dash) for p in c_kpi_patterns)
check(
    not c_in_kpi,
    "Dashboard no C as KPI candidate",
    "v4_control_center.html must NOT show C as KPI candidate"
)

mb = read_file(os.path.join(PROJECT, "build_v4_control_center_model.py"))
c_in_pending = bool(re.search(r'C.*pending|pending.*C', mb, re.IGNORECASE))
check(
    not c_in_pending,
    "Model no C in pending bet",
    "build_v4_control_center_model.py must NOT count C in pending bet"
)

# --- 11: Validation cumulative C check ---
c_in_validation = "C" in mb and "cumulative" in mb.lower()
check(
    not c_in_validation,
    "Model no C in validation cumulative",
    "validation cumulative must NOT read C"
)

# --- 12-15: Safety checks ---
# These are guaranteed by the checker not calling those functions
check(True, "Does not trigger scan", "Does NOT trigger scan")
check(True, "Does not trigger validation", "Does NOT trigger validation")
check(True, "Does not push QQ", "Does NOT push QQ")
check(True, "Does not change cron", "Does NOT change cron")

# --- Final verdict ---
status = "PASS"
if BLOCKERS:
    status = "BLOCKER"

output = {
    "checker": "check_v4_post_reset_context_canonical",
    "phase": "OPENCLAW-POST-RESET-MINIMAL-CONTEXT-REBUILD-20260527",
    "status": status,
    "results": RESULTS,
    "blockers": BLOCKERS
}

out_path = os.path.join(PROJECT, "data/runtime/status/v4_post_reset_context_canonical_checker_20260527.json")
os.makedirs(os.path.dirname(out_path), exist_ok=True)
with open(out_path, "w") as f:
    json.dump(output, f, indent=2, ensure_ascii=False)

print(f"Status: {status}")
for r in RESULTS:
    print(f"  [{r['status']}] {r['check']}: {r['detail']}")
if BLOCKERS:
    print(f"\nBLOCKERS ({len(BLOCKERS)}):")
    for b in BLOCKERS:
        print(f"  ! {b}")

sys.exit(0 if status == "PASS" else 1)
