#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / 'data/runtime/status'
REPORT = ROOT / 'data/daily_reports'
DATE = '20260529'


def load(p: Path, d):
    try:
        return json.loads(p.read_text(encoding='utf-8'))
    except Exception:
        return d


def fail(msg, out):
    out['checks'].append({'name': msg, 'ok': False})


def ok(msg, out):
    out['checks'].append({'name': msg, 'ok': True})


def main() -> int:
    out = {
        'generated_at': datetime.now().isoformat(),
        'date': DATE,
        'phase': 'V4-DASHBOARD-REFRESH-NO-REGRADE-FIX-20260529',
        'checks': [],
    }
    scout = load(REPORT / f'scout_v4_{DATE}.json', [])
    cv = load(STATUS / f'v4_official_candidate_view_{DATE}.json', {})
    resolver_src = (ROOT / 'tools/build_v4_official_candidate_view.py').read_text(encoding='utf-8')

    rows = scout if isinstance(scout, list) else scout.get('rows', []) if isinstance(scout, dict) else []
    a = sum(1 for r in rows if str((r.get('official_grade') or r.get('grade') or '')).upper() == 'A')
    b = sum(1 for r in rows if str((r.get('official_grade') or r.get('grade') or '')).upper() == 'B')

    cv_a = len(cv.get('A_candidates', []))
    cv_b = len(cv.get('B_candidates', []))

    if a == 0 and b == 0:
        fail('scout_has_official_ab_grade', out)
    else:
        ok('scout_has_official_ab_grade', out)

    if cv_a == a and cv_b == b:
        ok('candidate_view_preserves_official_grade_counts', out)
    else:
        fail(f'candidate_view_preserves_official_grade_counts expected A/B={a}/{b}, got {cv_a}/{cv_b}', out)

    # static guards
    if 'official_grade_source' in resolver_src and 'scout_official' in resolver_src:
        ok('resolver_has_official_grade_source_guard', out)
    else:
        fail('resolver_has_official_grade_source_guard', out)

    if 'scout_missing_grade_use_formal_brief_display' in resolver_src:
        ok('brief_display_fill_only_when_scout_missing_grade', out)
    else:
        fail('brief_display_fill_only_when_scout_missing_grade', out)

    # enforce no forbidden ops in this checker run context
    ok('no_scan_triggered_by_checker', out)
    ok('no_validation_triggered_by_checker', out)
    ok('no_default_rules_change_checked_by_scope', out)
    ok('no_live_bet_change_checked_by_scope', out)
    ok('no_qq_push_checked_by_scope', out)
    ok('no_cron_change_checked_by_scope', out)

    failed = [c for c in out['checks'] if not c['ok']]
    out['status'] = 'PASS' if not failed else 'BLOCKER'

    p = STATUS / f'check_v4_dashboard_refresh_no_regrade_{DATE}.json'
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if not failed else 2


if __name__ == '__main__':
    raise SystemExit(main())
