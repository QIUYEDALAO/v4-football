#!/usr/bin/env python3
"""Intel Ops Refresh Checker — dynamic date support"""
import json, subprocess, sys
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]
REFRESH = MODULE / "tools" / "intel_ops_refresh.py"

def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default="2026-05-20")
    args = ap.parse_args()

    R = {"check_status": "PASS", "refresh_ran": False, "json_parsed": False,
         "v2_current_ok": False, "v2_historical_ok": False, "builder_ok": False,
         "intel_checker_pass": False, "qq_preview_exists": False,
         "blockers": [], "warnings": []}
    block = False

    if not REFRESH.is_file():
        R["blockers"].append("refresh missing"); _finish(R, True)

    r = subprocess.run(["python3", str(REFRESH), "--date", args.date,
                        "--history-days", "4", "--v4-attribution-days", "3",
                        "--no-push", "--no-state-write", "--no-verified-write",
                        "--no-proof", "--no-d13", "--no-cron"],
                       capture_output=True, text=True, timeout=180, cwd=str(MODULE))
    R["refresh_rc"] = r.returncode; R["refresh_ran"] = True

    try:
        d = json.loads(r.stdout.strip().split("\n")[0])
        R["json_parsed"] = True
        R["refresh_status"] = d.get("status")
        R["dashboard_version"] = d.get("dashboard_version", "?")

        v2c = d.get("v2_current", {})
        R["v2_current_ok"] = bool(v2c) and "error" not in v2c
        v2h = d.get("v2_historical", {})
        R["v2_historical_ok"] = bool(v2h) and "error" not in v2h and v2h.get("per_date")
        if not R["v2_historical_ok"]: R["blockers"].append("v2_historical missing"); block = True
        R["builder_ok"] = d.get("builder", {}).get("status") == "OK"
        R["intel_checker_pass"] = d.get("intel_checker_status") == "PASS"
        if not R["intel_checker_pass"]: R["blockers"].append("intel checker not PASS"); block = True

        # QQ preview
        pf = d.get("qq_preview_file", "")
        R["qq_preview_exists"] = (MODULE / pf).is_file() if pf else False
        R["qq_preview_only"] = not d.get("qq_sent", True)
        if d.get("qq_sent", False): R["blockers"].append("qq_sent=true!"); block = True
        if d.get("route_marker_written", False): R["blockers"].append("route_marker!"); block = True
        if d.get("sent_marker_written", False): R["blockers"].append("sent_marker!"); block = True

        # Guards
        for f in ["qq_sent", "state_written", "verified_written", "proof_executed",
                  "d13_execute", "phase_e", "cron_modified", "formal_daily_pool_executed",
                  "supervisor_executed", "live_worker_executed"]:
            if d.get(f, True): R["blockers"].append(f"{f}=true"); block = True

        # Dashboard files
        dk = args.date.replace("-", "")
        idir = MODULE / "reports" / "intel_desk"
        for f in [f"INTEL_DASHBOARD_{dk}.md", f"INTEL_DASHBOARD_{dk}.json", "INTEL_DASHBOARD_LATEST.md"]:
            if not (idir / f).is_file(): R["blockers"].append(f"Missing: {f}"); block = True

        R["per_date"] = v2h.get("per_date", {})
        R["attribution_dates"] = list(d.get("v4_attribution", {}).keys())
        R["history_days"] = d.get("history_days")
        R["v4_attribution_days"] = d.get("v4_attribution_days")

    except Exception as e: R["blockers"].append(f"Parse: {e}"); block = True

    _finish(R, block)

def _finish(R, block):
    if block: R["check_status"] = "BLOCKER"
    elif R["warnings"]: R["check_status"] = "WARN"
    print("="*50); print("INTEL OPS REFRESH CHECKER"); print("="*50)
    print(f"Status: {R['check_status']}  |  rc: {R.get('refresh_rc','?')}  |  refresh: {R.get('refresh_status','?')}")
    print(f'v: {R.get("dashboard_version","?")}  |  history_days: {R.get("history_days","?")}  |  v4_days: {R.get("v4_attribution_days","?")}')
    for k in ["v2_current_ok","v2_historical_ok","builder_ok","intel_checker_pass","qq_preview_exists"]:
        print(f"  {k}: {R[k]}")
    if R.get("per_date"): print(f"  historical: {R['per_date']}")
    if R.get("attribution_dates"): print(f"  attribution on: {list(R['attribution_dates'])}")
    if R["blockers"]:
        print(f"\nBLOCKERS ({len(R['blockers'])}):");
        for b in R["blockers"]: print(f"  ! {b}")
        sys.exit(1)
    if R["warnings"]:
        print(f"\nWARNINGS ({len(R['warnings'])}):")
        for w in R["warnings"]: print(f"  ~ {w}")
    md = MODULE/"data"/"runtime"/"status"; md.mkdir(parents=True,exist_ok=True)
    (md/"intel_ops_refresh_check.json").write_text(json.dumps(R,indent=2,ensure_ascii=False))
    sys.exit(0)

if __name__=="__main__": main()
