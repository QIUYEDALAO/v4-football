#!/usr/bin/env python3
from __future__ import annotations
import json, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
STATUS=ROOT/'data/runtime/status'
RUNNER=ROOT/'tools/run_v3v4_dashboard_daily_update.py'

def main():
    blockers=[]
    r=subprocess.run([sys.executable,str(RUNNER),'--date','20260523','--phase','after-scan','--mode','dry-run','--no-api','--no-capture','--no-push','--no-cloud','--strict'],cwd=str(ROOT),text=True,capture_output=True,timeout=15)
    try: data=json.loads(r.stdout)
    except Exception: data={}; blockers.append('runner_output_not_json')
    if r.returncode!=0: blockers.append(f'runner_rc_{r.returncode}')
    if data.get('planned_time')!='13:00': blockers.append('after_scan_time_not_1300')
    if data.get('requires_scan_completed') is not True: blockers.append('requires_scan_completed_not_true')
    if data.get('validation_touched') is not False: blockers.append('validation_touched')
    for bad in ['yesterday_validation','cumulative_validation','validation_summary','attribution','review']:
        if bad not in data.get('forbidden_updates',[]): blockers.append(f'missing_forbidden_{bad}')
    for k in ['capture_ran','v4_scan_ran','QQ_push','push_enabled','cloud_publish','cron_enabled','auto_retry','auto_kill','timeout_change']:
        if data.get(k) is not False: blockers.append(f'{k}_not_false')
    out={'checker':'tools/check_v3v4_dashboard_after_scan_refresh.py','phase':'V3V4-DASHBOARD-DAILY-AUTO-UPDATE-SCHEDULE-CORRECTION-20260523','conclusion':'PASS' if not blockers else 'BLOCKER','after_scan_time':data.get('planned_time'),'requires_scan_completed':data.get('requires_scan_completed'),'scan_completed':data.get('scan_completed'),'brief_ready':data.get('brief_ready'),'candidate_ready':data.get('candidate_ready'),'validation_touched':data.get('validation_touched'),'status':data.get('status'),'blockers':blockers}
    (STATUS/'check_v3v4_dashboard_after_scan_refresh_result_20260523.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(out,ensure_ascii=False,indent=2)); return 0 if not blockers else 2
if __name__=='__main__': raise SystemExit(main())
