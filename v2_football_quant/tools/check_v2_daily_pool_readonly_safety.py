#!/usr/bin/env python3
"""V2 DAILY_POOL Readonly Safety Checker"""
import json, re, subprocess, sys
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]
RUNNER = MODULE / "tools" / "v2_daily_pool_readonly_runner.py"

def run(args_list):
    r = subprocess.run(["python3", str(RUNNER)] + args_list,
                       capture_output=True, text=True, timeout=60, cwd=str(MODULE))
    return r.returncode, r.stdout, r.stderr

def parse_json(text):
    for line in text.strip().split("\n"):
        if line.startswith("{"):
            try: return json.loads(line)
            except: continue
    try: return json.loads(text.strip())
    except: return None

def main():
    R = {"check_status": "PASS", "runner_exists": RUNNER.is_file(),
         "help_ok": False, "current_date_ok": False, "replay_ok": False,
         "json_parse_pass": False, "blockers": [], "warnings": []}
    block = False
    if not RUNNER.is_file():
        R["blockers"].append("Runner missing"); block = True
        _finish(R, block)

    # Help check
    rc, out, _ = run(["--help"])
    requires = ["date", "from-date", "to-date", "dry-run", "no-push",
                "no-state-write", "no-verified-write", "no-cron", "no-supervisor"]
    missing = [a for a in requires if a not in out.replace("_", "-")]
    R["help_ok"] = len(missing) == 0
    if missing: R["blockers"].append(f"Missing flags: {missing}"); block = True

    # Current-date
    rc, out, _ = run(["--date", "2026-05-20", "--dry-run", "--no-push",
        "--no-state-write", "--no-verified-write", "--no-cron", "--no-supervisor"])
    j = parse_json(out)
    if j:
        R["current_date_ok"] = True; R["json_parse_pass"] = True
        danger = ["formal_daily_pool_executed", "qq_sent", "state_written",
                  "verified_written", "proof_executed", "cron_modified", "supervisor_executed"]
        for f in danger:
            if j.get(f, False):
                R["blockers"].append(f"{f}=true"); block = True
    else:
        R["blockers"].append("Current-date JSON parse failed"); block = True

    # Replay
    rc, out, _ = run(["--from-date", "2026-05-17", "--to-date", "2026-05-20",
        "--dry-run", "--no-push", "--no-state-write", "--no-verified-write",
        "--no-cron", "--no-supervisor"])
    j = parse_json(out)
    if j: R["replay_ok"] = True; R["replay_dates"] = j.get("dates_checked", 0)
    else: R["blockers"].append("Replay JSON parse failed"); block = True

    _finish(R, block)

def _finish(R, block):
    if block: R["check_status"] = "BLOCKER"
    elif R["warnings"]: R["check_status"] = "WARN"
    print("V2 DAILY_POOL READONLY SAFETY CHECKER")
    print(f"Status: {R['check_status']}")
    print(f"  runner_exists: {R['runner_exists']}")
    print(f"  help_ok: {R['help_ok']}")
    print(f"  current_date_ok: {R['current_date_ok']}")
    print(f"  replay_ok: {R['replay_ok']}")
    print(f"  json_parse_pass: {R['json_parse_pass']}")
    if R["blockers"]:
        print(f"BLOCKERS ({len(R['blockers'])}):")
        for b in R["blockers"]: print(f"  ! {b}")
    md = MODULE / "data" / "runtime" / "status"
    md.mkdir(parents=True, exist_ok=True)
    mf = md / "v2_daily_pool_readonly_safety_check.json"
    mf.write_text(json.dumps(R, indent=2, ensure_ascii=False))
    print(f"Marker: {mf} (NOT committed)")
    sys.exit(1 if block else 0)

if __name__ == "__main__":
    main()
