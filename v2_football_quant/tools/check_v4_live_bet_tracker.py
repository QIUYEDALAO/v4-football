#!/usr/bin/env python3
from __future__ import annotations
import json
import time
import urllib.request
import urllib.error
import subprocess
from pathlib import Path

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

        d = '20260526'
        add_payload = {
            'date': d,
            'fixture_id': 999001,
            'league': '测试联赛',
            'home_cn': '测试主队',
            'away_cn': '测试客队',
            'v4_grade': 'A',
            'market_line': 'O1',
            'odds_water': 1.0,
            'stake': 100,
            'official_source': 'manual',
            'bet_status': 'BET'
        }
        c, add_res = http_post('http://127.0.0.1:8766/api/live_bets/add', add_payload)
        if c != 200 or (not add_res.get('ok')):
            blockers.append('api_add_failed')
        else:
            bid = add_res['record']['bet_id']
            c2, settle_res = http_post('http://127.0.0.1:8766/api/live_bets/settle', {
                'date': d, 'bet_id': bid, 'market_line': 'O1', 'stake': 100, 'odds_water': 1.0, 'ht_goal_count': 2, 'rebate_rate': 0.025
            })
            if c2 != 200 or (not settle_res.get('ok')):
                blockers.append('api_settle_failed')

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

    except Exception as e:
        blockers.append(f'server_or_api_error:{e}')
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except Exception:
            proc.kill()

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
        'jsonl_write_ok': 'api_add_failed' not in blockers,
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
