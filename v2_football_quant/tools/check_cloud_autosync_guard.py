#!/usr/bin/env python3
"""Cloud autosync guard for V3/V4-only read-only mirror."""
from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
STATUS_DIR=ROOT/'data/runtime/status'
TZ=timezone(timedelta(hours=8))
DATE='20260521'


def load(p: Path) -> dict:
    if not p.exists(): return {}
    try: return json.loads(p.read_text(encoding='utf-8'))
    except Exception: return {}


def main() -> int:
    manifest=load(STATUS_DIR/f'current_ops_manifest_{DATE}.json')
    bundle=load(STATUS_DIR/f'check_cloud_bundle_excludes_archive_result_{DATE}.json')
    blockers=[]; warnings=[]
    cloud=manifest.get('active_systems',{}).get('Cloud',{}) if manifest else {}
    if cloud.get('mode')!='readonly_mirror': blockers.append('cloud_mode_not_readonly_mirror')
    if cloud.get('reverse_sync') is not False: blockers.append('reverse_sync_not_false')
    if cloud.get('active_publish_allowed') is not False: blockers.append('active_publish_allowed_not_false')
    if bundle and bundle.get('cloud_bundle_v2_active_count',0)!=0: blockers.append('cloud_bundle_v2_active_count_not_zero')
    if not bundle: warnings.append('cloud_bundle_checker_result_missing')
    status='BLOCKER' if blockers else ('WARN_ONLY' if warnings else 'PASS')
    result={
        'checker':'tools/check_cloud_autosync_guard.py',
        'phase':'V2-DECOMMISSION-KEEP-V3-V4-ONLY-EXECUTION-20260521',
        'generated_at':datetime.now(TZ).isoformat(),
        'conclusion':status,
        'cloud_mode':cloud.get('mode'),
        'reverse_sync':cloud.get('reverse_sync'),
        'cloud_publish':False,
        'active_publish_allowed':cloud.get('active_publish_allowed'),
        'cloud_bundle_v2_active_count':bundle.get('cloud_bundle_v2_active_count') if bundle else None,
        'capture_ran':False,
        'qq_push':False,
        'cron_enabled':False,
        'blockers':blockers,
        'warnings':warnings,
    }
    out=STATUS_DIR/f'check_cloud_autosync_guard_result_{DATE}.json'
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 1 if blockers else 0

if __name__=='__main__':
    raise SystemExit(main())
