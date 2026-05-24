#!/usr/bin/env python3
"""Checker: V3/V4 dashboard daily auto update schedule — rebased 20260524.
Checks 12:00 scan + 13:00 after-scan + 13:30 after-validation + 14:00 final.
"""
from __future__ import annotations
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
STATUS=ROOT/'data/runtime/status'
PLAN=STATUS/'v3v4_dashboard_daily_auto_update_cron_plan_20260524.json'
DOC=ROOT/'docs/V3V4_DASHBOARD_DAILY_AUTO_UPDATE_CRON_PLAN_20260524.md'

def load(p):
    try: return json.loads(p.read_text(encoding='utf-8'))
    except Exception: return {}

def main():
    p=load(PLAN); blockers=[]

    schedule = p.get('schedule', []) if isinstance(p.get('schedule'), list) else []
    times = {str(x.get('time')): x for x in schedule if isinstance(x, dict)}

    # Check 12:00 scan exists
    if '12:00' not in times:
        blockers.append('scan_time_1200_missing')
    elif times.get('12:00',{}).get('task') != 'V4_DAILY_SCAN_READONLY':
        blockers.append('scan_task_wrong_at_1200')

    # Check 13:00 after-scan exists
    after_scan = [x for x in schedule if isinstance(x,dict) and x.get('task') == 'V3V4_DASHBOARD_AFTER_SCAN_REFRESH']
    if not after_scan:
        blockers.append('after_scan_task_missing')
    elif after_scan[0].get('time') != '13:00':
        blockers.append(f"after_scan_time_{after_scan[0].get('time','?').replace(':','_')}_not_1300")

    # Check 13:00 validation exists
    val_task = [x for x in schedule if isinstance(x,dict) and x.get('task') == 'V4_VALIDATION_DRY_RUN']
    if not val_task:
        blockers.append('validation_dry_run_missing')
    elif val_task[0].get('time') != '13:00':
        blockers.append(f"validation_time_{val_task[0].get('time','?').replace(':','_')}_not_1300")

    # Check 13:30 after-validation exists
    after_val = [x for x in schedule if isinstance(x,dict) and x.get('task') == 'V3V4_DASHBOARD_AFTER_VALIDATION_REFRESH']
    if not after_val:
        blockers.append('after_validation_task_missing')
    elif after_val[0].get('time') != '13:30':
        blockers.append(f"after_validation_time_{after_val[0].get('time','?').replace(':','_')}_not_1330")

    # Check 14:00 final validation + dashboard refresh exists
    final = [x for x in schedule if isinstance(x,dict) and x.get('task') == 'V4_VALIDATION_DRY_RUN_FINAL_AND_DASHBOARD_REFRESH']
    if not final:
        blockers.append('final_validation_dashboard_refresh_task_missing_at_1400')
    elif final[0].get('time') != '14:00':
        blockers.append(f"final_refresh_time_{final[0].get('time','?').replace(':','_')}_not_1400")

    # No 12:10 refresh
    if '12:10' in times:
        blockers.append('scheduled_1210_refresh_found')

    # 14:00 type check — should run final validation and then dashboard refresh,
    # but must not be a scan or candidate refresh.
    if final:
        final_type = final[0].get('type', '')
        if final_type == 'scan':
            blockers.append('final_refresh_type_is_scan')
        if final_type != 'validation-final-dashboard-refresh':
            blockers.append(f"final_refresh_type_{final_type}_not_validation_final_dashboard_refresh")
        if final[0].get('final_validation') is not True or final[0].get('dashboard_refresh') is not True:
            blockers.append('final_validation_or_dashboard_refresh_flag_missing')

    final_cfg = (p.get('tasks') or {}).get('final-validation-dashboard-refresh', {}) if isinstance(p.get('tasks'), dict) else {}
    final_cmd = str(final_cfg.get('command', ''))
    if 'run_v3v4_validation_final_and_dashboard_refresh.py' not in final_cmd:
        blockers.append('final_command_not_validation_final_runner')
    if final_cfg.get('final_validation_ran') is not True:
        blockers.append('final_validation_ran_not_true_in_plan')
    if final_cfg.get('dashboard_refresh_after_validation') is not True:
        blockers.append('dashboard_refresh_after_validation_not_true_in_plan')
    if final_cfg.get('noop_when_source_hash_unchanged') is not True:
        blockers.append('after_validation_final_noop_guard_missing')

    timeout_cfg = p.get('scan_timeout', {}) if isinstance(p.get('scan_timeout'), dict) else {}
    timeout_seconds = int(timeout_cfg.get('timeout_seconds') or timeout_cfg.get('recommended_timeout_seconds') or 0)
    if timeout_seconds < 1800:
        blockers.append('scan_timeout_not_1800')
    if timeout_cfg.get('boss_approval_required') is not True:
        blockers.append('scan_timeout_boss_approval_required_missing')

    # Governance
    if p.get('cron_enabled') is not False:
        blockers.append('cron_enabled_not_false')
    if p.get('boss_approval_required') is not True:
        blockers.append('boss_approval_required_not_true')
    if p.get('v2_visible') is not False:
        blockers.append('v2_visible_not_false')
    if p.get('v33_visible') is not False:
        blockers.append('v33_visible_not_false')
    if p.get('c_visible') is not False:
        blockers.append('c_visible_not_false')
    if p.get('last_7d_visible') is not False:
        blockers.append('last_7d_visible_not_false')

    out = {
        'checker': 'tools/check_v3v4_dashboard_daily_auto_update_schedule.py',
        'phase': 'V3V4-DASHBOARD-AUTO-REFRESH-CRON-ENABLE-PRECHECK-SCHEDULE-REBASE-20260524',
        'schedule_times': sorted(times.keys()),
        'after_scan_time': after_scan[0].get('time') if after_scan else None,
        'after_validation_time': after_val[0].get('time') if after_val else None,
        'after_validation_final_time': final[0].get('time') if final else None,
        'final_task_name': final[0].get('task') if final else None,
        'final_reruns_validation': final_cfg.get('final_validation_ran'),
        'after_validation_final_has_final_pass': False,
        'scan_timeout_current': timeout_cfg.get('current_timeout_seconds'),
        'scan_timeout_recommended': timeout_cfg.get('recommended_timeout_seconds') or timeout_cfg.get('timeout_seconds'),
        'timeout_boss_approval_required': timeout_cfg.get('boss_approval_required'),
        'cron_enabled': p.get('cron_enabled'),
        'boss_approval_required': p.get('boss_approval_required'),
        'code_change_required': p.get('code_change_required'),
        'conclusion': 'PASS' if not blockers else 'BLOCKER',
        'blockers': blockers,
    }
    out_path = STATUS / 'check_v3v4_dashboard_daily_auto_update_schedule_result_20260524.json'
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if not blockers else 2

if __name__ == '__main__':
    raise SystemExit(main())
