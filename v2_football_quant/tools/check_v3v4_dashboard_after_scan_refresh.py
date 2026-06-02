#!/usr/bin/env python3
from __future__ import annotations
import json, subprocess, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
STATUS=ROOT/'data/runtime/status'
HTML=ROOT/'data/runtime/dashboard/intel_ops_console.html'
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
    html=HTML.read_text(encoding='utf-8',errors='replace') if HTML.exists() else ''
    b_candidates=candidate.get('B_candidates') if isinstance(candidate.get('B_candidates'),list) else []
    model_items=((model.get('candidates') or {}).get('items') or []) if isinstance(model,dict) else []
    rops_model=next((x for x in model_items if isinstance(x,dict) and str(x.get('home_en'))=='Rops' and str(x.get('away_en'))=='OLS'),{})
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
    if rops_model.get('match_display')!='罗瓦涅米RoPS vs 奥卢OLS': blockers.append(f'rops_model_match_display_missing:{rops_model.get("match_display")}')
    if rops_model.get('original_match')!='Rops vs OLS': blockers.append(f'rops_model_original_match_missing:{rops_model.get("original_match")}')
    if rops_model.get('league_display')!='芬甲 / Finland Ykkonen': blockers.append(f'rops_model_league_display_missing:{rops_model.get("league_display")}')
    if rops_model.get('grade_display')!='B级候选': blockers.append(f'rops_model_grade_display_missing:{rops_model.get("grade_display")}')
    if rops_model.get('candidate_status_display')!='待关注': blockers.append(f'rops_model_status_display_missing:{rops_model.get("candidate_status_display")}')
    if rops_model.get('market_advice_display')!='0.75 / 150': blockers.append(f'rops_model_market_advice_missing:{rops_model.get("market_advice_display")}')
    if rops_model.get('technical_audit_display')!='RF C，盘后 C': blockers.append(f'rops_model_technical_audit_missing:{rops_model.get("technical_audit_display")}')
    if rops_model.get('goal_distribution_status')!='暂无真实进球分布': blockers.append(f'rops_model_goal_distribution_status_missing:{rops_model.get("goal_distribution_status")}')
    if '数据源未返回进球时间分布' not in str(rops_model.get('goal_distribution_missing_reason')): blockers.append('rops_model_goal_distribution_reason_missing')
    if rops_model.get('data_gap_display')!='进球分布不可用': blockers.append(f'rops_model_data_gap_display_missing:{rops_model.get("data_gap_display")}')
    if int(build.get('A',-1))!=0: blockers.append(f'dashboard_build_A_not_0:{build.get("A")}')
    if int(build.get('B',-1))!=1: blockers.append(f'dashboard_build_B_not_1:{build.get("B")}')
    if int(build.get('C_deprecated_count',-1))!=0: blockers.append(f'dashboard_build_C_not_0:{build.get("C_deprecated_count")}')
    if int(build.get('scan_total',-1))!=10: blockers.append(f'dashboard_build_scan_total_not_10:{build.get("scan_total")}')
    if int(build.get('SKIP',-1))!=9: blockers.append(f'dashboard_build_SKIP_not_9:{build.get("SKIP")}')
    if 'v3v4_dashboard_candidate_view_20260602.json' not in str(build.get('candidate_source')):
        blockers.append('dashboard_build_not_using_20260602_candidate_view')
    if brief.get('fallback_used') is True and int(candidate.get('B_count',0) or 0)==0:
        blockers.append('fallback_overwrote_effective_scan_result')
    required_visible_text = [
        '对阵：罗瓦涅米RoPS vs 奥卢OLS',
        '原始队名：Rops vs OLS',
        '联赛：芬甲 / Finland Ykkonen',
        '等级：B级候选',
        '状态：待关注',
        '盘口建议：0.75 / 150',
        '技术审计：RF C，盘后 C',
        '暂无真实进球分布。',
        '原因：H2H样本不足 / 联赛长期样本不足 / 数据源未返回进球时间分布。',
        '数据缺口：进球分布不可用。',
        '不支持原因：H2H样本不足 / 联赛长期样本不足 / 数据源未返回进球时间分布。',
        '当前结论：B级待关注，不是已推送推荐。',
    ]
    for full_text in required_visible_text:
        if full_text not in html:
            blockers.append(f'html_full_text_missing:{full_text}')
    if 'B级候选' not in html or '对阵：罗瓦涅米RoPS vs 奥卢OLS' not in html: blockers.append('html_rops_b_candidate_display_missing')
    if 'A0 / B1 / SKIP9' not in html: blockers.append('html_ab_skip_counts_changed')
    if '芬甲 / Finland Ykkonen' not in html: blockers.append('html_league_cn_alias_missing')
    if '暂无真实进球分布。' not in html: blockers.append('html_goal_distribution_missing_summary_missing')
    if '数据源未返回进球时间分布' not in html: blockers.append('html_goal_distribution_missing_reason_missing')
    if '数据缺口：进球分布不可用。' not in html:
        blockers.append('html_right_decision_data_gap_not_visible_full')
    if '单场决策' not in html or '数据缺口' not in html or '不支持原因' not in html:
        blockers.append('html_single_match_decision_gap_missing')
    pos_candidate=html.find('候选列表')
    pos_validation=html.find('V3/V4 比赛验证')
    pos_decision=html.find('decision-focus-panel')
    pos_v3=html.find('V3 战备窗口')
    if not (0 <= pos_candidate < pos_validation): blockers.append('html_candidate_not_before_validation')
    if not (0 <= pos_decision < pos_v3): blockers.append('html_right_decision_not_top_before_v3')
    for hidden_or_english_label in ['Shadow解释', 'REPORT_ONLY', 'official grade', 'market evidence', 'recent5 / H2H', 'season phase', 'MARKET_STRONG_CONFIRM', 'ACTIVE_SEASON', 'TIER_3_WEAK_COVERAGE']:
        if hidden_or_english_label in html:
            blockers.append(f'html_english_label_still_visible:{hidden_or_english_label}')
    if '20260523' in (data.get('scan_completion_marker') or ''): blockers.append('stale_scan_marker_path')
    code=RUNNER.read_text(encoding='utf-8',errors='replace')
    if 'SCAN_MARKER = STATUS / "v4_scout_date_daily1200_post_repair_openclaw_verify_20260523.json"' in code: blockers.append('hardcoded_scan_marker_present')
    out={'checker':'tools/check_v3v4_dashboard_after_scan_refresh.py','phase':'V3V4-DASHBOARD-DYNAMIC-DATE-MARKER-AND-MATCHDATE-TZ-HOTFIX','date':DATE,'conclusion':'PASS' if not blockers else 'BLOCKER','after_scan_time':data.get('planned_time'),'requires_scan_completed':data.get('requires_scan_completed'),'scan_completed':data.get('scan_completed'),'brief_ready':data.get('brief_ready'),'candidate_ready':data.get('candidate_ready'),'validation_preserved':data.get('validation_preserved'),'validation_touched':data.get('validation_touched'),'result_validation_changed':data.get('result_validation_changed'),'script_validation_changed':data.get('script_validation_changed'),'status':data.get('status'),'candidate_counts':{'A':candidate.get('A_count'),'B':candidate.get('B_count'),'C':candidate.get('C_count'),'SKIP':candidate.get('SKIP_count'),'scan_total':candidate.get('scan_total')},'B_candidates':[{'fixture_id':x.get('fixture_id'),'home':x.get('home'),'away':x.get('away'),'grade':x.get('grade')} for x in b_candidates if isinstance(x,dict)],'dashboard_model_counts':{'A':model_today.get('A'),'B':model_today.get('B'),'SKIP':model_today.get('SKIP'),'scan_total':model_today.get('scan_total')},'dashboard_model_candidate_source':(model.get('data_sources') or {}).get('candidates'),'rops_model_display':{k:rops_model.get(k) for k in ['match_display','original_match','league_display','grade_display','candidate_status_display','market_advice_display','technical_audit_display','goal_distribution_status','goal_distribution_missing_reason','data_gap_display','unsupported_reason']},'dashboard_build_counts':{'A':build.get('A'),'B':build.get('B'),'C':build.get('C_deprecated_count'),'SKIP':build.get('SKIP'),'scan_total':build.get('scan_total')},'dashboard_build_candidate_source':build.get('candidate_source'),'html_display_checks':{'required_visible_text':{text:text in html for text in required_visible_text},'league_alias_visible':'芬甲 / Finland Ykkonen' in html,'goal_distribution_missing_visible':'暂无真实进球分布。' in html,'missing_reason_visible':'数据源未返回进球时间分布' in html,'right_data_gap_full_visible':'数据缺口：进球分布不可用。' in html,'candidate_before_validation':0 <= pos_candidate < pos_validation,'right_decision_before_v3':0 <= pos_decision < pos_v3},'fallback_used':candidate.get('fallback_used'),'fallback_reason':candidate.get('fallback_reason'),'fallback_overwrites_effective_scan_result':False if int(candidate.get('B_count',0) or 0)>0 else bool(candidate.get('fallback_used')),'dynamic_marker_guard':not blockers,'blockers':blockers}
    (STATUS/f'check_v3v4_dashboard_after_scan_refresh_result_{DATE}.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(out,ensure_ascii=False,indent=2))
    return 1 if blockers else 0
if __name__=='__main__': raise SystemExit(main())
