#!/usr/bin/env python3
from __future__ import annotations
import json,re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / 'data/runtime/status'
DASH = ROOT / 'data/runtime/dashboard/intel_ops_console.html'
ALLOW = STATUS / 'v3v4_dashboard_active_source_allowlist_20260525.json'
QMAN = STATUS / 'v3v4_dashboard_source_quarantine_manifest_20260525.json'

POLLUTION_PATHS = [
    'data/runtime/status/intel_desk_v4_candidate_view_20260522.json',
    'data/runtime/status/v4_rolling_validation_rebuilt_20260520.json',
    'data/runtime/status/v4_validation_raw_records_20260520.json',
    'data/runtime/dashboard/intel_desk.html',
]

def main() -> int:
    blockers = []
    warnings = []

    if not ALLOW.exists():
        blockers.append('allowlist_missing')
        allow = {}
    else:
        allow = json.loads(ALLOW.read_text(encoding='utf-8'))

    if not QMAN.exists():
        blockers.append('quarantine_manifest_missing')
    else:
        q = json.loads(QMAN.read_text(encoding='utf-8'))
        moved = {i.get('path'): i.get('moved') for i in q.get('items', []) if isinstance(i, dict)}
        for rel in POLLUTION_PATHS:
            if rel in moved and not moved[rel]:
                blockers.append(f'pollution_not_quarantined:{rel}')
            if (ROOT / rel).exists():
                blockers.append(f'pollution_still_active:{rel}')

    if not DASH.exists():
        blockers.append('dashboard_missing')
        html = ''
    else:
        html = DASH.read_text(encoding='utf-8', errors='replace')

    if '20260522' in html and '未就绪' in html:
        blockers.append('stale_20260522_fallback_visible')
    if '124/140' in html:
        blockers.append('old_124_140_visible')
    if '18/18' in html:
        blockers.append('wrong_18_18_visible')
    if re.search(r'HT(?:7270|6140|7340)', html):
        blockers.append('abnormal_ht_visible')
    if all(x not in html for x in ['2/3 · 66.7%','6/8 · 75.0%','8/11 · 72.7%']):
        blockers.append('yesterday_validation_lost')
    if all(x not in html for x in ['8/12 · 66.7%','69/124 · 55.6%']):
        blockers.append('script_validation_lost')

    # Ensure blocked patterns are configured
    bp = allow.get('blocked_patterns', []) if isinstance(allow, dict) else []
    for must in ['124/140 · 88.6%', '18/18 · 100.0%', '20260522']:
        if not any(must in str(x) for x in bp):
            warnings.append(f'blocked_pattern_missing:{must}')

    out = {
        'checker': 'tools/check_v3v4_dashboard_source_decontamination.py',
        'phase': 'V3V4-DASHBOARD-DATA-SOURCE-DECONTAMINATION-AFTER-RESTORE-20260525',
        'allowlist_exists': ALLOW.exists(),
        'quarantine_manifest_exists': QMAN.exists(),
        'pollution_paths_checked': POLLUTION_PATHS,
        'dashboard_path': str(DASH.relative_to(ROOT)),
        'blockers': blockers,
        'warnings': warnings,
        'conclusion': 'PASS' if not blockers and not warnings else ('WARN_ONLY' if not blockers else 'FAIL')
    }
    outp = STATUS / 'check_v3v4_dashboard_source_decontamination_20260525.json'
    outp.write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if not blockers else 1

if __name__ == '__main__':
    raise SystemExit(main())
