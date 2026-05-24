#!/usr/bin/env python3
from __future__ import annotations
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
STATUS=ROOT/'data/runtime/status'
HTML=ROOT/'data/runtime/dashboard/intel_ops_console.html'
TZ=timezone(timedelta(hours=8))
DATE=datetime.now(TZ).strftime('%Y%m%d')


def load(p:Path)->dict:
    try: return json.loads(p.read_text(encoding='utf-8'))
    except Exception: return {}


def main()->int:
    blockers=[]; warnings=[]
    text=HTML.read_text(encoding='utf-8',errors='replace') if HTML.exists() else ''
    if not HTML.exists(): blockers.append('dashboard_html_missing')
    for token,name in [('昨日验证','yesterday_block_missing'),('累计验证','cumulative_block_missing'),('剧本验证（辅助）','script_block_missing')]:
        if token not in text: blockers.append(name)

    val=load(STATUS/f'v3v4_validation_summary_{DATE}.json')
    if val.get('brief_used_for_hit_rate') is not False: blockers.append('brief_used_for_hit_rate')
    if val.get('date_filter_field') not in ('match_date',None): blockers.append('date_filter_not_match_date')
    if val.get('yesterday_validation_target_date')!='20260523': blockers.append('yesterday_target_not_20260523')
    y=((val.get('dashboard_active') or {}).get('yesterday') or {})
    a=((y.get('A') or {}).get('display_rate') or 'N/A')
    b=((y.get('B') or {}).get('display_rate') or 'N/A')
    ab=((y.get('A_plus_B') or y.get('AB') or {}).get('display_rate') or 'N/A')
    na_all = (a=='N/A' and b=='N/A' and ab=='N/A')
    reason=((val.get('yesterday') or {}).get('reason')) or ((y.get('A_plus_B') or {}).get('reason')) or ''
    if na_all and not reason:
        if 'validation-empty-reason' not in text:
            blockers.append('all_na_without_reason')
    # If trusted rows exist for target_date, all N/A must be blocked.
    truth=load(STATUS/f'v3v4_yesterday_validation_source_truth_audit_20260524.json')
    trusted_ab=int(truth.get('trusted_AB_records_for_20260523') or 0)
    if trusted_ab>0 and na_all:
        blockers.append('trusted_rows_exist_but_all_na')

    if 'validation-yesterday' not in text and '昨日验证' in text:
        warnings.append('yesterday_css_hook_missing')

    out={
      'checker':'tools/check_v3v4_dashboard_yesterday_validation_visible.py',
      'phase':'V3V4-DASHBOARD-YESTERDAY-VALIDATION-VISIBILITY-HOTFIX-20260524',
      'date':DATE,
      'yesterday_validation_visible':'昨日验证' in text,
      'cumulative_validation_visible':'累计验证' in text,
      'script_validation_visible':'剧本验证（辅助）' in text,
      'brief_used_for_hit_rate':val.get('brief_used_for_hit_rate'),
      'scan_date_used_for_validation':val.get('date_filter_field')=='scan_date',
      'yesterday_validation_target_date':val.get('yesterday_validation_target_date'),
      'trusted_AB_records_for_target_date':trusted_ab,
      'all_na':na_all,
      'na_reason':reason,
      'blockers':blockers,
      'warnings':warnings,
      'conclusion':'BLOCKER' if blockers else ('WARN_ONLY' if warnings else 'PASS')
    }
    (STATUS/f'check_v3v4_dashboard_yesterday_validation_visible_result_{DATE}.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(out,ensure_ascii=False,indent=2))
    return 0 if not blockers else 2


if __name__=='__main__':
    raise SystemExit(main())
