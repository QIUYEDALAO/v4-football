#!/usr/bin/env python3
from __future__ import annotations
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
STATUS=ROOT/'data/runtime/status'
TZ=timezone(timedelta(hours=8))
DATE=datetime.now(TZ).strftime('%Y%m%d')


def load(p:Path)->dict:
    try: return json.loads(p.read_text(encoding='utf-8'))
    except Exception: return {}


def main()->int:
    blockers=[]; warnings=[]
    truth=load(STATUS/'v3v4_yesterday_validation_source_truth_audit_20260524.json')
    val=load(STATUS/f'v3v4_validation_summary_{DATE}.json')

    target=truth.get('target_date') or val.get('yesterday_validation_target_date')
    if target!='20260523': blockers.append('target_date_not_20260523')

    y=((val.get('dashboard_active') or {}).get('yesterday') or {})
    a=((y.get('A') or {}).get('display_rate') or 'N/A')
    b=((y.get('B') or {}).get('display_rate') or 'N/A')
    ab=((y.get('A_plus_B') or y.get('AB') or {}).get('display_rate') or 'N/A')
    all_na=(a=='N/A' and b=='N/A' and ab=='N/A')
    trusted_ab=int(truth.get('trusted_AB_records_for_20260523') or 0)

    reason=((val.get('yesterday') or {}).get('reason')) or ((y.get('A_plus_B') or {}).get('reason')) or truth.get('n_a_reason_current')

    if trusted_ab>0 and all_na:
        blockers.append('trusted_ab_gt_0_but_dashboard_all_na')
    if trusted_ab==0 and all_na and not reason:
        blockers.append('all_na_without_reason_when_no_trusted_sample')

    if val.get('brief_used_for_hit_rate') is not False:
        blockers.append('brief_used_for_hit_rate')
    if val.get('date_filter_field') not in ('match_date',None):
        blockers.append('scan_date_used_for_validation')

    out={
      'checker':'tools/check_v3v4_dashboard_yesterday_validation_data.py',
      'phase':'V3V4-YESTERDAY-VALIDATION-DATA-RECOVERY-HOTFIX-20260524',
      'date':DATE,
      'target_date':target,
      'trusted_AB_records':trusted_ab,
      'dashboard_A':a,
      'dashboard_B':b,
      'dashboard_AB':ab,
      'all_na':all_na,
      'na_reason':reason,
      'data_guard': trusted_ab==0 or not all_na,
      'no_unexplained_na_guard': (not all_na) or bool(reason),
      'blockers':blockers,
      'warnings':warnings,
      'conclusion':'BLOCKER' if blockers else ('WARN_ONLY' if warnings else 'PASS')
    }
    (STATUS/f'check_v3v4_dashboard_yesterday_validation_data_result_{DATE}.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(out,ensure_ascii=False,indent=2))
    return 0 if not blockers else 2


if __name__=='__main__':
    raise SystemExit(main())
