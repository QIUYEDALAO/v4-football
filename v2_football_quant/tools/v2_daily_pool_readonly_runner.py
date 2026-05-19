#!/usr/bin/env python3
"""V2 DAILY_POOL Readonly Runner — current mode + historical evidence scan"""
import argparse, json, re, subprocess, sys
from datetime import date, timedelta
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]
WIN_CHK = MODULE / "engine" / "v2_window_checker_with_watchdog.py"

EVIDENCE_KEYWORDS = [
    "daily_pool", "DAILY_POOL", "BET_LOCKED", "daily_runner",
    "v2_daily_status_push", "v2_daily_pool_summary",
]

def _find_evidence(dt_str: str, dt_dashed: str) -> dict:
    """Scan file tree for DAILY_POOL evidence on a given date, never calling the live window checker."""
    evidence = {"date": dt_str, "evidence_mode": "HISTORICAL_FILE_SCAN",
                "daily_pool_evidence_found": False, "daily_pool_files": [],
                "bet_locked_evidence_found": False, "bet_locked_count": 0,
                "watch_early_count": 0, "candidate_count": 0, "ht_skip_count": 0,
                "window_evidence_found": False, "log_evidence_found": False,
                "marker_found": False, "ledger_found": False,
                "status_classification": "NO_EVIDENCE_FOUND",
                "evidence_paths": [], "blocker_reason": ""}

    for root in ["data/runtime", "data", "reports", "logs"]:
        base = MODULE / root
        if not base.is_dir():
            continue
        for fp in base.rglob("*"):
            fname = fp.name
            if not (dt_str in fname or dt_dashed in fname):
                continue
            evidence["evidence_paths"].append(str(fp.relative_to(MODULE)))

            # Ledger
            if "ledger" in str(fp) and fp.is_file():
                try:
                    ld = json.loads(fp.read_text())
                    v2 = ld.get("v2", {})
                    if v2.get("daily_pool_status") == "DONE":
                        evidence["daily_pool_evidence_found"] = True
                        evidence["daily_pool_files"].append(str(fp.relative_to(MODULE)))
                        evidence["ledger_found"] = True
                        evidence["bet_locked_count"] = len(v2.get("official_bet_locked", [])) if isinstance(v2.get("official_bet_locked"), list) else v2.get("official_bet_locked", 0)
                        evidence["bet_locked_evidence_found"] = True
                except:
                    pass

            # P0 DAILY_POOL_MISSING marker
            if "P0_DAILY_POOL_MISSING" in fname:
                evidence["marker_found"] = True
                evidence["daily_pool_evidence_found"] = False
                evidence["daily_pool_files"].append(str(fp.relative_to(MODULE)))
                evidence["status_classification"] = "DAILY_POOL_MISSING"
                evidence["blocker_reason"] = "Daily pool did not run (P0 marker)"

            # v2_daily_status_push file
            if "v2_daily_status_push" in fname and fp.is_file():
                try:
                    dd = json.loads(fp.read_text())
                    evidence["daily_pool_evidence_found"] = True
                    evidence["daily_pool_files"].append(str(fp.relative_to(MODULE)))
                    evidence["window_evidence_found"] = True
                except:
                    pass

            # Other files with "daily_pool" in name — record but do NOT count as execution proof
            if "daily_pool" in fname.lower() and fp.is_file() and fp.suffix == ".json":
                evidence["daily_pool_files"].append(str(fp.relative_to(MODULE)))

    # Check v2_quant log
    logf = MODULE / "logs" / f"v2_quant_{dt_dashed}.log"
    if logf.is_file():
        evidence["log_evidence_found"] = True
        evidence["evidence_paths"].append(str(logf.relative_to(MODULE)))
        log_text = logf.read_text()
        if any(kw in log_text for kw in ["DAILY_POOL", "daily_runner", "BET_LOCKED"]):
            evidence["daily_pool_evidence_found"] = True
            # Try extract BET_LOCKED count from log
            m = re.search(r"BET_LOCKED[：:]\s*(\d+)", log_text)
            if m:
                evidence["bet_locked_count"] = int(m.group(1))
                evidence["bet_locked_evidence_found"] = True

    # Classify
    if evidence["status_classification"] != "DAILY_POOL_MISSING":
        if evidence["daily_pool_evidence_found"]:
            evidence["status_classification"] = "DAILY_POOL_FOUND"
        elif evidence["log_evidence_found"] or evidence["marker_found"]:
            evidence["status_classification"] = "DAILY_POOL_MISSING"
        else:
            evidence["status_classification"] = "NO_EVIDENCE_FOUND"

    return evidence


