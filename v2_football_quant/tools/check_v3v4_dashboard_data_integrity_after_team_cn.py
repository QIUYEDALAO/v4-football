#!/usr/bin/env python3
from __future__ import annotations
import json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASH = ROOT / 'data/runtime/dashboard/intel_ops_console.html'
STATUS = ROOT / 'data/runtime/status'


def main() -> int:
    blockers = []
    warnings = []
    if not DASH.exists():
        print(json.dumps({
            'checker': 'tools/check_v3v4_dashboard_data_integrity_after_team_cn.py',
            'conclusion': 'BLOCKER',
            'blockers': ['dashboard_missing']
        }, ensure_ascii=False, indent=2))
        return 2

    html = DASH.read_text(encoding='utf-8', errors='replace')

    # 1) source date fallback regression guard
    source_date_regressed = ('20260522' in html and '未就绪' in html)
    if source_date_regressed:
        blockers.append('source_date_regressed_to_20260522')

    # 2) old cumulative rollback guard
    if '124/140' in html:
        blockers.append('old_cumulative_124_140_returned')

    # 3) yesterday validation not cleared
    has_yesterday = all(x in html for x in ['2/3 · 66.7%', '6/8 · 75.0%', '8/11 · 72.7%'])
    if not has_yesterday:
        blockers.append('yesterday_validation_missing_or_changed')

    # 4) script validation not cleared
    has_script = all(x in html for x in ['8/12 · 66.7%', '69/124 · 55.6%'])
    if not has_script:
        blockers.append('script_validation_missing_or_changed')

    # 5) abnormal HT guard
    if re.search(r'HT(?:7270|6140|7340)', html):
        blockers.append('abnormal_ht_value_present')

    # 6) candidate count unchanged
    candidate_ok = ('A5 / B5' in html and 'SKIP4' in html)
    if not candidate_ok:
        blockers.append('candidate_count_changed')

    # 7) result validation changed guard
    result_ok = all(x in html for x in ['25/41 · 61.0%', '50/89 · 56.2%', '75/130 · 57.7%'])
    if not result_ok:
        blockers.append('result_validation_changed')

    # 8) script validation changed guard
    script_ok = has_script

    # 9) team-cn main title + english audit line coexist
    # Only fail when one side of main title has no Chinese chars and has Latin tokens.
    english_main = False
    for m in re.finditer(r"<div class=\"match-line\">(.*?)</div>", html, flags=re.S):
        plain = re.sub(r"<[^>]+>", "", m.group(1))
        parts = [x.strip() for x in plain.split("vs")]
        if len(parts) != 2:
            continue
        for side in parts:
            has_zh = bool(re.search(r"[\u4e00-\u9fff]", side))
            has_latin = bool(re.search(r"[A-Za-z]{3,}", side))
            if (not has_zh) and has_latin:
                english_main = True
                break
        if english_main:
            break
    en_audit = ('EN:' in html)
    if english_main:
        blockers.append('english_main_title_visible')
    if not en_audit:
        warnings.append('en_audit_line_missing')

    out = {
        'checker': 'tools/check_v3v4_dashboard_data_integrity_after_team_cn.py',
        'phase': 'V3V4-TEAM-CN-BAD-FIX-ROLLBACK-AND-DATA-RESTORE-20260525',
        'dashboard_path': str(DASH.relative_to(ROOT)),
        'source_date_regressed_20260522': source_date_regressed,
        'old_124_140_visible': '124/140' in html,
        'yesterday_validation_ok': has_yesterday,
        'script_validation_ok': script_ok,
        'candidate_count_ok': candidate_ok,
        'result_validation_ok': result_ok,
        'abnormal_ht_present': bool(re.search(r'HT(?:7270|6140|7340)', html)),
        'english_main_title_visible': bool(english_main),
        'en_audit_line_present': en_audit,
        'blockers': blockers,
        'warnings': warnings,
        'conclusion': 'PASS' if not blockers and not warnings else ('WARN_ONLY' if not blockers else 'FAIL')
    }
    marker = STATUS / 'check_v3v4_dashboard_data_integrity_after_team_cn_20260525.json'
    marker.write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if not blockers else 1


if __name__ == '__main__':
    raise SystemExit(main())
