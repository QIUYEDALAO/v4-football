#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / 'data/runtime/status'
DASH = ROOT / 'data/runtime/dashboard'


def load(p: Path):
    return json.loads(p.read_text(encoding='utf-8'))


def main() -> int:
    blockers = []
    warnings = []

    inv_p = STATUS / 'v4_league_hit_rate_inventory_20260526.json'
    stats_p = STATUS / 'v4_league_hit_rate_stats_20260526.json'
    html_p = DASH / 'v4_league_hit_rate.html'

    if not inv_p.exists():
        blockers.append('inventory_missing')
    if not stats_p.exists():
        blockers.append('stats_missing')
    if not html_p.exists():
        blockers.append('html_missing')

    if not blockers:
        inv = load(inv_p)
        stats = load(stats_p)

        A = int(inv.get('A_settled', -1))
        B = int(inv.get('B_settled', -1))
        AB = int(inv.get('AB_settled', -1))
        if (A, B, AB) != (41, 89, 130):
            warnings.append(f'sample_count_not_baseline:A={A},B={B},AB={AB}')

        recs = inv.get('records', [])
        for r in recs:
            if str(r.get('grade', '')).upper() not in {'A', 'B'}:
                blockers.append('non_ab_mixed')
                break
            if not bool(r.get('valid_for_league_stats', False)):
                blockers.append('invalid_records_mixed')
                break

        if bool(stats.get('outside_57_mixed', True)):
            blockers.append('outside_57_mixed_into_official')

        leagues = stats.get('leagues', [])
        if not leagues:
            blockers.append('leagues_empty')

        allowed_actions = {
            'KEEP_OBSERVE',
            'GOOD_BUT_SMALL_SAMPLE',
            'WATCHLIST',
            'SHADOW_DOWNGRADE_CANDIDATE',
            'SHADOW_UPGRADE_CANDIDATE',
            'NO_ACTION_LOW_SAMPLE',
        }
        forbidden_actions = {'DELETE_LEAGUE', 'BAN_LEAGUE_NOW', 'PRODUCTION_CHANGE_NOW'}

        for lg in leagues:
            for k in ['sample_total_ab', 'hit_rate_a', 'hit_rate_b', 'hit_rate_ab', 'ht_0_goal_count', 'ht_1_goal_count', 'ht_2plus_goal_count', 'o075_roi_with_rebate', 'o1_roi_with_rebate', 'o125_roi_with_rebate', 'o15_roi_with_rebate']:
                if k not in lg:
                    blockers.append(f'league_field_missing:{k}')
                    break
            action = str(lg.get('recommended_action', ''))
            if action not in allowed_actions:
                blockers.append(f'invalid_action:{action}')
            if action in forbidden_actions:
                blockers.append(f'forbidden_action:{action}')
            n = int(lg.get('sample_total_ab', 0))
            if n < 10 and action in {'SHADOW_DOWNGRADE_CANDIDATE', 'SHADOW_UPGRADE_CANDIDATE'}:
                blockers.append(f'small_sample_shadow_action:{lg.get("league")}:{n}')

    out = {
        'checker': 'tools/check_v4_league_hit_rate_report.py',
        'phase': 'V4-LEAGUE-HIT-RATE-AND-ROI-DIAGNOSTIC-20260526',
        'inventory_exists': inv_p.exists(),
        'stats_exists': stats_p.exists(),
        'html_exists': html_p.exists(),
        'blockers': blockers,
        'warnings': warnings,
        'conclusion': 'PASS' if not blockers else 'BLOCKER'
    }
    outp = STATUS / 'check_v4_league_hit_rate_report_20260526.json'
    outp.write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if not blockers else 1


if __name__ == '__main__':
    raise SystemExit(main())
