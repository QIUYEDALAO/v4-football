#!/usr/bin/env python3
from __future__ import annotations
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
STATUS=ROOT/'data/runtime/status'
DASH=ROOT/'data/runtime/dashboard/outside_57_observation.html'
TZ=timezone(timedelta(hours=8)); DATE=datetime.now(TZ).strftime('%Y%m%d')
html=DASH.read_text(encoding='utf-8',errors='replace') if DASH.exists() else ''
blockers=[]
if not DASH.exists(): blockers.append('outside57_html_missing')
for tok in ['57联赛外观察池','非正式推荐','不自动下注','不进QQ']:
    if tok not in html: blockers.append(f'missing_token:{tok}')
out={'checker':'tools/check_v4_outside_57_web_observation_page.py','phase':'V3V4-TEAM-CN-PERSISTENT-PIPELINE-FIX-20260525','date':DATE,'outside_57_html_exists':DASH.exists(),'blockers':blockers,'conclusion':'PASS' if not blockers else 'BLOCKER'}
(STATUS/f'check_v4_outside_57_web_observation_page_result_{DATE}.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(out,ensure_ascii=False,indent=2))
raise SystemExit(0 if not blockers else 2)
