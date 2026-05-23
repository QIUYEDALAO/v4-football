#!/usr/bin/env python3
"""OpenClaw active source manifest checker for V3/V4-only scope."""
from __future__ import annotations
import json,re
from datetime import datetime, timezone, timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; STATUS=ROOT/'data/runtime/status'; TZ=timezone(timedelta(hours=8)); DATE='20260523'

def load(p):
 if not p.exists(): return {}
 try: return json.loads(p.read_text(encoding='utf-8'))
 except Exception: return {}

def active_text(m):
 parts=[]
 for d in m.get('active_systems',{}).values():
  if isinstance(d,dict):
   for k in ['active_sources','allowed_tasks','entrypoint','review_mode']:
    v=d.get(k)
    if isinstance(v,list): parts.extend(map(str,v))
    elif v is not None: parts.append(str(v))
 return '\n'.join(parts)

def main():
 m=load(STATUS/'current_ops_manifest_20260521.json') or load(STATUS/'current_ops_manifest_v3_v4_only_20260521.json')
 text=active_text(m); blockers=[]; warnings=[]
 v2=bool(re.search(r'\bv2\b|bet_locked',text,re.I)); v33=bool(re.search(r'\bv33\b',text,re.I))
 v3=bool(m.get('active_systems',{}).get('V3',{}).get('active_sources'))
 v4=bool(m.get('active_systems',{}).get('V4',{}).get('active_sources'))
 grades=m.get('active_systems',{}).get('V4',{}).get('allowed_grades')
 mode=m.get('active_systems',{}).get('V4',{}).get('review_mode')
 if not m: blockers.append('manifest_missing')
 if v2: blockers.append('v2_active_in_manifest')
 if v33: blockers.append('v33_active_in_manifest')
 if not v3: blockers.append('v3_missing')
 if not v4: blockers.append('v4_missing')
 if grades!=['A','B','C','SKIP']: blockers.append(f'v4_grades_mismatch:{grades}')
 if mode!='REPORT_ONLY': blockers.append(f'v4_review_mode_not_report_only:{mode}')
 status='BLOCKER' if blockers else ('WARN_ONLY' if warnings else 'PASS')
 result={'checker':'tools/check_openclaw_active_source_manifest.py','phase':'V3V4-INTEL-OPS-CONSOLE-UI-REFIT-AND-V2-PURGE-CLOSEOUT-20260523','generated_at':datetime.now(TZ).isoformat(),'conclusion':status,'v2_active_in_manifest':v2,'v3_active':v3,'v4_active':v4,'v33_active':v33,'v4_allowed_grades':grades,'v4_review_mode':mode,'blockers':blockers,'warnings':warnings}
 (STATUS/f'check_openclaw_active_source_manifest_result_{DATE}.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(result,ensure_ascii=False,indent=2)); return 1 if blockers else 0
if __name__=='__main__': raise SystemExit(main())