def _current_check(dt: str) -> dict:
    """Run live window checker for current date only."""
    r = subprocess.run(["python3", str(WIN_CHK), "--no-push", "--observe-only", "--no-formal-state-write", "--no-verified-write"], capture_output=True, text=True, timeout=60, cwd=str(MODULE))
    out = r.stdout
    result = {"date": dt, "evidence_mode": "CURRENT_WINDOW_CHECKER",
              "window_checker_status": "UNKNOWN",
              "BET_LOCKED_count": 0, "WATCH_EARLY_count": 0,
              "CANDIDATE_count": 0, "HT_SKIP_count": 0,
              "window_checker_returncode": r.returncode}
    if "SKIPPED" in out:
        result["window_checker_status"] = "SKIPPED_NO_ACTIVE_WINDOW"
    m = re.search(r"BET_LOCKED[：:]\s*(\d+)", out)
    if m: result["BET_LOCKED_count"] = int(m.group(1))
    m = re.search(r"WATCH_EARLY[：:]\s*(\d+)", out)
    if m: result["WATCH_EARLY_count"] = int(m.group(1))
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--date", default="")
    p.add_argument("--from-date", default="")
    p.add_argument("--to-date", default="")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--review-only", action="store_true")
    p.add_argument("--no-push", action="store_true")
    p.add_argument("--no-state-write", action="store_true")
    p.add_argument("--no-verified-write", action="store_true")
    p.add_argument("--no-cron", action="store_true")
    p.add_argument("--no-supervisor", action="store_true")
    p.add_argument("--watchdog-only-failure", action="store_true")
    p.add_argument("--pretty", action="store_true")
    args = p.parse_args()

    GUARDS = {"qq_sent": False, "state_written": False, "verified_written": False,
              "proof_executed": False, "cron_modified": False, "supervisor_executed": False,
              "formal_daily_pool_executed": False}

    if args.from_date and args.to_date:
        # HISTORICAL EVIDENCE SCAN — never calls live window checker
        fd = date.fromisoformat(args.from_date[:10].replace("/", "-"))
        td = date.fromisoformat(args.to_date[:10].replace("/", "-"))
        dates = []
        d = fd
        while d <= td:
            dates.append(d.strftime("%Y-%m-%d"))
            d += timedelta(days=1)

        per_date = {}
        for dt in dates:
            dt_str = dt.replace("-", "")
            per_date[dt] = _find_evidence(dt_str, dt)

        missing_dates = [dt for dt, v in per_date.items() if v["status_classification"] in ("DAILY_POOL_MISSING", "NO_EVIDENCE_FOUND")]
        bet_dates = [dt for dt, v in per_date.items() if v["bet_locked_evidence_found"] and v.get("bet_locked_count", 0) > 0]
        no_evidence_dates = [dt for dt, v in per_date.items() if v["status_classification"] == "NO_EVIDENCE_FOUND"]

        result = {"mode": "READONLY_HISTORICAL_EVIDENCE_SCAN",
                  "evidence_mode": "HISTORICAL_FILE_SCAN",
                  "from_date": args.from_date, "to_date": args.to_date,
                  "dates_checked": len(dates),
                  "missing_daily_pool_dates": missing_dates,
                  "no_evidence_dates": no_evidence_dates,
                  "bet_locked_dates": bet_dates,
                  "evidence_paths": list({p for v in per_date.values() for p in v.get("evidence_paths", [])}),
                  "per_date": per_date, **GUARDS}
    else:
        dt = args.date or date.today().strftime("%Y-%m-%d")
        result = _current_check(dt)
        result["mode"] = "READONLY_CURRENT"
        result["readonly_check_executed"] = True
        result["no_push"] = args.no_push
        result["no_state_write"] = args.no_state_write
        result["no_verified_write"] = args.no_verified_write
        result.update(GUARDS)

    if args.pretty:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(result, ensure_ascii=False))
    if args.from_date:
        print(f"[INFO] Historical evidence scan {args.from_date} to {args.to_date}: {len(dates)} dates.", file=sys.stderr)
    else:
        print(f"[INFO] Readonly check complete. No formal DAILY_POOL run.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
