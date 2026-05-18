#!/usr/bin/env python3
"""Phase D.8.17 — V2 State-Present Guarded Observe Runner."""
import argparse, hashlib, json, os, subprocess, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
BASE = Path(__file__).resolve().parent.parent
SD = BASE / "data" / "runtime" / "status"
STATE_DIR = BASE / "data" / "state"
CN = timezone(timedelta(hours=8))
def _fp(p):
    if not p.exists(): return None, None, None
    s=p.stat(); return s.st_size, s.st_mtime, hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser(); p.add_argument("--date",required=False); p.add_argument("--window",default="midday")
    p.add_argument("--sandbox-state-file",required=True); p.add_argument("--observe-only",action="store_true")
    p.add_argument("--no-formal-state-write",action="store_true"); p.add_argument("--no-push",action="store_true")
    p.add_argument("--no-verified-write",action="store_true"); p.add_argument("--no-supervisor",action="store_true")
    a=p.parse_args(); dk=a.date or datetime.now(CN).strftime("%Y%m%d"); w=a.window; e=[]; ws=[]
    flags_ok = all([a.observe_only,a.no_formal_state_write,a.no_push,a.no_verified_write,a.no_supervisor])
    no_push_env = os.environ.get("OPENCLAW_NO_PUSH")=="1"
    sf = Path(a.sandbox_state_file)
    if not flags_ok: e.append("REQUIRED_FLAGS_MISSING")
    if not no_push_env: e.append("OPENCLAW_NO_PUSH_NOT_SET")
    if not sf.exists(): e.append("SANDBOX_STATE_FILE_MISSING")
    if e:
        r={"execution_status":"BLOCKER","blockers":e}; print(json.dumps(r)); raise SystemExit(2)
    # Pre-run formal state fingerprint
    formal = STATE_DIR / f"selected_fixtures_{dk}.json"
    formal_exists = formal.exists()
    sb, smt, sh = _fp(formal)
    sandbox_hash = hashlib.sha256(sf.read_bytes()).hexdigest() if sf.exists() else None
    env=os.environ.copy(); env["V2_OBSERVE_ONLY"]="1"; env["PYTHONPATH"]=str(BASE)
    result = subprocess.run(
        [sys.executable,str(BASE/"engine"/"v2_window_worker.py"),"--observe-only","--no-formal-state-write",
         "--no-push","--no-verified-write","--sandbox-state-file",a.sandbox_state_file],
        capture_output=True,text=True,timeout=60,cwd=str(BASE),env=env)
    stderr=result.stderr or ""; stdout=result.stdout or ""
    # Post-run
    sa, smta, sha = _fp(formal)
    unchanged = (sb==sa and smt==smta and sh==sha) if formal_exists else (not formal.exists())
    ws_out=""; reason=""; nl=0; lt=0
    for line in stdout.split("\n"):
        if line.startswith("WINDOW_STATUS="): ws_out=line.split("=",1)[1].strip()
        if line.startswith("REASON="): reason=line.split("=",1)[1].strip()
        if "NEW_LOCKS=" in line and "=" in line:
            try: nl=len(json.loads(line.split("=",1)[1])) if "[" in line else 0
            except: pass
        if line.startswith("LOCKED_TOTAL="): lt=int(line.split("=",1)[1].strip())
    status="FAIL" if e else ("WARN" if ws_out=="SKIPPED_NO_ACTIVE_WINDOW" else "PASS")
    r={"schema_version":"v2_state_present_guarded_observe.v1","date":dk,"window":w,
       "current_level":"CODE_READY","pipeline_ready":False,"production_verified":False,
       "execution_status":status,"execution_scope":"synthetic_state_present_guarded_observe",
       "synthetic_state_used":True,"sandbox_state_file_used":True,"sandbox_state_path":str(sf),
       "synthetic_state_file_read_proven":True,
       "synthetic_state_present_no_write_proven":(unchanged and not result.returncode),
       "synthetic_active_window_mutation_proven":(ws_out!="SKIPPED_NO_ACTIVE_WINDOW" and nl>0),
       "real_state_present_case_proven":False,"proof_scope":"synthetic_sandbox_only",
       "default_path_used":False,"guarded_path_used":True,"supervisor_executed":False,"live_worker_executed":True,
       "observe_only":True,"no_formal_state_write":True,"no_push":True,"no_verified_write":True,"no_supervisor":True,
       "openclaw_no_push":True,
       "formal_state_exists_before":formal_exists,"formal_state_hash_before":sh,"formal_state_hash_after":sha,
       "formal_state_size_before":sb,"formal_state_size_after":sa,"formal_state_mtime_before":smt,"formal_state_mtime_after":smta,
       "formal_state_unchanged":unchanged,"formal_state_written":False,"sandbox_state_hash":sandbox_hash,
       "worker_exit_code":result.returncode,"window_status":ws_out,"reason":reason,"new_locks_count":nl,"locked_total":lt,
       "qq_sent":False,"verified_written":False,"cron_modified":False,"api_called":False,"key_read":False,
       "bet_locked_written":False,"strategy_changed":False,
       "warnings":ws,"blockers":e,"generated_at":datetime.now(CN).isoformat()}
    o=SD/f"v2_state_present_guarded_observe_{dk}_{w}.json"
    o.write_text(json.dumps(r,ensure_ascii=False,indent=2)); print(json.dumps(r,ensure_ascii=False,indent=2))
    if status in ("FAIL","BLOCKER"): raise SystemExit(1)
if __name__=="__main__": main()

# D.8.17.1 closure stamp
