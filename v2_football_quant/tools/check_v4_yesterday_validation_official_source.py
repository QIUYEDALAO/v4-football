#!/usr/bin/env python3
from __future__ import annotations
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
STATUS=ROOT/'data/runtime/status'
TZ=timezone(timedelta(hours=8)); DATE=datetime.now(TZ).strftime('%Y%m%d')
blockers=[]; d={}
paths=sorted(STATUS.glob('v3v4_validation_summary_*.json'))
P=paths[-1] if paths else None
if not P or not P.exists(): blockers.append('validation_summary_missing')
else:
 d=json.loads(P.read_text(encoding='utf-8'))
 y=((d.get('dashboard_active') or {}).get('yesterday') or {})
 if not y: blockers.append('yesterday_block_missing')
out={'checker':'tools/check_v4_yesterday_validation_official_source.py','phase':'V3V4-TEAM-CN-PERSISTENT-PIPELINE-FIX-20260525','date':DATE,'summary_path':str(P.relative_to(ROOT)) if P else None,'yesterday_label':((d.get('dashboard_active') or {}).get('yesterday') or {}).get('label') if d else None,'blockers':blockers,'conclusion':'PASS' if not blockers else 'BLOCKER'}
(STATUS/f'check_v4_yesterday_validation_official_source_result_{DATE}.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(out,ensure_ascii=False,indent=2))
raise SystemExit(0 if not blockers else 2)
