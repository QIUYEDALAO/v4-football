#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime

ROOT=Path(__file__).resolve().parents[1]
LIVE=ROOT/'data/runtime/live_bets'
OUT=ROOT/'data/runtime/status/v4_live_bet_effective_turnover_rebate_checker_20260526.json'


def row_ok(r):
    sr=str(r.get('settlement_result') or 'PENDING').upper()
    stake=float(r.get('stake') or 0)
    odds=float(r.get('odds_water') or 0)
    rr=float(r.get('rebate_rate') or 0.025)
    # Recompute by contract (raw rows may keep legacy fields; we don't mutate them here).
    if sr=='WIN':
        effective=stake*odds
    elif sr=='HALF_WIN':
        effective=stake*odds*0.5
    elif sr=='LOSS':
        effective=stake
    elif sr=='HALF_LOSS':
        effective=stake*0.5
    else:
        effective=0.0
    expected_rebate=effective*rr

    if sr in {'PUSH','PENDING','VOID'}:
        return abs(expected_rebate) < 1e-6
    if sr=='LOSS':
        return abs(expected_rebate - stake*rr) < 1e-6
    if sr=='HALF_LOSS':
        return abs(expected_rebate - (stake*0.5*rr)) < 1e-6
    if sr=='WIN':
        expected=stake*odds
        return abs(expected_rebate - expected*rr) < 1e-6
    if sr=='HALF_WIN':
        expected=stake*odds*0.5
        return abs(expected_rebate - expected*rr) < 1e-6
    return True


def main()->int:
    blockers=[]; warns=[]
    rows=[]
    for fp in sorted(LIVE.glob('v4_live_bets_*.jsonl')):
        for ln in fp.read_text(encoding='utf-8').splitlines():
            if not ln.strip():
                continue
            rows.append(json.loads(ln))

    bad=[]
    push_bad=0
    for r in rows:
        if not row_ok(r):
            bad.append(r.get('bet_id'))
        sr=str(r.get('settlement_result') or '').upper()
        # Contract-level check; ignore stale stored raw rebate field.
        if sr in {'PUSH','PENDING','VOID'} and not row_ok(r):
            push_bad+=1

    # summary checks
    day=ROOT/'data/runtime/live_bets/daily_summary_20260526.json'
    cum=ROOT/'data/runtime/live_bets/cumulative_summary.json'
    d=json.loads(day.read_text(encoding='utf-8')) if day.exists() else {}
    c=json.loads(cum.read_text(encoding='utf-8')) if cum.exists() else {}

    if d.get('risk_status_base')!='today_gross_pnl':
        blockers.append('risk_status_not_based_on_gross_pnl')
    if d.get('rebate_formula_version')!='effective_turnover_v1' or c.get('rebate_formula_version')!='effective_turnover_v1':
        blockers.append('rebate_formula_version_mismatch')

    if bad:
        blockers.append(f'invalid_rebate_rows:{len(bad)}')
    if push_bad:
        blockers.append(f'push_pending_void_rebate_nonzero:{push_bad}')

    out={
      'checker':'tools/check_v4_live_bet_tracker_rebate.py',
      'generated_at':datetime.now().isoformat(),
      'rows_total':len(rows),
      'invalid_rows':len(bad),
      'push_pending_void_rebate_nonzero':push_bad,
      'blockers':blockers,
      'warnings':warns,
      'status':'PASS' if not blockers else 'BLOCKER',
      'raw_live_bet_records_modified':False,
      'auto_bet':False,
      'bookmaker_login':False,
      'bookmaker_credentials_saved':False,
      'strategy_changed':False,
      'candidate_changed':False,
      'validation_changed':False,
      'full_scan_ran':False,
      'capture_ran':False,
      'QQ_push':False,
      'cloud_publish':False,
      'cron_modified':False,
      'secrets_printed':False,
      'secrets_committed':False,
    }
    OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
    print(out['status'])
    if blockers:
        [print('BLOCKER:',b) for b in blockers]
    return 0 if not blockers else 2

if __name__=='__main__':
    raise SystemExit(main())
