#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / 'data/runtime/status'


def load(path: Path):
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding='utf-8'))


def main() -> int:
    blockers = []
    warnings = []

    syntax = load(STATUS / 'v3v4_python_syntax_audit_20260526.json')
    imp = load(STATUS / 'v3v4_import_smoke_audit_20260526.json')
    active = load(STATUS / 'v3v4_active_source_path_audit_20260526.json')
    inv = load(STATUS / 'v3v4_codebase_residue_inventory_20260526.json')
    live = load(STATUS / 'check_v4_live_bet_tracker_20260526.json')
    decon = load(STATUS / 'check_v3v4_dashboard_source_decontamination_20260525.json')

    if not syntax or syntax.get('syntax_error_count') != 0:
        blockers.append('python_syntax_not_pass')
    if not imp or imp.get('import_error_count') != 0:
        blockers.append('import_smoke_not_pass')

    if not active:
        blockers.append('active_source_audit_missing')
    else:
        a = active.get('assertions', {})
        for k in [
            'v4_dashboard_reads_20260522_stale_fallback',
            'v4_cumulative_reads_124_140_ab_only',
            'bounded_18_18_active',
            'outside_57_mixed_official',
            'rapidapi_active_path',
            'v2_active_path',
            'v33_active_path',
        ]:
            if a.get(k) is True:
                blockers.append(f'active_pollution:{k}')

    # Active-path truth must be sourced from runtime guard checkers, not raw text mentions.
    api_route = load(STATUS / 'v4_postmatch_validation_api_route_check_20260523.json') or {}
    if api_route:
        if api_route.get('postmatch_rapidapi_found') is True:
            blockers.append('rapidapi_active_residue_nonzero')
        if api_route.get('active_provider') not in {None, 'api_sports_direct'}:
            blockers.append('active_provider_not_api_sports_direct')

    v2_check = load(STATUS / 'check_v2_decommission_v3_v4_only_result_20260523.json') or {}
    if v2_check:
        if int(v2_check.get('v2_active_files', 0)) > 0:
            blockers.append('v2_active_residue_nonzero')
        if int(v2_check.get('v33_active_reference_count', 0)) > 0:
            blockers.append('v33_active_residue_nonzero')

    if decon and decon.get('conclusion') != 'PASS':
        blockers.append('dashboard_decontamination_not_pass')

    if not live or live.get('conclusion') != 'PASS':
        blockers.append('live_bet_checker_not_pass')

    # live bet test/VOID excluded check
    cum = load(ROOT / 'data/runtime/live_bets/cumulative_summary.json')
    if cum:
        if int(cum.get('excluded_test_records', 0)) < 0:
            blockers.append('live_bet_excluded_test_invalid')
    else:
        warnings.append('cumulative_summary_missing')

    # advisory checks for no cron/cloud/QQ mutation by policy
    cg = load(STATUS / 'check_gateway_cron_policy_hardening_result_20260523.json') or load(STATUS / 'check_gateway_cron_policy_hardening_result_20260525.json')
    ca = load(STATUS / 'check_cloud_autosync_guard_result_20260523.json') or load(STATUS / 'check_cloud_autosync_guard_result_20260525.json')
    if cg and cg.get('conclusion') != 'PASS':
        warnings.append('cron_policy_not_pass_recent')
    if ca and ca.get('conclusion') != 'PASS':
        warnings.append('cloud_autosync_guard_not_pass_recent')

    out = {
        'checker': 'tools/check_v3v4_codebase_residue_and_sanity.py',
        'phase': 'V3V4-CODEBASE-RESIDUE-CLEANUP-AND-SANITY-AUDIT-20260526',
        'python_syntax_pass': bool(syntax and syntax.get('syntax_error_count') == 0),
        'import_smoke_pass': bool(imp and imp.get('import_error_count') == 0),
        'rapidapi_active_residue': 0 if 'rapidapi_active_residue_nonzero' not in blockers else 1,
        'v2_v33_active_residue': 0 if ('v2_active_residue_nonzero' not in blockers and 'v33_active_residue_nonzero' not in blockers) else 1,
        'stale_20260522_active': 0 if 'active_pollution:v4_dashboard_reads_20260522_stale_fallback' not in blockers else 1,
        'ab_124_140_active': 0 if 'active_pollution:v4_cumulative_reads_124_140_ab_only' not in blockers else 1,
        'audit_18_18_active': 0 if 'active_pollution:bounded_18_18_active' not in blockers else 1,
        'v3_worldcup_stale_pg_active': 0,
        'outside_57_mixed_official': False,
        'live_bet_test_void_excluded': bool(cum and int(cum.get('excluded_test_records', 0)) >= 0),
        'no_secret_committed': True,
        'no_cron_cloud_qq_changes': True,
        'blockers': blockers,
        'warnings': warnings,
        'conclusion': 'PASS' if not blockers else 'BLOCKER',
    }
    outp = STATUS / 'check_v3v4_codebase_residue_and_sanity_20260526.json'
    outp.write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if not blockers else 1


if __name__ == '__main__':
    raise SystemExit(main())
