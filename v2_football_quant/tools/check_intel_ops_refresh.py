#!/usr/bin/env python3
"""Intel Ops Refresh Checker — validates one-command refresh output"""
import json, subprocess, sys
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]
REFRESH = MODULE / "tools" / "intel_ops_refresh.py"

def main():
    R = {"check_status": "PASS", "refresh_ran": False, "json_parsed": False,
         "v2_current_ok": False, "v2_historical_ok": False, "builder_ok": False,
         "intel_checker_pass": False, "blockers": [], "warnings": []}
    block = False

    if not REFRESH.is_file():
        R["blockers"].append("intel_ops_refresh.py missing"); _finish(R, True)

    r = subprocess.run(["python3", str(REFRESH), "--date", "2026-05-20",
                        "--history-from", "2026-05-17", "--history-to", "2026-05-20",
                        "--no-push", "--no-state-write", "--no-verified-write",
                        "--no-proof", "--no-d13", "--no-cron"],
                       capture_output=True, text=True, timeout=180, cwd=str(MODULE))
    R["refresh_rc"] = r.returncode

    try:
        d = json.loads(r.stdout.strip().split("\n")[0])
        R["json_parsed"] = True; R["refresh_ran"] = True
        R["refresh_status"] = d.get("status")

        # V2 checks
        v2c = d.get("v2_current", {})
        R["v2_current_ok"] = bool(v2c) and "error" not in v2c
        if not R["v2_current_ok"]: R["warnings"].append("v2_current parse issue")

        v2h = d.get("v2_historical", {})
        R["v2_historical_ok"] = bool(v2h) and "error" not in v2h and v2h.get("per_date")
        if not R["v2_historical_ok"]: R["blockers"].append("v2_historical missing/failed"); block = True

        R["builder_ok"] = d.get("builder", {}).get("status") == "OK"
        R["intel_checker_pass"] = d.get("intel_checker_status") == "PASS"
        if not R["intel_checker_pass"]: R["blockers"].append("intel checker not PASS"); block = True

        # Guard checks
        for f in ["qq_sent", "state_written", "verified_written", "proof_executed",
                  "d13_execute", "phase_e", "cron_modified", "formal_daily_pool_executed",
                  "supervisor_executed", "live_worker_executed"]:
            if d.get(f, True): R["blockers"].append(f"Guard {f}=true"); block = True

        # Dashboard files
        idir = MODULE / "reports" / "intel_desk"
        for f in ["INTEL_DASHBOARD_20260520.md", "INTEL_DASHBOARD_20260520.json", "INTEL_DASHBOARD_LATEST.md"]:
            if not (idir / f).is_file(): R["blockers"].append(f"Dashboard file missing: {f}"); block = True

        R["per_date"] = v2h.get("per_date", {})

    except Exception as e: R["blockers"].append(f"Refresh parse: {e}"); block = True

    _finish(R, block)


def _finish(R, block):
    if block: R["check_status"] = "BLOCKER"
    elif R["warnings"]: R["check_status"] = "WARN"
    print("=" * 50)
    print("INTEL OPS REFRESH CHECKER")
    print("=" * 50)
    print(f"Status: {R['check_status']}  |  refresh_rc: {R.get('refresh_rc','?')}  |  refresh_status: {R.get('refresh_status','?')}")
    for k in ["v2_current_ok", "v2_historical_ok", "builder_ok", "intel_checker_pass", "json_parsed"]:
        print(f"  {k}: {R[k]}")
    if R.get("per_date"):
        print(f"  historical: {R['per_date']}")
    if R["blockers"]:
        print(f"\nBLOCKERS ({len(R['blockers'])}):")
        for b in R["blockers"]: print(f"  ! {b}")
        sys.exit(1)
    if R["warnings"]:
        print(f"\nWARNINGS ({len(R['warnings'])}):")
        for w in R["warnings"]: print(f"  ~ {w}")
    md = MODULE / "data" / "runtime" / "status"
    md.mkdir(parents=True, exist_ok=True)
    (md / "intel_ops_refresh_check.json").write_text(json.dumps(R, indent=2, ensure_ascii=False))
    print(f"\n{md}/intel_ops_refresh_check.json (not committed)")
    sys.exit(0)


if __name__ == "__main__":
    main()
