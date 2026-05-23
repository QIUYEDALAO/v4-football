#!/usr/bin/env python3
"""Cloud bundle exclusion checker for V3/V4-only current scope."""
from __future__ import annotations
import json,re
from datetime import datetime, timezone, timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; STATUS=ROOT/'data/runtime/status'; BUNDLE=ROOT/'data/runtime/cloud_publish/bundle_current'; TZ=timezone(timedelta(hours=8)); DATE='20260523'
PAT=re.compile(r'\bV2\b|v2_|BET_LOCKED|PRODUCTION_VERIFIED|\bV33\b',re.I)

def main():
 hits=[]; blockers=[]; warnings=[]
 if BUNDLE.exists():
  for p in BUNDLE.rglob('*'):
   if not p.is_file(): continue
   rel=str(p.relative_to(ROOT))
   if 'archive' in p.parts: continue
   txt=p.read_text(encoding='utf-8',errors='replace') if p.suffix.lower() in {'.html','.json','.js','.md','.txt'} else ''
   if PAT.search(p.name) or PAT.search(txt): hits.append(rel)
 if hits: blockers.append(f'cloud_bundle_legacy_active_hits:{len(hits)}')
 status='BLOCKER' if blockers else ('WARN_ONLY' if warnings else 'PASS')
 result={'checker':'tools/check_cloud_bundle_excludes_archive.py','phase':'V3V4-INTEL-OPS-CONSOLE-UI-REFIT-AND-V2-PURGE-CLOSEOUT-20260523','generated_at':datetime.now(TZ).isoformat(),'conclusion':status,'bundle_current_exists':BUNDLE.exists(),'cloud_bundle_v2_active_count':len(hits),'cloud_bundle_v2_active_sample':hits[:20],'cloud_publish':False,'reverse_sync':False,'blockers':blockers,'warnings':warnings}
 (STATUS/f'check_cloud_bundle_excludes_archive_result_{DATE}.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(result,ensure_ascii=False,indent=2)); return 1 if blockers else 0
if __name__=='__main__': raise SystemExit(main())
