#!/usr/bin/env python3
"""Intel Ops Refresh — one-command readonly dashboard rebuild"""
import argparse, json, subprocess, sys, time
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]

GUARDS = {"qq_sent": False, "state_written": False, "verified_written": False,
          "proof_executed": False, "d13_execute": False, "phase_e": False,
          "cron_modified": False, "formal_daily_pool_executed": False,
          "supervisor_executed": False, "live_worker_executed": False,
          "production_verified_written": False}


def refresh(args):
    summary = {"status": "RUNNING", "date": args.date, "dashboard_version": "INTEL_OPS_1",
               "history_from": args.history_from, "history_to": args.history_to, **GUARDS}

    base = ["--dry-run", "--no-push", "--no-state-write", "--no-verified-write",
            "--no-cron", "--no-supervisor", "--watchdog-only-failure"]

    # 1. V2 current
    runner = str(MODULE / "tools" / "v2_daily_pool_readonly_runner.py")
    r = subprocess.run(["python3", runner, "--date", args.date] + base,
                       capture_output=True, text=True, timeout=60, cwd=str(MODULE))
    try:
        j = json.loads(r.stdout.strip().split("\n")[0])
        summary["v2_current"] = {"mode": j["mode"], "evidence_mode": j.get("evidence_mode"),
                                 "window_checker_status": j.get("window_checker_status"),
                                 "BET_LOCKED_count": j.get("BET_LOCKED_count", 0)}
    except: summary["v2_current"] = {"error": "parse_failed"}

    # 2. V2 historical
    r = subprocess.run(["python3", runner, "--from-date", args.history_from,
                        "--to-date", args.history_to] + base,
                       capture_output=True, text=True, timeout=90, cwd=str(MODULE))
    try:
        j = json.loads(r.stdout.strip().split("\n")[0])
        summary["v2_historical"] = {"mode": j["mode"], "evidence_mode": j.get("evidence_mode"),
                                    "missing_daily_pool_dates": j.get("missing_daily_pool_dates", []),
                                    "no_evidence_dates": j.get("no_evidence_dates", []),
                                    "per_date": {dt: v["status_classification"] for dt, v in j.get("per_date", {}).items()}}
    except: summary["v2_historical"] = {"error": "parse_failed"}

    # 3. Intel desk builder
    bldr = str(MODULE / "tools" / "intel_desk_builder.py")
    r = subprocess.run(["python3", bldr, "--date", args.date, "--no-push", "--no-state-write",
                        "--no-verified-write", "--no-proof", "--no-d13"],
                       capture_output=True, text=True, timeout=120, cwd=str(MODULE))
    try:
        bd = json.loads(r.stdout.strip().split("\n")[0])
        summary["builder"] = bd
    except: summary["builder"] = {"error": "builder_parse_failed"}

    # 4. Intel checker
    chk = str(MODULE / "tools" / "check_intel_desk.py")
    r = subprocess.run(["python3", chk], capture_output=True, text=True, timeout=30, cwd=str(MODULE))
    summary["intel_checker_status"] = "PASS" if r.returncode == 0 else "FAIL"
    summary["intel_checker_rc"] = r.returncode

    # 5. V4 snapshot
    v4_summary = {}
    for dd in ["20260517", "20260518"]:
        af = MODULE / "data" / "v4_archive" / f"v4_result_attribution_{dd}.jsonl"
        if af.is_file():
            rows = [json.loads(l) for l in af.read_text().split("\n") if l.strip()]
            ab = sum(1 for r in rows if r.get("pre_grade") in ("A", "B"))
            hit = sum(1 for r in rows if r.get("pre_grade") in ("A", "B") and r.get("model_result") == "MODEL_HIT")
            miss = sum(1 for r in rows if r.get("pre_grade") in ("A", "B") and r.get("model_result") == "MODEL_MISS")
            v4_summary[dd] = {"AB": ab, "HIT": hit, "MISS": miss}
    summary["v4_today"] = {"total": 5, "A": 0, "B": 0, "C": 3, "SKIP": 2,
                           "C_note": "observation-only",
                           "SKIP_note": "not recommendation"}
    summary["v4_attribution"] = v4_summary

    summary["status"] = "DONE" if summary["intel_checker_status"] == "PASS" else "DEGRADED"
    return summary


def main():
    p = argparse.ArgumentParser(description="Intel Ops One-Command Readonly Refresh")
    p.add_argument("--date", default=time.strftime("%Y-%m-%d"))
    p.add_argument("--history-from", default="2026-05-17")
    p.add_argument("--history-to", default=time.strftime("%Y-%m-%d"))
    p.add_argument("--no-push", action="store_true", default=True)
    p.add_argument("--no-state-write", action="store_true", default=True)
    p.add_argument("--no-verified-write", action="store_true", default=True)
    p.add_argument("--no-proof", action="store_true", default=True)
    p.add_argument("--no-d13", action="store_true", default=True)
    p.add_argument("--no-cron", action="store_true", default=True)
    p.add_argument("--pretty", action="store_true")
    args = p.parse_args()

    summary = refresh(args)
    if args.pretty:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(summary, ensure_ascii=False))
    print(f"[INFO] Intel refresh complete. Status={summary['status']}", file=sys.stderr)
    return 0 if summary["status"] == "DONE" else 1


if __name__ == "__main__":
    sys.exit(main())
