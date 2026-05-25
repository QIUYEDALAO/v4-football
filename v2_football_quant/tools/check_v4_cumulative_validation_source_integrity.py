#!/usr/bin/env python3
from __future__ import annotations
import json,re
from pathlib import Path
from datetime import datetime

ROOT=Path(__file__).resolve().parents[1]
STATUS=ROOT/'data/runtime/status'
HTML=ROOT/'data/runtime/dashboard/intel_ops_console.html'
OUT=STATUS/'check_v4_cumulative_validation_source_integrity_20260526.json'

def load(p:Path):
    try:return json.loads(p.read_text(encoding='utf-8'))
    except Exception:return {}

def main()->int:
    html=HTML.read_text(encoding='utf-8') if HTML.exists() else ''
    summary=load(STATUS/'v3v4_validation_summary_20260525.json')
    sot=load(STATUS/'v4_official_ab_validation_source_of_truth_20260525.json')
    blockers=[]; warns=[]

    # main cumulative cannot be polluted
    for tok in ['124/140','39/46','85/94','88.6%','84.8%','90.4%']:
        if tok in html:
            blockers.append(f'polluted_token_visible:{tok}')

    if 'A/B-only' not in html:
        blockers.append('ab_only_label_missing')

    # source checks
    if summary.get('schema_version')!='v3v4_validation_summary.source_of_truth.v1':
        blockers.append('summary_not_from_source_of_truth_contract')
    if not sot:
        blockers.append('source_of_truth_file_missing')

    # banned input style
    if summary.get('brief_used_for_hit_rate') is True:
        blockers.append('brief_used_for_hit_rate_true')
    if summary.get('scan_date_used_for_validation') is True:
        blockers.append('scan_date_used_for_validation_true')

    # yesterday top/footer consistency: no stale 6/10 or stale footer B2/4 when top differs
    top_y_ab='5/9 · 55.6%' in html
    footer_stale='B 2/4·50.0% AB 5/9·55.6%（全部完成）' in html
    if '6/10 · 60.0%' in html:
        blockers.append('yesterday_top_stale_6_10_visible')
    if footer_stale:
        blockers.append('stale_footer_copy_visible')
    if not top_y_ab:
        warns.append('top_yesterday_ab_not_5_9_check_source')

    # pending separated
    if '待补验' not in html:
        blockers.append('pending_counter_missing')

    # ensure official boundaries
    if summary.get('c_excluded_from_ab') is not True:
        blockers.append('c_not_excluded_from_ab')
    if summary.get('outside_57_mixed_into_official') is True:
        blockers.append('outside57_mixed_into_official')

    out={
      'checker':'tools/check_v4_cumulative_validation_source_integrity.py',
      'phase':'V4-CUMULATIVE-VALIDATION-SOURCE-POLLUTION-ROOTCAUSE-CLEANUP-20260526',
      'generated_at':datetime.now().isoformat(),
      'blockers':blockers,
      'warnings':warns,
      'conclusion':'PASS' if not blockers else 'BLOCKER',
      'full_scan_ran':False,'cloud_publish':False,'QQ_push':False,'cron_modified':False,
    }
    OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(out,ensure_ascii=False,indent=2))
    return 0 if not blockers else 2

if __name__=='__main__':
    raise SystemExit(main())
