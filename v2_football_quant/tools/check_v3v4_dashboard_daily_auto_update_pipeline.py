#!/usr/bin/env python3
from __future__ import annotations
import json, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
STATUS=ROOT/'data/runtime/status'
PLAN=STATUS/'v3v4_dashboard_daily_auto_update_cron_plan_20260523.json'
RUNNER=ROOT/'tools/run_v3v4_dashboard_daily_update.py'

def load(p):
    try: return json.loads(p.read_text(encoding='utf-8'))
    except Exception: return {}

def run(phase):
    r=subprocess.run([sys.executable,str(RUNNER),'--date','20260523','--phase',phase,'--mode','dry-run','--no-api','--no-capture','--no-push','--no-cloud','--strict'],cwd=str(ROOT),text=True,capture_output=True,timeout=15)
    try: data=json.loads(r.stdout)
    except Exception: data={}
    return r.returncode,data

def main():
    p=load(PLAN); blockers=[]; warnings=[]
    if not RUNNER.exists(): blockers.append('runner_missing')
    rc_scan, scan = run('after-scan') if RUNNER.exists() else (99,{})
    rc_val, val = run('after-validation') if RUNNER.exists() else (99,{})
    if rc_scan!=0: blockers.append(f'after_scan_runner_rc_{rc_scan}')
    if rc_val!=0: blockers.append(f'after_validation_runner_rc_{rc_val}')
    if scan.get('validation_touched') is not False: blockers.append('after_scan_validation_touched')
    if val.get('candidate_touched') is not False: blockers.append('after_validation_candidate_touched')
    if scan.get('planned_time')!='13:00': blockers.append('after_scan_time_not_1300')
    if val.get('planned_time')!='13:30': blockers.append('after_validation_time_not_1330')
    for label,obj in [('after_scan',scan),('after_validation',val)]:
        for k in ['cron_enabled','autosync_cron_created','capture_ran','QQ_push','push_enabled','cloud_publish','auto_retry','auto_kill','timeout_change','brief_used_for_hit_rate','scan_date_used_for_validation','v2_restored','v33_active','c_active_in_dashboard','c_validation_visible','last_7d_visible','strategy_changed','v4_candidate_numbers_changed','validation_numbers_changed','attribution_numbers_changed']:
            if obj.get(k) is not False: blockers.append(f'{label}_{k}_not_false')
    out={'checker':'tools/check_v3v4_dashboard_daily_auto_update_pipeline.py','phase':'V3V4-DASHBOARD-DAILY-AUTO-UPDATE-SCHEDULE-CORRECTION-20260523','conclusion':'PASS' if not blockers else 'BLOCKER','phase_boundary_guard':not blockers,'after_scan_time':scan.get('planned_time'),'after_validation_time':val.get('planned_time'),'after_scan_validation_touched':scan.get('validation_touched'),'after_validation_candidate_touched':val.get('candidate_touched'),'cron_enabled':p.get('cron_enabled'),'blockers':blockers,'warnings':warnings}
    (STATUS/'check_v3v4_dashboard_daily_auto_update_pipeline_result_20260523.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(out,ensure_ascii=False,indent=2)); return 0 if not blockers else 2
if __name__=='__main__': raise SystemExit(main())
