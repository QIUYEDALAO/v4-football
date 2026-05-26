#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / 'data/runtime/status'
TOOLS = ROOT / 'tools'
DASH = ROOT / 'data/runtime/dashboard/v4_control_center.html'


def load_latest_summary() -> tuple[Path|None, dict]:
    files = sorted(STATUS.glob('v4_system_error_summary_*.json'))
    if not files:
        return None, {}
    p = files[-1]
    try:
        return p, json.loads(p.read_text(encoding='utf-8'))
    except Exception:
        return p, {}


def main() -> int:
    now = datetime.now().isoformat()
    out = {
        'phase': 'V4-CONTROL-CENTER-COPY-CLEANUP-AND-ERROR-ACTIVE-LOGIC-FIX-20260527',
        'generated_at': now,
        'checker': 'tools/check_v4_system_error_center.py',
        'checks': [],
        'blockers': [],
        'warnings': [],
        'conclusion': 'PASS'
    }

    def check(name: str, ok: bool, detail: str = '', blocker: bool = True):
        out['checks'].append({'name': name, 'ok': ok, 'detail': detail})
        if not ok:
            if blocker:
                out['blockers'].append(f'{name}: {detail}')
            else:
                out['warnings'].append(f'{name}: {detail}')

    collector = TOOLS / 'collect_v4_system_error_summary.py'
    src = collector.read_text(encoding='utf-8', errors='ignore') if collector.exists() else ''
    check('collector_exists', collector.exists(), str(collector))
    check('collector_has_json_parse_contract', '_status_from_json_obj' in src, 'must parse JSON structurally')
    check('collector_has_self_feedback_excludes', 'SELF_FEEDBACK_EXCLUDES' in src, 'must exclude own summary/checker outputs')
    check('collector_has_active_whitelist', '_is_active_eligible_status_file' in src, 'must enforce active source whitelist')

    summary_path, summary = load_latest_summary()
    check('summary_exists', summary_path is not None, str(summary_path) if summary_path else 'missing')

    active = summary.get('active_items', []) if isinstance(summary, dict) else []
    recent = summary.get('recent_items', []) if isinstance(summary, dict) else []
    c_active_err = int(summary.get('active_error_count') or 0)
    c_active_blk = int(summary.get('active_blocker_count') or 0)

    # 0) header copy cleanup checks
    if DASH.exists():
        html = DASH.read_text(encoding='utf-8', errors='ignore')
        check('copy_remove_final_design', '最终设计稿' not in html, 'found 最终设计稿')
        check('copy_remove_main_route', '主入口：8766/v4_control_center.html' not in html, 'found main route copy')
        check('copy_remove_8765_route', '8765：只读跳转' not in html, 'found 8765 route copy')
        # green blocker conflict guard (string template level)
        if c_active_blk == 0:
            check('no_blocker_text_when_zero', '系统阻塞' not in html, 'html still contains blocker text template', blocker=False)
        if c_active_err == 0:
            check('no_error_count_text_when_zero', '系统异常(' not in html, 'html still contains error count template', blocker=False)
    else:
        check('dashboard_html_exists', False, str(DASH))

    # 1) ACTIVE hard guards
    bad_active = []
    for it in active:
        sf = str(it.get('source_file') or '')
        s = str(it.get('summary') or '')
        sev = str(it.get('severity') or '').upper()
        resolved = bool(it.get('resolved'))
        if resolved:
            bad_active.append((sf, 'resolved=true in ACTIVE'))
        if sf.startswith('v4_system_error_summary_'):
            bad_active.append((sf, 'self feedback in ACTIVE'))
        if 'all_pass' in s and 'true' in s.lower():
            bad_active.append((sf, 'all_pass=true in ACTIVE'))
        if 'conclusion' in s and 'PASS' in s:
            bad_active.append((sf, 'conclusion=PASS in ACTIVE'))
        if 'blockers' in s and '[]' in s:
            bad_active.append((sf, 'blockers=[] in ACTIVE'))
        if sev not in {'BLOCKER', 'FAIL'}:
            bad_active.append((sf, f'ACTIVE severity invalid: {sev}'))
        if bool(it.get('process_artifact')):
            bad_active.append((sf, 'process_artifact=true in ACTIVE'))
        lname = sf.lower()
        if any(x in lname for x in ('freeze', 'audit', 'verify', 'git_manifest', '_manifest_', 'report')):
            bad_active.append((sf, 'process file pattern in ACTIVE'))
        if 'checker' in lname and ('pass' in s.lower() or 'all_pass' in s.lower()):
            bad_active.append((sf, 'checker pass in ACTIVE'))
        if 'all_pass' in s.lower() and 'true' in s.lower():
            bad_active.append((sf, 'all_pass=true in ACTIVE'))
        if '已恢复' in str(it):
            bad_active.append((sf, '已恢复 text in ACTIVE item'))
        if bool(it.get('active_eligible')) is False:
            bad_active.append((sf, 'active_eligible=false in ACTIVE'))
        if sev == 'WARN':
            bad_active.append((sf, 'WARN in ACTIVE'))
        # historical recovered defaults should not stay in ACTIVE
        if any(k in lname for k in ('qq_notify_done', 'dashboard_daily_auto_update', 'api_controlled_ingest_real')):
            bad_active.append((sf, 'known historical recovered source in ACTIVE'))

    check('active_has_no_false_positive_pass_items', len(bad_active) == 0, str(bad_active[:8]))

    # 2) ACTIVE counters must match unresolved blocker/fail
    unresolved = [i for i in active if not bool(i.get('resolved')) and str(i.get('severity','')).upper() in {'BLOCKER','FAIL'}]
    unresolved_blockers = [i for i in unresolved if str(i.get('severity','')).upper() == 'BLOCKER']
    check('active_error_count_matches', c_active_err == len(unresolved), f'count={c_active_err}, expected={len(unresolved)}')
    check('active_blocker_count_matches', c_active_blk == len(unresolved_blockers), f'count={c_active_blk}, expected={len(unresolved_blockers)}')
    check('active_error_count_matches_active_items_len', c_active_err == len(active), f'count={c_active_err}, active_len={len(active)}')
    check('active_resolved_true_count_zero', sum(1 for i in active if bool(i.get('resolved')))==0, 'resolved=true found in ACTIVE')
    check('active_process_artifact_zero', sum(1 for i in active if bool(i.get('process_artifact')))==0, 'process_artifact=true found in ACTIVE')
    check('active_active_eligible_false_zero', sum(1 for i in active if i.get('active_eligible') is False)==0, 'active_eligible=false found in ACTIVE')
    check('active_warn_zero', sum(1 for i in active if str(i.get('severity','')).upper()=='WARN')==0, 'WARN found in ACTIVE')

    # 3) recent can contain resolved/warn
    rec_bad = [i for i in recent if bool(i.get('active')) and bool(i.get('resolved'))]
    check('recent_has_no_active_resolved_conflict', len(rec_bad) == 0, f'bad={len(rec_bad)}')

    # 4) frontend safety text gates
    if DASH.exists():
        html = DASH.read_text(encoding='utf-8', errors='ignore')
        check('frontend_no_raw_log_token', 'raw_log' not in html.lower(), 'raw log token exists')
        check('frontend_no_kill_retry_rerun_buttons', all(k not in html.lower() for k in ['kill', 'rerun', 'retry']), 'dangerous action words found', blocker=False)
        check('frontend_active_title_updated', '当前未恢复' in html, 'ACTIVE title not updated')
        check('frontend_recent_title_updated', '最近已恢复 / 观察项' in html, 'RECENT title not updated')

    # 5) model-facing consistency
    if c_active_blk == 0:
        check('active_blocker_zero_consistency', summary.get('system_error_status') != 'BLOCKER', f"status={summary.get('system_error_status')}", blocker=False)
    if c_active_err == 0:
        check('active_error_zero_consistency', summary.get('system_error_status') in {'PASS','WARN_ONLY'}, f"status={summary.get('system_error_status')}", blocker=False)

    if out['blockers']:
        out['conclusion'] = 'BLOCKER'
    elif out['warnings']:
        out['conclusion'] = 'WARN_ONLY'

    res = STATUS / 'v4_control_center_copy_error_checker_20260527.json'
    res.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'result': str(res), 'conclusion': out['conclusion'], 'blockers': len(out['blockers']), 'warnings': len(out['warnings'])}, ensure_ascii=False))
    return 0 if out['conclusion'] != 'BLOCKER' else 1


if __name__ == '__main__':
    raise SystemExit(main())
