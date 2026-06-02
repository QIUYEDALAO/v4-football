#!/usr/bin/env python3
"""Repo active file singleton guard for V3/V4-only scope."""
from __future__ import annotations
import json, re
from datetime import datetime, timezone, timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; STATUS=ROOT/'data/runtime/status'; TZ=timezone(timedelta(hours=8)); DATE='20260523'
ALLOWED={'tools/check_v2_decommission_v3_v4_only.py','tools/check_local_v2_full_purge.py'}
PAT=re.compile(r'(^v2|check_v2|_v2_|v2_|bet_locked)',re.I)

def main():
 blockers=[]; warnings=[]; hits=[]
 for base in ['engine','tools','config']:
  root=ROOT/base
  if not root.exists(): continue
  for p in root.rglob('*'):
   if not p.is_file() or 'archive' in p.parts or '__pycache__' in p.parts: continue
   rel=str(p.relative_to(ROOT))
   if rel in ALLOWED: continue
   if PAT.search(p.name): hits.append(rel)
 if hits: blockers.append(f'active_legacy_named_files:{len(hits)}')
 v3=[ROOT/'engine/wc_model.py',ROOT/'engine/v3_config/v3_thresholds.json']
 v4=[ROOT/'engine/v4_runner.py',ROOT/'engine/v4_review_renderer.py',ROOT/'tools/build_v4_control_center_model.py']
 missing_v3=[str(p.relative_to(ROOT)) for p in v3 if not p.exists()]
 missing_v4=[str(p.relative_to(ROOT)) for p in v4 if not p.exists()]
 if missing_v3: blockers.append(f'missing_v3:{missing_v3}')
 if missing_v4: blockers.append(f'missing_v4:{missing_v4}')
 status='BLOCKER' if blockers else ('WARN_ONLY' if warnings else 'PASS')
 result={'checker':'tools/check_repo_active_file_singleton.py','phase':'V3V4-INTEL-OPS-CONSOLE-UI-REFIT-AND-V2-PURGE-CLOSEOUT-20260523','generated_at':datetime.now(TZ).isoformat(),'conclusion':status,'v2_active_files_after':len(hits),'v2_active_files_sample':hits[:20],'v3_active':not missing_v3,'v4_active':not missing_v4,'deleted_files':0,'blockers':blockers,'warnings':warnings}
 (STATUS/f'check_repo_active_file_singleton_result_{DATE}.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(result,ensure_ascii=False,indent=2)); return 1 if blockers else 0
if __name__=='__main__': raise SystemExit(main())
