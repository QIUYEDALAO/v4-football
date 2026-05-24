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

def main():
    blockers=[]
    r=subprocess.run([sys.executable,str(RUNNER),'--date',DATE,'--phase','after-scan','--mode','dry-run','--no-api','--no-capture','--no-push','--no-cloud','--strict'],cwd=str(ROOT),text=True,capture_output=True,timeout=30)
    data=json.loads((STATUS/f'v3v4_dashboard_daily_update_after_scan_dry_run_{DATE}.json').read_text()) if (STATUS/f'v3v4_dashboard_daily_update_after_scan_dry_run_{DATE}.json').exists() else {}
    if r.returncode!=0: blockers.append(f'after_scan_dry_run_rc_{r.returncode}')
    if data.get('date')!=DATE: blockers.append('after_scan_not_current_date')
    if data.get('status')=='SCAN_NOT_READY': blockers.append('after_scan_scan_not_ready')
    if data.get('brief_ready') is not True: blockers.append('brief_not_ready')
    if data.get('candidate_ready') is not True: blockers.append('candidate_not_ready')
    if data.get('validation_touched') is not False: blockers.append('after_scan_validation_touched')
    if data.get('validation_preserved') is not True: blockers.append('after_scan_validation_not_preserved')
    if data.get('result_validation_changed') not in (False, None): blockers.append('after_scan_result_validation_changed')
    if data.get('script_validation_changed') not in (False, None): blockers.append('after_scan_script_validation_changed')
    if '20260523' in (data.get('scan_completion_marker') or ''): blockers.append('stale_scan_marker_path')
    code=RUNNER.read_text(encoding='utf-8',errors='replace')
    if 'SCAN_MARKER = STATUS / "v4_scout_date_daily1200_post_repair_openclaw_verify_20260523.json"' in code: blockers.append('hardcoded_scan_marker_present')
    out={'checker':'tools/check_v3v4_dashboard_after_scan_refresh.py','phase':'V3V4-DASHBOARD-DYNAMIC-DATE-MARKER-AND-MATCHDATE-TZ-HOTFIX','date':DATE,'conclusion':'PASS' if not blockers else 'BLOCKER','after_scan_time':data.get('planned_time'),'requires_scan_completed':data.get('requires_scan_completed'),'scan_completed':data.get('scan_completed'),'brief_ready':data.get('brief_ready'),'candidate_ready':data.get('candidate_ready'),'validation_preserved':data.get('validation_preserved'),'validation_touched':data.get('validation_touched'),'result_validation_changed':data.get('result_validation_changed'),'script_validation_changed':data.get('script_validation_changed'),'status':data.get('status'),'dynamic_marker_guard':not blockers,'blockers':blockers}
    (STATUS/f'check_v3v4_dashboard_after_scan_refresh_result_{DATE}.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(out,ensure_ascii=False,indent=2))
    return 1 if blockers else 0
if __name__=='__main__': raise SystemExit(main())
