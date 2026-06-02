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
    candidate=json.loads((STATUS/f'v3v4_dashboard_candidate_view_{DATE}.json').read_text()) if (STATUS/f'v3v4_dashboard_candidate_view_{DATE}.json').exists() else {}
    build=json.loads((STATUS/f'v3v4_dashboard_brief_validation_auto_refresh_build_{DATE}.json').read_text()) if (STATUS/f'v3v4_dashboard_brief_validation_auto_refresh_build_{DATE}.json').exists() else {}
    brief=json.loads((STATUS/f'v3v4_dashboard_brief_resolution_{DATE}.json').read_text()) if (STATUS/f'v3v4_dashboard_brief_resolution_{DATE}.json').exists() else {}
    model=json.loads((STATUS/f'v4_control_center_model_{DATE}.json').read_text()) if (STATUS/f'v4_control_center_model_{DATE}.json').exists() else {}
    model_today=((model.get('top_status') or {}).get('today_candidates') or {}) if isinstance(model,dict) else {}
    b_candidates=candidate.get('B_candidates') if isinstance(candidate.get('B_candidates'),list) else []
    if r.returncode!=0: blockers.append(f'after_scan_dry_run_rc_{r.returncode}')
    if data.get('date')!=DATE: blockers.append('after_scan_not_current_date')
    if data.get('status')=='SCAN_NOT_READY': blockers.append('after_scan_scan_not_ready')
    if data.get('brief_ready') is not True: blockers.append('brief_not_ready')
    if data.get('candidate_ready') is not True: blockers.append('candidate_not_ready')
    if data.get('validation_touched') is not False: blockers.append('after_scan_validation_touched')
    if data.get('validation_preserved') is not True: blockers.append('after_scan_validation_not_preserved')
    if data.get('result_validation_changed') not in (False, None): blockers.append('after_scan_result_validation_changed')
    if data.get('script_validation_changed') not in (False, None): blockers.append('after_scan_script_validation_changed')
    if int(candidate.get('B_count',-1))!=1: blockers.append(f'candidate_B_not_1:{candidate.get("B_count")}')
    if int(candidate.get('A_count',-1))!=0: blockers.append(f'candidate_A_not_0:{candidate.get("A_count")}')
    if int(candidate.get('C_count',-1))!=0: blockers.append(f'candidate_C_not_0:{candidate.get("C_count")}')
    if not any(str(x.get('home'))=='Rops' and str(x.get('away'))=='OLS' and str(x.get('grade'))=='B' for x in b_candidates if isinstance(x,dict)):
        blockers.append('rops_vs_ols_missing_from_B_candidates')
    if int(candidate.get('scan_total',-1))!=10: blockers.append(f'candidate_scan_total_not_10:{candidate.get("scan_total")}')
    if int(candidate.get('SKIP_count',-1))!=9: blockers.append(f'candidate_SKIP_not_9:{candidate.get("SKIP_count")}')
    if int(model_today.get('A',-1))!=0: blockers.append(f'dashboard_model_A_not_0:{model_today.get("A")}')
    if int(model_today.get('B',-1))!=1: blockers.append(f'dashboard_model_B_not_1:{model_today.get("B")}')
    if int(model_today.get('SKIP',-1))!=9: blockers.append(f'dashboard_model_SKIP_not_9:{model_today.get("SKIP")}')
    if int(model_today.get('scan_total',-1))!=10: blockers.append(f'dashboard_model_scan_total_not_10:{model_today.get("scan_total")}')
    if 'v3v4_dashboard_candidate_view_20260602.json' not in str(((model.get('data_sources') or {}).get('candidates'))):
        blockers.append('dashboard_model_not_using_20260602_candidate_view')
    if int(build.get('A',-1))!=0: blockers.append(f'dashboard_build_A_not_0:{build.get("A")}')
    if int(build.get('B',-1))!=1: blockers.append(f'dashboard_build_B_not_1:{build.get("B")}')
    if int(build.get('C_deprecated_count',-1))!=0: blockers.append(f'dashboard_build_C_not_0:{build.get("C_deprecated_count")}')
    if int(build.get('scan_total',-1))!=10: blockers.append(f'dashboard_build_scan_total_not_10:{build.get("scan_total")}')
    if int(build.get('SKIP',-1))!=9: blockers.append(f'dashboard_build_SKIP_not_9:{build.get("SKIP")}')
    if 'v3v4_dashboard_candidate_view_20260602.json' not in str(build.get('candidate_source')):
        blockers.append('dashboard_build_not_using_20260602_candidate_view')
    if brief.get('fallback_used') is True and int(candidate.get('B_count',0) or 0)==0:
        blockers.append('fallback_overwrote_effective_scan_result')
    if '20260523' in (data.get('scan_completion_marker') or ''): blockers.append('stale_scan_marker_path')
    code=RUNNER.read_text(encoding='utf-8',errors='replace')
    if 'SCAN_MARKER = STATUS / "v4_scout_date_daily1200_post_repair_openclaw_verify_20260523.json"' in code: blockers.append('hardcoded_scan_marker_present')
    out={'checker':'tools/check_v3v4_dashboard_after_scan_refresh.py','phase':'V3V4-DASHBOARD-DYNAMIC-DATE-MARKER-AND-MATCHDATE-TZ-HOTFIX','date':DATE,'conclusion':'PASS' if not blockers else 'BLOCKER','after_scan_time':data.get('planned_time'),'requires_scan_completed':data.get('requires_scan_completed'),'scan_completed':data.get('scan_completed'),'brief_ready':data.get('brief_ready'),'candidate_ready':data.get('candidate_ready'),'validation_preserved':data.get('validation_preserved'),'validation_touched':data.get('validation_touched'),'result_validation_changed':data.get('result_validation_changed'),'script_validation_changed':data.get('script_validation_changed'),'status':data.get('status'),'candidate_counts':{'A':candidate.get('A_count'),'B':candidate.get('B_count'),'C':candidate.get('C_count'),'SKIP':candidate.get('SKIP_count'),'scan_total':candidate.get('scan_total')},'B_candidates':[{'fixture_id':x.get('fixture_id'),'home':x.get('home'),'away':x.get('away'),'grade':x.get('grade')} for x in b_candidates if isinstance(x,dict)],'dashboard_model_counts':{'A':model_today.get('A'),'B':model_today.get('B'),'SKIP':model_today.get('SKIP'),'scan_total':model_today.get('scan_total')},'dashboard_model_candidate_source':(model.get('data_sources') or {}).get('candidates'),'dashboard_build_counts':{'A':build.get('A'),'B':build.get('B'),'C':build.get('C_deprecated_count'),'SKIP':build.get('SKIP'),'scan_total':build.get('scan_total')},'dashboard_build_candidate_source':build.get('candidate_source'),'fallback_used':candidate.get('fallback_used'),'fallback_reason':candidate.get('fallback_reason'),'fallback_overwrites_effective_scan_result':False if int(candidate.get('B_count',0) or 0)>0 else bool(candidate.get('fallback_used')),'dynamic_marker_guard':not blockers,'blockers':blockers}
    (STATUS/f'check_v3v4_dashboard_after_scan_refresh_result_{DATE}.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(out,ensure_ascii=False,indent=2))
    return 1 if blockers else 0
if __name__=='__main__': raise SystemExit(main())
