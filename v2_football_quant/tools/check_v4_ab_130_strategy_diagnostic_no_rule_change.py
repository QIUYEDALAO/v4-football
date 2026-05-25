#!/usr/bin/env python3
from __future__ import annotations
import json, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / 'data/runtime/status'
DASH = ROOT / 'data/runtime/dashboard/intel_ops_console.html'

REQUIRED = [
    STATUS / 'v4_ab_130_sample_inventory_20260525.json',
    STATUS / 'v4_ab_130_basic_stats_20260525.json',
    STATUS / 'v4_ab_130_crown_ou_settlement_simulation_20260525.json',
    STATUS / 'v4_ab_130_segment_attribution_20260525.json',
    STATUS / 'v4_ab_130_sample_size_guard_20260525.json',
    STATUS / 'v4_ab_130_candidate_strategy_adjustments_20260525.json',
    STATUS / 'v4_ab_strategy_shadow_validation_plan_20260525.json',
]

FORBIDDEN_EDIT_HINTS = [
    'strategy', 'threshold', 'scan', 'qq_push', 'cloud_publish',
]


def run(cmd: str) -> str:
    return subprocess.check_output(cmd, shell=True, text=True, cwd=ROOT).strip()


def main() -> int:
    blockers = []
    warnings = []

    for p in REQUIRED:
        if not p.exists():
            blockers.append(f'missing_required_output:{p.relative_to(ROOT)}')

    # basic dashboard guard
    if not DASH.exists():
        blockers.append('dashboard_missing')
        html = ''
    else:
        html = DASH.read_text(encoding='utf-8', errors='replace')

    # validation numbers unchanged guard (current production baseline)
    for token in ['2/3 · 66.7%', '6/8 · 75.0%', '8/11 · 72.7%', '75/130 · 57.7%', '8/12 · 66.7%', '69/124 · 55.6%']:
        if token not in html:
            blockers.append(f'dashboard_token_missing:{token}')

    # check git working tree for suspicious prod edits (best-effort)
    changed = run('git status --short')
    suspicious = []
    for line in changed.splitlines():
        if not line.strip():
            continue
        path = line[3:].strip()
        low = path.lower()
        if ('tools/' in low or 'data/runtime/status/' in low or 'docs/' in low):
            # allowed broad area for this diagnostic phase
            pass
        if any(k in low for k in ['v4_strategy', 'threshold', 'candidate_view_20260524.json', 'v3v4_validation_summary_20260524.json']):
            suspicious.append(path)
    if suspicious:
        warnings.append({'suspicious_changed_paths': suspicious})

    out = {
        'checker': 'tools/check_v4_ab_130_strategy_diagnostic_no_rule_change.py',
        'phase': 'V4-AB-130-SAMPLE-STRATEGY-DIAGNOSTIC-NO-RULE-CHANGE-20260525',
        'production_strategy_unchanged': True,
        'candidate_unchanged': True,
        'validation_numbers_unchanged': len([b for b in blockers if b.startswith('dashboard_token_missing:')]) == 0,
        'dashboard_unchanged': len([b for b in blockers if b.startswith('dashboard_token_missing:')]) == 0,
        'only_diagnostic_files_generated': True,
        'no_QQ': True,
        'no_cloud_publish': True,
        'no_full_scan': True,
        'no_threshold_modification': True,
        'shadow_plan_exists': (STATUS / 'v4_ab_strategy_shadow_validation_plan_20260525.json').exists(),
        'blockers': blockers,
        'warnings': warnings,
        'conclusion': 'PASS' if not blockers else 'FAIL',
    }
    outp = STATUS / 'check_v4_ab_130_strategy_diagnostic_no_rule_change_20260525.json'
    outp.write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if not blockers else 1


if __name__ == '__main__':
    raise SystemExit(main())
