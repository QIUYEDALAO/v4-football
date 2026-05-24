#!/usr/bin/env python3
from __future__ import annotations
import json, re, subprocess, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
STATUS=ROOT/'data/runtime/status'
TZ=timezone(timedelta(hours=8))
DATE=datetime.now(TZ).strftime('%Y%m%d')
ACTIVE_FILES=[
 ROOT/'tools/run_v3v4_dashboard_daily_update.py',
 ROOT/'tools/run_v3v4_validation_final_and_dashboard_refresh.py',
 ROOT/'tools/v3v4_dashboard_brief_resolver.py',
 ROOT/'tools/build_v3v4_dashboard_markers_from_scan_outputs.py',
]
BAD_PATTERNS=[
 r'v3v4_dashboard_brief_resolution_20260523',
 r'v3v4_dashboard_candidate_view_20260523',
 r'v4_scout_date_daily1200_post_repair_openclaw_verify_20260523',
 r'v3v4_validation_summary_20260523',
 r'v4_match_date_validation_history_recovery_20260523',
 r'DATE_KEY = "20260523"',
]

def main():
    blockers=[]; hits=[]
    for path in ACTIVE_FILES:
        text=path.read_text(encoding='utf-8',errors='replace') if path.exists() else ''
        for pat in BAD_PATTERNS:
            for m in re.finditer(pat,text):
                line=text.count('\n',0,m.start())+1
                hits.append({'file':str(path.relative_to(ROOT)),'line':line,'pattern':pat})
    if hits: blockers.append('active_hardcoded_stale_marker_dates')
    # Runner must rebuild markers from same-date formal outputs when missing.
    runner=(ROOT/'tools/run_v3v4_dashboard_daily_update.py').read_text(encoding='utf-8',errors='replace')
    if 'ensure_scan_markers' not in runner or 'resolve_brief(date, write=True)' not in runner:
        blockers.append('missing_marker_rebuild_path')
    proc=subprocess.run([sys.executable,str(ROOT/'tools/run_v3v4_dashboard_daily_update.py'),'--date',DATE,'--phase','after-scan','--mode','dry-run','--no-api','--no-capture','--no-push','--no-cloud','--strict'],cwd=str(ROOT),capture_output=True,text=True,timeout=30)
    marker_path=STATUS/f'v3v4_dashboard_daily_update_after_scan_dry_run_{DATE}.json'
    marker=json.loads(marker_path.read_text()) if marker_path.exists() else {}
    if proc.returncode!=0: blockers.append(f'after_scan_dynamic_probe_rc_{proc.returncode}')
    if marker.get('date')!=DATE: blockers.append('after_scan_probe_wrong_date')
    if marker.get('status')=='SCAN_NOT_READY': blockers.append('after_scan_probe_scan_not_ready')
    if '20260523' in json.dumps(marker.get('marker_resolution',{}),ensure_ascii=False): blockers.append('marker_resolution_contains_20260523')
    out={'checker':'tools/check_v3v4_dashboard_dynamic_date_markers.py','phase':'V3V4-DASHBOARD-DYNAMIC-DATE-MARKER-AND-MATCHDATE-TZ-HOTFIX','date':DATE,'check_status':'BLOCKER' if blockers else 'PASS','dynamic_marker_guard':not blockers,'hardcoded_hits':hits,'after_scan_status':marker.get('status'),'marker_resolution':marker.get('marker_resolution'),'blockers':blockers}
    STATUS.mkdir(parents=True,exist_ok=True)
    (STATUS/f'check_v3v4_dashboard_dynamic_date_markers_result_{DATE}.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(out,ensure_ascii=False,indent=2))
    return 1 if blockers else 0
if __name__=='__main__': raise SystemExit(main())
