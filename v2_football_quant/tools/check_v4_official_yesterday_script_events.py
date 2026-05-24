#!/usr/bin/env python3
from __future__ import annotations
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
STATUS=ROOT/'data/runtime/status'; P=STATUS/'v4_script_validation_summary_20260524.json'
TZ=timezone(timedelta(hours=8)); DATE=datetime.now(TZ).strftime('%Y%m%d')
blockers=[]; d={}
if not P.exists(): blockers.append('script_validation_summary_missing')
else:
 d=json.loads(P.read_text(encoding='utf-8'))
 if d.get('date_filter_field')!='match_date': blockers.append('script_not_match_date')
 if d.get('brief_used_for_script_validation') is not False: blockers.append('brief_used_for_script_validation')
out={'checker':'tools/check_v4_official_yesterday_script_events.py','phase':'V3V4-TEAM-CN-PERSISTENT-PIPELINE-FIX-20260525','date':DATE,'date_filter_field':d.get('date_filter_field') if d else None,'brief_used_for_script_validation':d.get('brief_used_for_script_validation') if d else None,'blockers':blockers,'conclusion':'PASS' if not blockers else 'BLOCKER'}
(STATUS/f'check_v4_official_yesterday_script_events_result_{DATE}.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(out,ensure_ascii=False,indent=2))
raise SystemExit(0 if not blockers else 2)
