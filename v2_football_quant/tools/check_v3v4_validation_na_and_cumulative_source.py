#!/usr/bin/env python3
import json
import re
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
STATUS_DIR = ROOT / 'data/runtime/status'
HTML_PATH = ROOT / 'data/runtime/dashboard/intel_ops_console.html'
SUMMARY_PATH = STATUS_DIR / 'v3v4_validation_summary_20260525.json'
OUT_PATH = STATUS_DIR / 'check_v3v4_validation_na_and_cumulative_source_20260526.json'


def load_json(path: Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return None


def main():
    blockers = []
    warns = []

    html = HTML_PATH.read_text(encoding='utf-8') if HTML_PATH.exists() else ''
    summary = load_json(SUMMARY_PATH) or {}

    # 1) N/A cannot be treated as validation success
    non_success_tokens = ('validation 链路未视为成功', '不代表验证链路成功')
    ysec = re.search(r'<div class="validation-col validation-yesterday">(.*?)</div>\s*</div>', html, re.S)
    ytxt = ysec.group(1) if ysec else ''
    yesterday_na = 'N/A' in ytxt
    if yesterday_na and not any(t in html for t in non_success_tokens):
        blockers.append('na_marked_as_success_or_missing_failure_label')

    # 2) API missing/disabled cannot PASS
    api_disabled = '--no-api' in str(summary.get('api_disabled_reason', ''))
    if api_disabled and yesterday_na and not any(t in html for t in non_success_tokens):
        blockers.append('api_disabled_but_no_chain_failure_label')

    # 3) old 124/140 not as AB-only primary
    if '124/140 · 88.6%' in html:
        blockers.append('old_124_140_reflowed_as_primary')

    # 4) C excluded from A/B-only
    if 'A/B-only · 不含C' not in html:
        blockers.append('ab_only_source_label_missing')

    # 5) brief cannot be used for hit-rate
    if summary.get('brief_used_for_hit_rate') is not False:
        blockers.append('brief_used_for_hit_rate_not_false')

    # 6) scan_date cannot be used for validation
    if summary.get('date_filter_field') and summary.get('date_filter_field') != 'match_date':
        blockers.append('scan_date_used_for_validation')

    # 7) dashboard must show source label
    if 'result_source_label=' not in html and 'A/B-only · 不含C' not in html:
        blockers.append('dashboard_source_label_missing')

    result = {
        'phase': 'V3V4-DASHBOARD-VALIDATION-NA-AND-CUMULATIVE-RECOUNT-CORRECTION-20260526',
        'generated_at': datetime.now().isoformat(),
        'dashboard_path': str(HTML_PATH.relative_to(ROOT)),
        'summary_path': str(SUMMARY_PATH.relative_to(ROOT)),
        'api_disabled': api_disabled,
        'yesterday_na': yesterday_na,
        'brief_used_for_hit_rate': summary.get('brief_used_for_hit_rate'),
        'date_filter_field': summary.get('date_filter_field'),
        'blockers': blockers,
        'warnings': warns,
        'pass': len(blockers) == 0,
        'status': 'PASS' if len(blockers) == 0 else 'BLOCKER',
    }
    OUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')

    print(result['status'])
    if blockers:
        for b in blockers:
            print('BLOCKER:', b)


if __name__ == '__main__':
    main()
