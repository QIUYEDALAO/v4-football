#!/usr/bin/env python3
"""Checker: V3/V4 dashboard daily auto update pipeline — including 14:00 final.
"""
from __future__ import annotations
import json, subprocess, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
STATUS=ROOT/'data/runtime/status'

def load(p:Path)->dict:
    try: return json.loads(p.read_text(encoding='utf-8'))
    except: return {}

def main():
    TZ=timezone(timedelta(hours=8))
    DATE=datetime.now(TZ).strftime('%Y%m%d')
    p=load(STATUS/f'v3v4_dashboard_daily_auto_update_cron_plan_{DATE}.json')
    blockers=[]; warnings=[]

    # After-scan runner test
    rc_scan=subprocess.run([sys.executable,str(ROOT/'tools/run_v3v4_dashboard_daily_update.py'),'--date',DATE,'--phase','after-scan','--mode','dry-run','--no-api','--no-capture','--no-push','--no-cloud'],capture_output=True,text=True,timeout=30)
    scan=load(STATUS/f"v3v4_dashboard_daily_update_after_scan_dry_run_{DATE}.json")
    if rc_scan.returncode!=0: warnings.append(f'after_scan_runner_rc_{rc_scan.returncode}')
    if scan.get('validation_touched') is not False: blockers.append('after_scan_validation_touched')
    if scan.get('validation_preserved') is not True: blockers.append('after_scan_validation_not_preserved')
    if scan.get('candidate_touched') is not False: blockers.append('after_scan_candidate_touched_before_apply')

    # After-validation runner test (13:30)
    rc_val=subprocess.run([sys.executable,str(ROOT/'tools/run_v3v4_dashboard_daily_update.py'),'--date',DATE,'--phase','after-validation','--mode','dry-run','--no-api','--no-capture','--no-push','--no-cloud'],capture_output=True,text=True,timeout=30)
    val=load(STATUS/f"v3v4_dashboard_daily_update_after_validation_dry_run_{DATE}.json")
    if rc_val.returncode!=0: warnings.append(f'after_validation_runner_rc_{rc_val.returncode}')
    if val.get('candidate_touched') is not False: blockers.append('after_validation_candidate_touched')
    if val.get('yesterday_validation_target_date')!='20260523': blockers.append('after_validation_target_date_not_20260523')
    if val.get('planned_time')!='13:30': blockers.append('after_validation_time_not_1330')

    # Final check (14:00). This must run a second validation dry-run and then
    # refresh/noop the dashboard validation section depending on source hash.
    final_tasks=[x for x in p.get('schedule',[]) if isinstance(x,dict) and x.get('task')=='V4_VALIDATION_DRY_RUN_FINAL_AND_DASHBOARD_REFRESH']
    if not final_tasks:
        blockers.append('final_refresh_task_missing_in_plan')
    else:
        ft=final_tasks[0]
        if ft.get('time')!='14:00': blockers.append(f"final_refresh_time_{ft.get('time','?').replace(':','_')}_not_1400")
        if ft.get('type')=='scan': blockers.append('final_refresh_type_is_scan')
        if ft.get('type')!='validation-final-dashboard-refresh': blockers.append('final_refresh_type_not_validation_final_dashboard_refresh')
        if ft.get('final_validation') is not True: blockers.append('final_validation_flag_missing')
        if ft.get('dashboard_refresh') is not True: blockers.append('final_dashboard_refresh_flag_missing')

    final_cfg=(p.get('tasks') or {}).get('final-validation-dashboard-refresh', {}) if isinstance(p.get('tasks'), dict) else {}
    final_cmd=str(final_cfg.get('command',''))
    if 'run_v3v4_validation_final_and_dashboard_refresh.py' not in final_cmd: blockers.append('final_command_not_validation_final_runner')

    rc_final=subprocess.run([sys.executable,str(ROOT/'tools/run_v3v4_validation_final_and_dashboard_refresh.py'),'--date',DATE,'--mode','dry-run','--no-capture','--no-push','--no-cloud','--strict'],capture_output=True,text=True,timeout=180)
    final_marker=load(STATUS/f'v3v4_validation_final_and_dashboard_refresh_{DATE}.json')
    if rc_final.returncode!=0: warnings.append(f'after_validation_final_runner_rc_{rc_final.returncode}')
    if final_marker.get('final_validation_ran') is not True: blockers.append('final_validation_ran_not_true')
    if final_marker.get('scan_ran') is not False: blockers.append('final_pass_scan_ran')
    if final_marker.get('candidate_touched') is not False: blockers.append('final_pass_candidate_touched')
    if final_marker.get('match_date_used') is not True: blockers.append('final_match_date_not_used')
    if final_marker.get('brief_used_for_hit_rate') is not False: blockers.append('final_brief_used_for_hit_rate')
    if final_marker.get('yesterday_validation_target_date')!='20260523': blockers.append('final_target_date_not_20260523')
    if final_marker.get('refresh_status') not in ('NOOP_AFTER_VALIDATION_RERUN','UPDATED_AFTER_FINAL_VALIDATION','VALIDATION_NOT_READY_FINAL','VALIDATION_HASH_MISSING'):
        blockers.append(f"final_refresh_status_invalid:{final_marker.get('refresh_status')}")
    val=load(STATUS/f'v3v4_validation_summary_{DATE}.json')
    y=((val.get('dashboard_active') or {}).get('yesterday') or {})
    a=((y.get('A') or {}).get('display_rate') or 'N/A')
    b=((y.get('B') or {}).get('display_rate') or 'N/A')
    ab=((y.get('A_plus_B') or y.get('AB') or {}).get('display_rate') or 'N/A')
    if a=='N/A' and b=='N/A' and ab=='N/A':
        reason=((val.get('yesterday') or {}).get('reason')) or ((y.get('A_plus_B') or {}).get('reason'))
        if not reason: blockers.append('pipeline_all_na_without_reason')

    timeout_cfg=p.get('scan_timeout', {}) if isinstance(p.get('scan_timeout'), dict) else {}
    timeout_seconds=int(timeout_cfg.get('timeout_seconds') or timeout_cfg.get('recommended_timeout_seconds') or 0)
    if timeout_seconds < 1800:
        blockers.append('scan_timeout_not_1800')
    if timeout_cfg.get('boss_approval_required') is not True:
        blockers.append('scan_timeout_boss_approval_required_missing')
    code_change=p.get('code_change_required')
    if code_change is True:
        blockers.append('code_change_required_true')

    # Governance
    for k in ['cron_enabled','v2_visible','v33_visible','c_visible','last_7d_visible']:
        if p.get(k) is not False: blockers.append(f'{k}_not_false')
    if p.get('boss_approval_required') is not True: blockers.append('boss_approval_required_not_true')

    out={'checker':'tools/check_v3v4_dashboard_daily_auto_update_pipeline.py','phase':'V3V4-DASHBOARD-DYNAMIC-DATE-MARKER-AND-MATCHDATE-TZ-HOTFIX','conclusion':'PASS' if not blockers else 'BLOCKER','phase_boundary_guard':not blockers,'after_scan_time':scan.get('planned_time'),'after_validation_time':val.get('planned_time'),'after_validation_final_time':ft.get('time') if final_tasks else None,'after_scan_validation_touched':scan.get('validation_touched'),'after_validation_candidate_touched':val.get('candidate_touched'),'final_refresh_in_plan':bool(final_tasks),'final_validation_ran':final_marker.get('final_validation_ran'),'dashboard_validation_refreshed':final_marker.get('dashboard_validation_refreshed'),'final_refresh_status':final_marker.get('refresh_status'),'noop_on_same_hash':final_marker.get('refresh_status')=='NOOP_AFTER_VALIDATION_RERUN','final_pass_candidate_touched':final_marker.get('candidate_touched'),'code_change_required':code_change,'timeout_seconds':timeout_seconds,'cron_enabled':p.get('cron_enabled'),'blockers':blockers,'warnings':warnings}
    out_path=STATUS/f'check_v3v4_dashboard_daily_auto_update_pipeline_result_{DATE}.json'
    out_path.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(out,ensure_ascii=False,indent=2))
    return 0 if not blockers else 2

if __name__=='__main__': raise SystemExit(main())
