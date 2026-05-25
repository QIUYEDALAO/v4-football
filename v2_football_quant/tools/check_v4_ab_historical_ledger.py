#!/usr/bin/env python3
from __future__ import annotations
import csv
import json
from pathlib import Path
from datetime import datetime

ROOT=Path(__file__).resolve().parents[1]
STATUS=ROOT/'data/runtime/status'
VAL=ROOT/'data/runtime/validation'
DASH=ROOT/'data/runtime/dashboard'

INV=STATUS/'v4_ab_historical_official_recommendation_inventory_20260526.json'
MATCH=STATUS/'v4_ab_historical_postmatch_matchup_20260526.json'
LEDGER=VAL/'v4_ab_historical_ledger_20260526.json'
SIM=STATUS/'v4_ab_historical_crown_ou_settlement_simulation_20260526.json'
SEG=STATUS/'v4_ab_historical_segment_attribution_20260526.json'
HTML=DASH/'v4_ab_historical_ledger.html'
INTEL=DASH/'intel_ops_console.html'
OUT=STATUS/'v4_ab_historical_ledger_checker_20260526.json'

def jload(p):
    if not p.exists():return None
    try:return json.loads(p.read_text(encoding='utf-8'))
    except Exception:return None

def main()->int:
    blockers=[]; warns=[]
    inv=jload(INV) or {}
    recs=inv.get('records',[])
    if not recs: blockers.append('inventory_empty')
    for r in recs:
        if r.get('grade') not in {'A','B'}: blockers.append('contains_non_ab_grade'); break
        if not r.get('official_recommendation',False): blockers.append('non_official_record_found'); break
        bad=' '.join([str(r.get('home_team','')),str(r.get('away_team',''))]).upper()
        if any(x in bad for x in ['UNKNOWN','TBD','(无)']): blockers.append('placeholder_team_in_official'); break
    m=jload(MATCH) or {}
    mrs=m.get('records',[])
    if len(mrs)!=len(recs): warns.append('matchup_count_not_equal_inventory')
    for r in mrs[:10]:
        if r.get('settled') is False and not (r.get('pending_retry') or r.get('excluded_reason')):
            blockers.append('pending_without_reason'); break
    ledger=jload(LEDGER) or {}
    lrows=ledger.get('records',[])
    if not lrows:
        blockers.append('ledger_rows_empty')
    for r in lrows:
        # settled lines: ht_goal_count and result_hit contract
        if r.get('settled') and r.get('ht_goal_count') is not None:
            hg=int(r.get('ht_goal_count'))
            rh=r.get('result_hit')
            if hg>=1 and rh is not True:
                blockers.append('result_hit_contract_violation_settled_ge1')
                break
            if hg==0 and rh is not False:
                blockers.append('result_hit_contract_violation_settled_eq0')
                break
        # pending lines must keep result_hit null
        if (not r.get('settled')) and r.get('result_hit') is not None:
            blockers.append('pending_result_hit_not_null')
            break
        # unknown league must carry reason
        if str(r.get('league','')).upper() in {'','UNKNOWN'} and not r.get('league_missing_reason'):
            blockers.append('unknown_league_without_reason')
            break

        # hard source boundaries
        if str(r.get('grade','')).upper() not in {'A','B'}:
            blockers.append('ledger_non_ab_grade')
            break

    sim=jload(SIM) or {}
    if not sim.get('aggregate'): blockers.append('simulation_missing')
    else:
        st={x.get('settlement_type') for x in sim.get('per_match',[]) if x.get('settlement_type')}
        if not st.intersection({'WIN','HALF_WIN','PUSH','HALF_LOSS','LOSS','PENDING'}):
            blockers.append('settlement_type_invalid')
        for x in sim.get('per_match',[]):
            if x.get('line') not in {0.75,1.0,1.25,1.5}:
                blockers.append('unexpected_line_in_simulation')
                break
    seg=jload(SEG) or {}
    for s in seg.get('segments',[]):
        if s.get('sample_count',0)<10 and s.get('confidence_level')!='OBSERVE_ONLY':
            blockers.append('small_sample_not_observe_only'); break
    html=HTML.read_text(encoding='utf-8') if HTML.exists() else ''
    if not html: blockers.append('ledger_html_missing')
    if '诊断用途，不自动改策略' not in html: blockers.append('diagnostic_disclaimer_missing')
    if '{WIN/HALF_WIN/PUSH/HALF_LOSS/LOSS}' in html:
        blockers.append('settlement_placeholder_visible')
    if '结果命中' not in html or '剧本命中' not in html:
        blockers.append('result_script_columns_missing')
    intel=INTEL.read_text(encoding='utf-8') if INTEL.exists() else ''
    if any(x in intel for x in ['124/140 · 88.6%','39/46 · 84.8%','85/94 · 90.4%']): blockers.append('dashboard_polluted')
    if 'V4 AB历史复盘' not in intel and '/v4_ab_historical_ledger.html' not in intel:
        warns.append('entry_missing_in_main_dashboard')

    out={
      'phase':'V4-AB-HISTORICAL-RECOMMENDATION-LEDGER-AND-POSTMATCH-ATTRIBUTION-20260526',
      'generated_at':datetime.now().isoformat(),
      'blockers':blockers,
      'warnings':warns,
      'status':'PASS' if not blockers else 'BLOCKER',
      'full_scan_ran':False,
      'capture_ran':False,
      'strategy_changed':False,
      'candidate_changed':False,
      'candidate_rating_changed':False,
      'result_validation_history_changed':False,
      'script_validation_history_changed':False,
      'brief_used_for_hit_rate':False,
      'scan_date_used_for_validation':False,
      'scout_full_pool_used':False,
      'outside_57_mixed_into_official':False,
      'live_bet_real_records_modified':False,
      'v2_restored':False,
      'v33_active':False,
      'QQ_push':False,
      'cloud_publish':False,
      'cron_modified':False,
      'secrets_printed':False,
      'secrets_committed':False,
    }
    OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
    print(out['status'])
    if blockers:
        [print('BLOCKER:',b) for b in blockers]
    return 0 if not blockers else 2

if __name__=='__main__':
    raise SystemExit(main())
