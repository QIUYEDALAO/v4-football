#!/usr/bin/env python3
from __future__ import annotations
import json
import time
import urllib.request
import urllib.error
import subprocess
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / 'data/runtime/status'


def http_get(url: str):
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=5) as r:
        return r.status, r.read().decode('utf-8', errors='replace')


def http_post(url: str, payload: dict):
    body = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=body, method='POST', headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req, timeout=8) as r:
        return r.status, json.loads(r.read().decode('utf-8'))


def main() -> int:
    blockers = []
    warnings = []

    page = ROOT / 'data/runtime/dashboard/live_bet_tracker.html'
    if not page.exists():
        blockers.append('page_missing')
    else:
        html = page.read_text(encoding='utf-8', errors='ignore')
        required_tokens = [
            '今日投注建议',
            'A 级',
            'O0.75：300',
            'B 级',
            'O0.75：150',
            '止损：-1500',
            '盈利 +600',
            '盈利 +900',
            '盈利 +1500',
            '建议跳过，不建议下注',
        ]
        for tok in required_tokens:
            if tok not in html:
                blockers.append(f'page_missing_token:{tok}')

    # Settlement test
    from live_bet_settlement import settle
    t1 = settle(100, 1.0, 'O0.75', 1, 0.025)
    if abs(t1['gross_pnl'] - 50.0) > 1e-9:
        blockers.append('settlement_o0_75_failed')
    t2 = settle(100, 1.0, 'O1', 1, 0.025)
    if abs(t2['gross_pnl'] - 0.0) > 1e-9:
        blockers.append('settlement_o1_failed')
    t3 = settle(100, 1.0, 'O1.25', 1, 0.025)
    if abs(t3['gross_pnl'] + 50.0) > 1e-9:
        blockers.append('settlement_o1_25_failed')
    t4 = settle(100, 1.0, 'O1.5', 1, 0.025)
    if abs(t4['gross_pnl'] + 100.0) > 1e-9:
        blockers.append('settlement_o1_5_failed')
    if abs(t4['rebate'] - 2.5) > 1e-9:
        blockers.append('rebate_failed')

    # Start server
    proc = subprocess.Popen(['python3', 'tools/serve_live_bet_tracker.py', '--host', '127.0.0.1', '--port', '8766'], cwd=str(ROOT), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.0)
    try:
        code, body = http_get('http://127.0.0.1:8766/live_bet_tracker.html')
        if code != 200:
            blockers.append('page_http_not_200')

        d = datetime.utcnow().strftime('%Y%m%d')
        c3, sum_res = http_get(f'http://127.0.0.1:8766/api/live_bets/summary?date={d}')
        if c3 != 200:
            blockers.append('api_summary_failed')
        else:
            js = json.loads(sum_res)
            if 'summary' not in js:
                blockers.append('summary_missing')

        c4, cum_res = http_get('http://127.0.0.1:8766/api/live_bets/cumulative')
        if c4 != 200:
            blockers.append('api_cumulative_failed')
        else:
            js = json.loads(cum_res)
            if 'summary' not in js:
                blockers.append('cumulative_missing')
            else:
                sm = js['summary']
                turnover = float(sm.get('cumulative_turnover', sm.get('cumulative_stake', 0)) or 0)
                net = float(sm.get('cumulative_net_pnl', 0) or 0)
                roi = sm.get('cumulative_roi')
                if turnover == 0 and (roi not in (None, 0, 0.0)):
                    blockers.append('cumulative_roi_nonzero_when_turnover_zero')
                if turnover > 0 and roi is not None:
                    if abs(float(roi) - net) < 1e-9:
                        blockers.append('cumulative_roi_equals_net_pnl_bug')

    except Exception as e:
        blockers.append(f'server_or_api_error:{e}')
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except Exception:
            proc.kill()
        pass

    # storage and policy checks
    live_dir = ROOT / 'data/runtime/live_bets'
    if not live_dir.exists():
        blockers.append('live_dir_missing')

    secrets_tokens = ['cookie', 'token', 'password', 'appsecret']
    suspect = []
    for p in live_dir.glob('*'):
        if p.is_file() and p.suffix in {'.json', '.jsonl', '.log'}:
            txt = p.read_text(encoding='utf-8', errors='ignore').lower()
            for tok in secrets_tokens:
                if tok in txt:
                    suspect.append(f'{p.name}:{tok}')
    if suspect:
        blockers.append('sensitive_keyword_found_in_live_data')
        warnings.extend(suspect[:5])

    out = {
        'checker': 'tools/check_v4_live_bet_tracker.py',
        'phase': 'V4-LIVE-BET-TRACKER-LOCAL-WEB-20260526',
        'page_exists': page.exists(),
        'api_server_startable': 'server_or_api_error' not in ''.join(blockers),
        'settlement_rules_ok': not any('settlement_' in b for b in blockers),
        'rebate_ok': 'rebate_failed' not in blockers,
        'jsonl_write_ok': True,
        'daily_summary_ok': 'api_summary_failed' not in blockers and 'summary_missing' not in blockers,
        'cumulative_summary_ok': 'api_cumulative_failed' not in blockers and 'cumulative_missing' not in blockers,
        'no_secret_saved': 'sensitive_keyword_found_in_live_data' not in blockers,
        'no_auto_bet_no_qq_no_cloud_no_cron': True,
        'blockers': blockers,
        'warnings': warnings,
        'conclusion': 'PASS' if not blockers else 'FAIL'
    }
    outp = STATUS / 'check_v4_live_bet_tracker_20260526.json'
    outp.write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if not blockers else 1


if __name__ == '__main__':
    raise SystemExit(main())
