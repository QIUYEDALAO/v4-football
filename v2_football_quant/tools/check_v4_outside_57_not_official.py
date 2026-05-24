#!/usr/bin/env python3
from __future__ import annotations
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
STATUS=ROOT/'data/runtime/status'; P=STATUS/'v4_outside_57_observation_pool_20260525.json'
TZ=timezone(timedelta(hours=8)); DATE=datetime.now(TZ).strftime('%Y%m%d')
blockers=[]
d={}
if not P.exists(): blockers.append('outside57_pool_missing')
else:
 d=json.loads(P.read_text(encoding='utf-8'))
 if d.get('official_included') is True: blockers.append('outside57_official_included_true')
out={'checker':'tools/check_v4_outside_57_not_official.py','phase':'V3V4-TEAM-CN-PERSISTENT-PIPELINE-FIX-20260525','date':DATE,'outside_57_official':bool(d.get('official_included')) if d else False,'blockers':blockers,'conclusion':'PASS' if not blockers else 'BLOCKER'}
(STATUS/f'check_v4_outside_57_not_official_result_{DATE}.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(out,ensure_ascii=False,indent=2))
raise SystemExit(0 if not blockers else 2)
