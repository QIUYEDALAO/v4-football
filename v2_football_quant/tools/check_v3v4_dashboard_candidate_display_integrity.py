#!/usr/bin/env python3
from __future__ import annotations
import json,re
from pathlib import Path
from datetime import datetime

ROOT=Path(__file__).resolve().parents[1]
STATUS=ROOT/'data/runtime/status'
HTML=ROOT/'data/runtime/dashboard/intel_ops_console.html'
CV=STATUS/'v3v4_dashboard_candidate_view_20260525.json'
OUT=STATUS/'check_v3v4_dashboard_candidate_display_integrity_20260526.json'

def load(p:Path):
    try:return json.loads(p.read_text(encoding='utf-8'))
    except Exception:return {}

def main()->int:
    blockers=[]; warns=[]
    html=HTML.read_text(encoding='utf-8') if HTML.exists() else ''
    cv=load(CV)

    mh=re.search(r'A/B/SKIP</span><b>A(\d+)\s*/\s*B(\d+)\s*/\s*SKIP(\d+)</b>',html)
    ma=re.search(r"A级候选</span><b>(\d+) 场</b>",html)
    mb=re.search(r"B级候选</span><b>(\d+) 场</b>",html)
    top_a=int(mh.group(1)) if mh else None
    top_b=int(mh.group(2)) if mh else None
    sec_a=int(ma.group(1)) if ma else None
    sec_b=int(mb.group(1)) if mb else None

    if top_a is None or top_b is None or sec_a is None or sec_b is None:
        blockers.append('candidate_count_parse_failed')
    else:
        if top_a!=sec_a: blockers.append('top_A_count_mismatch_section')
        if top_b!=sec_b: blockers.append('top_B_count_mismatch_section')

    # B=0 => no B card rows
    if top_b==0 and sec_b!=0:
        blockers.append('B_zero_but_B_section_has_cards')

    # UNKNOWN/TBD/(无) placeholders cannot appear in official A/B cards
    for tok in ['：(无) <span>vs</span> UNKNOWN','主信息字段待正式源补齐','time_bins 待补齐']:
        if tok in html:
            blockers.append(f'placeholder_visible:{tok}')

    # no missing-prefix in active titles
    if '中文名缺失：' in html:
        blockers.append('team_cn_missing_prefix_visible')

    # yesterday N/A cannot be validation success
    if '昨日验证' in html and 'N/A' in html and '不代表验证链路成功' not in html:
        blockers.append('na_without_non_success_disclaimer')

    # cumulative must be AB-only and no 124/140
    if not all(t in html for t in ['25/41 · 61.0%','50/89 · 56.2%','75/130 · 57.7%','A/B-only · 不含C']):
        blockers.append('ab_only_cumulative_signature_missing')
    if '124/140 · 88.6%' in html or '140 · 88.6%' in html:
        blockers.append('legacy_124_140_reflowed')

    # outside57 should not mix into official
    if 'outside_57' in html and '当前不参与 V4 A/B 正式候选' not in html:
        warns.append('outside57_token_present_verify_official_boundary')

    # fixed constraints
    if cv.get('brief_used_for_hit_rate') is True:
        blockers.append('brief_used_for_hit_rate_true')

    out={
      'checker':'tools/check_v3v4_dashboard_candidate_display_integrity.py',
      'phase':'V3V4-DASHBOARD-CANDIDATE-DISPLAY-INTEGRITY-AND-VALIDATION-NA-FIX-20260526',
      'generated_at':datetime.now().isoformat(),
      'top_counts':{'A':top_a,'B':top_b},
      'section_counts':{'A':sec_a,'B':sec_b},
      'blockers':blockers,
      'warnings':warns,
      'conclusion':'PASS' if not blockers else 'BLOCKER',
      'strategy_changed':False,
      'candidate_changed':False,
      'validation_recomputed':False,
      'full_scan_ran':False,
      'QQ_push':False,
      'cloud_publish':False,
      'cron_modified':False,
    }
    OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
    print(out['conclusion'])
    if blockers:
      [print('BLOCKER:',b) for b in blockers]
    return 0 if not blockers else 2

if __name__=='__main__':
    raise SystemExit(main())
