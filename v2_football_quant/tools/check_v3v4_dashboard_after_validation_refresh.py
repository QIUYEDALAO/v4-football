#!/usr/bin/env python3
from __future__ import annotations
import json, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
STATUS=ROOT/'data/runtime/status'
RUNNER=ROOT/'tools/run_v3v4_dashboard_daily_update.py'

def main():
    blockers=[]
    r=subprocess.run([sys.executable,str(RUNNER),'--date','20260523','--phase','after-validation','--mode','dry-run','--no-api','--no-capture','--no-push','--no-cloud','--strict'],cwd=str(ROOT),text=True,capture_output=True,timeout=15)
    try: data=json.loads(r.stdout)
    except Exception: data={}; blockers.append('runner_output_not_json')
    if r.returncode!=0: blockers.append(f'runner_rc_{r.returncode}')
    if data.get('planned_time')!='13:30': blockers.append('after_validation_time_not_1330')
    if data.get('requires_validation_completed') is not True: blockers.append('requires_validation_completed_not_true')
    if data.get('candidate_touched') is not False: blockers.append('candidate_touched')
    if data.get('date_filter_field')!='match_date': blockers.append('validation_not_match_date')
    if data.get('brief_used_for_hit_rate') is not False: blockers.append('brief_used_for_hit_rate')
    for bad in ['today_candidate_source','brief_source','candidate_raw_numbers','v4_strategy']:
        if bad not in data.get('forbidden_updates',[]): blockers.append(f'missing_forbidden_{bad}')
    for k in ['capture_ran','v4_scan_ran','QQ_push','push_enabled','cloud_publish','cron_enabled','auto_retry','auto_kill','timeout_change','strategy_changed','v4_candidate_numbers_changed']:
        if data.get(k) is not False: blockers.append(f'{k}_not_false')
    out={'checker':'tools/check_v3v4_dashboard_after_validation_refresh.py','phase':'V3V4-DASHBOARD-DAILY-AUTO-UPDATE-SCHEDULE-CORRECTION-20260523','conclusion':'PASS' if not blockers else 'BLOCKER','after_validation_time':data.get('planned_time'),'requires_validation_completed':data.get('requires_validation_completed'),'validation_ready':data.get('validation_ready'),'candidate_touched':data.get('candidate_touched'),'brief_used_for_hit_rate':data.get('brief_used_for_hit_rate'),'date_filter_field':data.get('date_filter_field'),'status':data.get('status'),'blockers':blockers}
    (STATUS/'check_v3v4_dashboard_after_validation_refresh_result_20260523.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(out,ensure_ascii=False,indent=2)); return 0 if not blockers else 2
if __name__=='__main__': raise SystemExit(main())
