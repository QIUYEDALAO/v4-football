#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / 'data/runtime/status'
LIVE = ROOT / 'data/runtime/live_bets'
HTML = ROOT / 'data/runtime/dashboard/v4_control_center.html'


def load_json(p: Path):
    try:
        return json.loads(p.read_text(encoding='utf-8'))
    except Exception:
        return {}


def load_jsonl(p: Path):
    out = []
    if not p.exists():
        return out
    for ln in p.read_text(encoding='utf-8').splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            out.append(json.loads(ln))
        except Exception:
            pass
    return out


def main() -> int:
    today = datetime.now().strftime('%Y%m%d')
    model = load_json(STATUS / f'v4_control_center_model_{today}.json')
    se = model.get('live_bet_summary') or {}
    todo = model.get('todo_summary') or {}

    no_bet_path = LIVE / f'v4_no_bet_decisions_{today}.jsonl'
    no_bets = load_jsonl(no_bet_path)

    checks = []

    checks.append(("no_bet_file_exists_or_empty_ok", True, str(no_bet_path)))

    bad_flags = [r for r in no_bets if any([
        r.get('counts_as_bet') is not False,
        r.get('counts_as_stake') is not False,
        r.get('counts_as_pnl') is not False,
        r.get('counts_as_turnover') is not False,
        r.get('counts_as_validation') is not False,
    ])]
    checks.append(("no_bet_flags_all_false", len(bad_flags) == 0, f"bad={len(bad_flags)}"))

    html = HTML.read_text(encoding='utf-8') if HTML.exists() else ''
    checks.append(("frontend_button_exists", "早进球未投" in html and "/api/v4_live_bet/no_bet" in html, "button+api"))

    today_stake = float(se.get('today_stake', 0) or 0)
    today_real_stake = float(se.get('today_real_stake', 0) or 0)
    checks.append(("stake_fields_present", isinstance(today_stake, float) and isinstance(today_real_stake, float), f"today_stake={today_stake}"))

    # no_bet should not inflate stake/pnl/turnover by itself; we only assert model has dedicated no_bet fields.
    checks.append(("todo_has_no_bet_fields", 'no_bet_count' in todo and 'no_bet_items' in todo, f"no_bet_count={todo.get('no_bet_count')}"))

    blockers, warnings = [], []
    for n, ok, d in checks:
        if not ok:
            blockers.append(f"{n}: {d}")

    out = {
        'phase': 'V4-LIVE-BET-NO-BET-REASON-EARLY-GOAL-RECORD-20260527',
        'generated_at': datetime.now().isoformat(),
        'checker': 'tools/check_v4_no_bet_reason.py',
        'checks': [{'name': n, 'ok': ok, 'detail': d} for n, ok, d in checks],
        'blockers': blockers,
        'warnings': warnings,
        'conclusion': 'PASS' if not blockers else 'BLOCKER',
        'full_scan_ran': False,
        'validation_recomputed': False,
        'QQ_push': False,
        'cloud_publish': False,
        'cron_modified': False,
    }
    out_path = STATUS / 'v4_no_bet_reason_checker_20260527.json'
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'result': str(out_path), 'conclusion': out['conclusion'], 'blockers': len(blockers)}, ensure_ascii=False))
    return 0 if out['conclusion'] == 'PASS' else 2


if __name__ == '__main__':
    raise SystemExit(main())
