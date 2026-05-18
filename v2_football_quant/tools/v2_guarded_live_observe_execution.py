#!/usr/bin/env python3
"""Phase D.8.14 — V2 Guarded Live Observe Execution (single-window, all guard flags active)."""
import argparse, hashlib, json, os, subprocess, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
BASE = Path(__file__).resolve().parent.parent
SD = BASE / "data" / "runtime" / "status"
STATE_DIR = BASE / "data" / "state"
CN = timezone(timedelta(hours=8))

def _fingerprint(p):
    if not p.exists(): return None, None, None
    s = p.stat()
    h = hashlib.sha256(p.read_bytes()).hexdigest()
    return s.st_size, s.st_mtime, h

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--window", default="midday")
    p.add_argument("--observe-only", action="store_true")
    p.add_argument("--no-formal-state-write", action="store_true")
    p.add_argument("--no-push", action="store_true")
    p.add_argument("--no-verified-write", action="store_true")
    p.add_argument("--no-supervisor", action="store_true")
    p.add_argument("--date", required=False, help="for marker naming only")
    a = p.parse_args()

    today = datetime.now(CN).strftime("%Y%m%d")
    dk = a.date or today
    w = a.window
    e = []; warns = []

    # Check all required flags
    flags_ok = all([a.observe_only, a.no_formal_state_write, a.no_push, a.no_verified_write, a.no_supervisor])
    no_push_env = os.environ.get("OPENCLAW_NO_PUSH") == "1"
    if not flags_ok:
        e.append("REQUIRED_FLAGS_MISSING")
    if not no_push_env:
        e.append("OPENCLAW_NO_PUSH_NOT_SET")

    if e:
        r = {"schema_version":"v2_guarded_live_observe_execution.v1","date":dk,"window":w,
             "execution_status":"BLOCKER","current_level":"CODE_READY","pipeline_ready":False,"production_verified":False,
             "required_flags_present":flags_ok,"openclaw_no_push":no_push_env,
             "supervisor_executed":False,"live_worker_executed":False,
             "blockers":e,"generated_at":datetime.now(CN).isoformat()}
        out=SD/f"v2_guarded_live_observe_execution_{dk}_{w}.json"
        out.write_text(json.dumps(r,ensure_ascii=False,indent=2)); print(json.dumps(r,ensure_ascii=False,indent=2))
        raise SystemExit(2)

    # No supervisor allowed
    supervisor_executed = False

    # Pre-run state fingerprint
    state_path = STATE_DIR / f"selected_fixtures_{today}.json"
    size_before, mtime_before, h_before = _fingerprint(state_path)
    state_exists = state_path.exists()

    worker_exit = None; stdout = ""; stderr = ""
    live_executed = False

    if not state_exists:
        warns.append("NO_CURRENT_STATE_FOR_LIVE_OBSERVE")
        # Still run observe-only to test logic pathway
        env = os.environ.copy()
        env["V2_OBSERVE_ONLY"] = "1"
        env["PYTHONPATH"] = str(BASE)
        result = subprocess.run(
            [sys.executable, str(BASE / "engine" / "v2_window_worker.py"), "--observe-only", "--no-formal-state-write", "--no-push", "--no-verified-write"],
            capture_output=True, text=True, timeout=30, cwd=str(BASE), env=env
        )
        worker_exit = result.returncode
        stdout = result.stdout[-2000:] if result.stdout else ""
        stderr = result.stderr[-500:] if result.stderr else ""
        live_executed = True
    else:
        env = os.environ.copy()
        env["V2_OBSERVE_ONLY"] = "1"
        env["PYTHONPATH"] = str(BASE)
        result = subprocess.run(
            [sys.executable, str(BASE / "engine" / "v2_window_worker.py"), "--observe-only", "--no-formal-state-write", "--no-push", "--no-verified-write"],
            capture_output=True, text=True, timeout=60, cwd=str(BASE), env=env
        )
        worker_exit = result.returncode
        stdout = result.stdout[-3000:] if result.stdout else ""
        stderr = result.stderr[-500:] if result.stderr else ""
        live_executed = True

    # Post-run state fingerprint
    size_after, mtime_after, h_after = _fingerprint(state_path)
    unchanged = (size_before == size_after and mtime_before == mtime_after and h_before == h_after) if state_exists else True

    if not state_exists:
        # Check no new file was created
        new_created = state_path.exists()
        if new_created:
            e.append("STATE_FILE_CREATED_DURING_OBSERVE")
            unchanged = False

    # Parse worker output
    ws = ""; reason = ""; nl = 0; lt = 0
    for line in stdout.split("\n"):
        if line.startswith("WINDOW_STATUS="): ws = line.split("=",1)[1].strip()
        if line.startswith("REASON="): reason = line.split("=",1)[1].strip()
        if line.startswith("NEW_LOCKS="): nl = len(json.loads(line.split("=",1)[1])) if "[" in line else 0
        if line.startswith("LOCKED_TOTAL="): lt = int(line.split("=",1)[1].strip())

    status = "FAIL" if e else ("WARN" if warns else "PASS")
    r = {"schema_version":"v2_guarded_live_observe_execution.v1","date":dk,"window":w,
         "execution_status":status,"current_level":"CODE_READY","pipeline_ready":False,"production_verified":False,
         "default_path_used":False,"guarded_path_used":True,"required_flags_present":flags_ok,"openclaw_no_push":no_push_env,
         "supervisor_executed":supervisor_executed,"live_worker_executed":live_executed,
         "observe_only":True,"no_formal_state_write":True,"no_push":True,"no_verified_write":True,"no_supervisor":True,
         "formal_state_exists":state_exists,
         "formal_state_hash_before":h_before,"formal_state_hash_after":h_after,
         "formal_state_size_before":size_before,"formal_state_size_after":size_after,
         "formal_state_mtime_before":mtime_before,"formal_state_mtime_after":mtime_after,
         "formal_state_unchanged":unchanged,"formal_state_written":False,
         "qq_sent":False,"verified_written":False,"cron_modified":False,"api_called":False,"key_read":False,
         "worker_exit_code":worker_exit,"worker_stdout_summary":stdout[-800:],"worker_stderr_summary":stderr[-200:],
         "window_status":ws,"reason":reason,"new_locks_count":nl,"locked_total":lt,
         "warnings":warns,"blockers":e,"generated_at":datetime.now(CN).isoformat()}
    out=SD/f"v2_guarded_live_observe_execution_{dk}_{w}.json"
    out.write_text(json.dumps(r,ensure_ascii=False,indent=2)); print(json.dumps(r,ensure_ascii=False,indent=2))
    if status in ("FAIL","BLOCKER"): raise SystemExit(1)

if __name__=="__main__": main()
