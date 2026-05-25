#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime
ROOT=Path(__file__).resolve().parents[1]
STATUS=ROOT/'data/runtime/status'
p=STATUS/'v4_yesterday_result_validation_bounded_rerun_20260526.json'
out=STATUS/'check_v4_yesterday_official_validation_bounded_rerun_20260526.json'
block=[]
if not p.exists():
 block.append('bounded_rerun_result_missing')
 d={}
else:
 d=json.loads(p.read_text())
 if int(d.get('a_settled',0))<=0 and int(d.get('b_settled',0))<=0:
  block.append('no_settled_ab_rows')
 if d.get('source')!='API-SPORTS direct v3 fixtures?id=X':
  block.append('unexpected_source')
res={'checker':'tools/check_v4_yesterday_official_validation_bounded_rerun.py','generated_at':datetime.now().isoformat(),'result_path':str(p.relative_to(ROOT)),'blockers':block,'conclusion':'PASS' if not block else 'BLOCKER'}
out.write_text(json.dumps(res,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(res,ensure_ascii=False,indent=2))
raise SystemExit(0 if not block else 2)
