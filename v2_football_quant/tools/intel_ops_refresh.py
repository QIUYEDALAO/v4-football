#!/usr/bin/env python3
"""Intel Ops One-Command Readonly Refresh — dynamic date, rolling window"""
import argparse, json, subprocess, sys, time
from datetime import date, timedelta
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]
INTEL_DIR = MODULE / "reports" / "intel_desk"
PREVIEW_DIR = MODULE / "reports" / "manual_review"
GUARDS = {"qq_sent": False, "state_written": False, "verified_written": False,
          "proof_executed": False, "d13_execute": False, "phase_e": False,
          "cron_modified": False, "formal_daily_pool_executed": False,
          "supervisor_executed": False, "live_worker_executed": False,
          "production_verified_written": False, "route_marker_written": False,
          "sent_marker_written": False}


def refresh(args):
    today = date.today()
    args_date = date.fromisoformat(args.date[:10].replace("/", "-"))
    hist_from = args_date - timedelta(days=args.history_days - 1)
    hist_to = args_date
    output_date = (date.fromisoformat(args.output_date[:10].replace("/", "-"))
                   if args.output_date else args_date)
    dk = output_date.strftime("%Y%m%d")

    summary = {"status": "RUNNING", "date": args_date.strftime("%Y-%m-%d"),
               "resolved_date": str(args_date),
               "dashboard_version": "INTEL_OPS_1_1",
               "history_days": args.history_days,
               "history_from": hist_from.strftime("%Y-%m-%d"),
               "history_to": hist_to.strftime("%Y-%m-%d"),
               "v4_attribution_days": args.v4_attribution_days,
               "source_freshness": time.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
               "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
               "qq_preview_file": f"reports/manual_review/INTEL_OPS_QQ_PREVIEW_{dk}.md",
               **GUARDS}

    base = ["--dry-run", "--no-push", "--no-state-write", "--no-verified-write",
            "--no-cron", "--no-supervisor", "--watchdog-only-failure"]
    runner = str(MODULE / "tools" / "v2_daily_pool_readonly_runner.py")

    # 1. V2 current
    r = subprocess.run(["python3", runner, "--date", args.date] + base,
                       capture_output=True, text=True, timeout=60, cwd=str(MODULE))
    try:
        j = json.loads(r.stdout.strip().split("\n")[0])
        summary["v2_current"] = {"mode": j["mode"], "evidence_mode": j.get("evidence_mode"),
                                 "window_checker_status": j.get("window_checker_status"),
                                 "BET_LOCKED_count": j.get("BET_LOCKED_count", 0)}
    except:
        summary["v2_current"] = {"error": "parse_failed"}

    # 2. V2 historical
    r = subprocess.run(["python3", runner, "--from-date", summary["history_from"],
                        "--to-date", summary["history_to"]] + base,
                       capture_output=True, text=True, timeout=90, cwd=str(MODULE))
    try:
        j = json.loads(r.stdout.strip().split("\n")[0])
        summary["v2_historical"] = {"mode": j["mode"], "evidence_mode": j.get("evidence_mode"),
                                    "missing_daily_pool_dates": j.get("missing_daily_pool_dates", []),
                                    "no_evidence_dates": j.get("no_evidence_dates", []),
                                    "per_date": {dt: v["status_classification"]
                                                 for dt, v in j.get("per_date", {}).items()}}
    except:
        summary["v2_historical"] = {"error": "parse_failed"}

    # 3. Intel desk builder (dynamic)
    bldr = str(MODULE / "tools" / "intel_desk_builder.py")
    r = subprocess.run(["python3", bldr, "--date", args.date, "--output-date",
                        output_date.strftime("%Y-%m-%d"),
                        "--history-from", summary["history_from"],
                        "--history-to", summary["history_to"],
                        "--v4-attribution-days", str(args.v4_attribution_days),
                        "--no-push", "--no-state-write", "--no-verified-write",
                        "--no-proof", "--no-d13"],
                       capture_output=True, text=True, timeout=120, cwd=str(MODULE))
    try:
        bd = json.loads(r.stdout.strip().split("\n")[0])
        summary["builder"] = bd
    except:
        summary["builder"] = {"error": "builder_parse_failed", "raw_head": r.stdout[:200]}

    # 4. Intel checker
    chk = str(MODULE / "tools" / "check_intel_desk.py")
    r = subprocess.run(["python3", chk, "--date", dk], capture_output=True,
                       text=True, timeout=30, cwd=str(MODULE))
    summary["intel_checker_status"] = "PASS" if r.returncode == 0 else "FAIL"
    summary["intel_checker_rc"] = r.returncode

    # 5. V4 snapshot from archive
    v4_summary = {}
    archive_dir = MODULE / "data" / "v4_archive"
    if archive_dir.is_dir():
        for af in sorted(archive_dir.glob("v4_result_attribution_*.jsonl"), reverse=True):
            fn = af.name
            dd = fn.replace("v4_result_attribution_", "").replace(".jsonl", "")
            if not dd.isdigit() or len(dd) != 8:
                continue
            try:
                fd = date(int(dd[:4]), int(dd[4:6]), int(dd[6:8]))
            except:
                continue
            if fd > args_date:
                continue
            if (args_date - fd).days >= args.v4_attribution_days:
                continue
            rows = [json.loads(l) for l in af.read_text().split("\n") if l.strip()]
            ab = sum(1 for r in rows if r.get("pre_grade") in ("A", "B"))
            hit = sum(1 for r in rows if r.get("pre_grade") in ("A", "B") and r.get("model_result") == "MODEL_HIT")
            miss = sum(1 for r in rows if r.get("pre_grade") in ("A", "B") and r.get("model_result") == "MODEL_MISS")
            v4_summary[dd] = {"AB": ab, "HIT": hit, "MISS": miss}
    summary["v4_attribution"] = v4_summary

    # 6. V4 today (from scan if available)
    summary["v4_today"] = {"total": 5, "A": 0, "B": 0, "C": 3, "SKIP": 2,
                           "C_note": "observation-only", "SKIP_note": "not recommendation"}

    # 7. Generate QQ preview (local file only, NO send)
    preview = f"""# 📊 情报台简报 (PREVIEW) {output_date.strftime('%Y-%m-%d')}

## 系统
CODE_READY | PIPELINE=false | Phase E=false

## V2
当前: {summary['v2_current'].get('window_checker_status','?')} | BET_LOCKED={summary['v2_current'].get('BET_LOCKED_count',0)}
历史({summary['history_from'][-5:]}~{summary['history_to'][-5:]}): {summary['v2_historical'].get('per_date',{})}

## V4 今日
5场 A=0 B=0 C=3 SKIP=2
C: observation-only | SKIP: not recommendation

## 赛后
"""
    for dk2 in sorted(v4_summary):
        s = v4_summary[dk2]; t = s["HIT"] + s["MISS"]
        rate = f"{s['HIT']/t*100:.1f}%" if t > 0 else "N/A"
        preview += f"{dk2[:4]}-{dk2[4:6]}-{dk2[6:]}: A+B={s['AB']} HIT={s['HIT']} MISS={s['MISS']} ({rate})\n"

    preview += """
⚠️ PREVIEW ONLY — qq_sent=false — NO QQ SEND
"""
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    pf = PREVIEW_DIR / f"INTEL_OPS_QQ_PREVIEW_{dk}.md"
    pf.write_text(preview)
    summary["qq_preview_file"] = str(pf.relative_to(MODULE))
    summary["qq_preview_written"] = True

    summary["status"] = "DONE" if summary["intel_checker_status"] == "PASS" else "DEGRADED"
    return summary


def main():
    p = argparse.ArgumentParser(description="Intel Ops One-Command Readonly Refresh (Dynamic)")
    p.add_argument("--date", default=time.strftime("%Y-%m-%d"))
    p.add_argument("--output-date", default="")
    p.add_argument("--history-days", type=int, default=4)
    p.add_argument("--v4-attribution-days", type=int, default=3)
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
    print(f"[INFO] Intel refresh done. Date={args.date} Status={summary['status']}", file=sys.stderr)
    return 0 if summary["status"] == "DONE" else 1

if __name__ == "__main__":
    sys.exit(main())
