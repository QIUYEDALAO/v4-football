#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
STATUS=ROOT/'data/runtime/status'
PLAN=STATUS/'v3v4_dashboard_daily_auto_update_cron_plan_20260523.json'
DOC=ROOT/'docs/V3V4_DASHBOARD_DAILY_AUTO_UPDATE_CRON_PLAN_20260523.md'

def load(p):
    try: return json.loads(p.read_text(encoding='utf-8'))
    except Exception: return {}

def main():
    p=load(PLAN); blockers=[]
    tasks=p.get('tasks',{}) if isinstance(p.get('tasks'),dict) else {}
    timeline=p.get('timeline',[]) if isinstance(p.get('timeline'),list) else []
    scheduled_times=[str(x.get('time')) for x in timeline if isinstance(x,dict)] + [str(v.get('planned_time')) for v in tasks.values() if isinstance(v,dict)]
    if tasks.get('after-scan',{}).get('planned_time')!='13:00': blockers.append('after_scan_time_not_1300')
    if tasks.get('after-validation',{}).get('planned_time')!='13:30': blockers.append('after_validation_time_not_1330')
    if '12:10' in scheduled_times: blockers.append('scheduled_1210_refresh_found')
    if p.get('cron_enabled') is not False: blockers.append('cron_enabled_not_false')
    if p.get('autosync_cron_created') is not False: blockers.append('autosync_cron_created_not_false')
    if p.get('boss_approval_required') is not True: blockers.append('boss_approval_required_not_true')
    if (p.get('delivery') or {}).get('mode')!='none': blockers.append('delivery_mode_not_none')
    for k in ['QQ_push','cloud_publish','capture_ran','auto_retry','auto_kill','timeout_change','brief_used_for_hit_rate','scan_date_used_for_validation']:
        if p.get(k) is not False: blockers.append(f'{k}_not_false')
    out={'checker':'tools/check_v3v4_dashboard_daily_auto_update_schedule.py','phase':'V3V4-DASHBOARD-DAILY-AUTO-UPDATE-SCHEDULE-CORRECTION-20260523','conclusion':'PASS' if not blockers else 'BLOCKER','after_scan_time':tasks.get('after-scan',{}).get('planned_time'),'after_validation_time':tasks.get('after-validation',{}).get('planned_time'),'wrong_time_guard':True,'cron_enabled':p.get('cron_enabled'),'boss_approval_required':p.get('boss_approval_required'),'scheduled_times':scheduled_times,'blockers':blockers}
    (STATUS/'check_v3v4_dashboard_daily_auto_update_schedule_result_20260523.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(out,ensure_ascii=False,indent=2)); return 0 if not blockers else 2
if __name__=='__main__': raise SystemExit(main())
