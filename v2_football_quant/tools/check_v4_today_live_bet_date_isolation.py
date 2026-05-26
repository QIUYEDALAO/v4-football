#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / 'data/runtime/status'
DASH = ROOT / 'data/runtime/dashboard/v4_control_center.html'


def fail(msg, out):
    out['conclusion'] = 'BLOCKER'
    out['issues'].append(msg)


def main():
    today = datetime.now().strftime('%Y%m%d')
    model_file = STATUS / f'v4_control_center_model_{today}.json'
    out = {
        'phase': 'V4-TODAY-LIVE-BET-DATE-ISOLATION-FIX-20260526',
        'generated_at': datetime.now().isoformat(),
        'today_date': today,
        'model_file': str(model_file),
        'checks': {},
        'issues': [],
        'conclusion': 'PASS'
    }
    if not model_file.exists():
        fail('model file missing', out)
    else:
        m = json.loads(model_file.read_text(encoding='utf-8'))
        live = (m.get('live_bet_summary') or {})
        cands = ((m.get('candidates') or {}).get('items') or [])

        trs = float(live.get('today_real_stake') or live.get('today_stake') or 0)
        tds = float(live.get('today_default_stake') or 0)
        cross = int(live.get('cross_day_open_bets_count') or 0)
        out['checks']['today_real_stake'] = trs
        out['checks']['today_default_stake'] = tds
        out['checks']['cross_day_open_bets_count'] = cross

        if trs > 0 and tds == trs:
            fail('today_real_stake equals default stake, potential contamination', out)
        if cross < 0:
            fail('invalid cross day open count', out)

        for i, x in enumerate(cands):
            bs = str(x.get('live_bet_status') or '')
            settled = bool(x.get('settled'))
            already = bool(x.get('already_bet'))
            # VOID must not force already_bet/settled true
            if bs == 'VOID' and (already or settled):
                fail(f'candidate[{i}] VOID but marked already_bet/settled', out)

    if DASH.exists():
        h = DASH.read_text(encoding='utf-8')
        if '投注本金' in h:
            fail('frontend still shows 投注本金 label', out)
        if 'gross_pnl' in h:
            fail('frontend leaks gross_pnl token', out)
        if ' pending' in h:
            out['issues'].append('WARN: pending token exists in JS source')
            if out['conclusion'] == 'PASS':
                out['conclusion'] = 'WARN_ONLY'
    else:
        fail('dashboard html missing', out)

    result = STATUS / 'v4_today_live_bet_date_isolation_checker_20260526.json'
    result.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'result': str(result), 'conclusion': out['conclusion'], 'issues': out['issues']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
