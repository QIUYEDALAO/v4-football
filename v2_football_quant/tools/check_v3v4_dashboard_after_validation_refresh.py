#!/usr/bin/env python3
from __future__ import annotations
import json, subprocess, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
STATUS=ROOT/'data/runtime/status'
RUNNER=ROOT/'tools/run_v3v4_dashboard_daily_update.py'
TZ=timezone(timedelta(hours=8))
DATE=datetime.now(TZ).strftime('%Y%m%d')


def prev_date_yyyymmdd(date_str: str) -> str:
    dt = datetime.strptime(date_str, "%Y%m%d")
    return (dt - timedelta(days=1)).strftime("%Y%m%d")

def main():
    blockers=[]; warnings=[]
    r=subprocess.run([sys.executable,str(RUNNER),'--date',DATE,'--phase','after-validation','--mode','dry-run','--no-api','--no-capture','--no-push','--no-cloud','--strict'],cwd=str(ROOT),text=True,capture_output=True,timeout=30)
    path=STATUS/f'v3v4_dashboard_daily_update_after_validation_dry_run_{DATE}.json'
    data=json.loads(path.read_text()) if path.exists() else {}
    if r.returncode!=0: blockers.append(f'after_validation_dry_run_rc_{r.returncode}')
    if data.get('date')!=DATE: blockers.append('after_validation_not_current_date')
    if data.get('candidate_touched') is not False: blockers.append('after_validation_candidate_touched')
    if data.get('brief_used_for_hit_rate') not in (False,None): blockers.append('brief_used_for_hit_rate')
    if data.get('date_filter_field') not in ('match_date', None): blockers.append('validation_not_match_date')
    expected_target = prev_date_yyyymmdd(DATE)
    if data.get('yesterday_validation_target_date') != expected_target:
        blockers.append(f'after_validation_target_date_not_{expected_target}')
    val_path=STATUS/f'v3v4_validation_summary_{DATE}.json'
    if val_path.exists():
        val=json.loads(val_path.read_text())
        y=((val.get('dashboard_active') or {}).get('yesterday') or {})
        a=((y.get('A') or {}).get('display_rate') or 'N/A')
        b=((y.get('B') or {}).get('display_rate') or 'N/A')
        ab=((y.get('A_plus_B') or y.get('AB') or {}).get('display_rate') or 'N/A')
        if a=='N/A' and b=='N/A' and ab=='N/A':
            reason=((val.get('yesterday') or {}).get('reason')) or ((y.get('A_plus_B') or {}).get('reason'))
            if not reason:
                blockers.append('after_validation_all_na_without_reason')
    if data.get('status')=='VALIDATION_NOT_READY': warnings.append('validation_not_ready')
    if '20260523' in str(data.get('validation_completion_marker')): blockers.append('stale_validation_marker_path')
    out={'checker':'tools/check_v3v4_dashboard_after_validation_refresh.py','phase':'V3V4-DASHBOARD-DYNAMIC-DATE-MARKER-AND-MATCHDATE-TZ-HOTFIX','date':DATE,'conclusion':'BLOCKER' if blockers else ('WARN_ONLY' if warnings else 'PASS'),'after_validation_time':data.get('planned_time'),'requires_validation_completed':data.get('requires_validation_completed'),'validation_ready':data.get('validation_ready'),'candidate_touched':data.get('candidate_touched'),'brief_used_for_hit_rate':data.get('brief_used_for_hit_rate'),'date_filter_field':data.get('date_filter_field'),'yesterday_validation_target_date':data.get('yesterday_validation_target_date'),'status':data.get('status'),'blockers':blockers,'warnings':warnings}
    (STATUS/f'check_v3v4_dashboard_after_validation_refresh_result_{DATE}.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(out,ensure_ascii=False,indent=2))
    return 1 if blockers else 0
if __name__=='__main__': raise SystemExit(main())
