#!/usr/bin/env python3
"""Check compact V3/V4 dashboard: A/B candidates only, no C active, no 7d block."""
from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "data/runtime/status"
DASH = ROOT / "data/runtime/dashboard/intel_ops_console.html"
DATE = "20260523"
TZ = timezone(timedelta(hours=8))

FORBIDDEN_VISIBLE = [
    "V2 active", "BET_LOCKED", "V2历史池", "V2锁仓", "V2验证", "V2 QQ", "V2_ONLY", "V33 active",
    "C级观察", "C观察", "V4 C观察", "近7天验证",
]


def load(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def curl(url: str) -> tuple[int, str]:
    out = Path('/tmp/v3v4_compact_dashboard_check.html')
    try:
        r = subprocess.run(['curl','-sS','-L','--max-time','3','-w','\n%{http_code}','-o',str(out),url],cwd=str(ROOT),text=True,capture_output=True,timeout=6)
        code = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else '000'
        return int(code) if code.isdigit() else 0, out.read_text(encoding='utf-8',errors='replace') if out.exists() else ''
    except Exception:
        return 0, ''


def strip_tags(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text)


def card_r3_lines(html: str) -> list[str]:
    return [strip_tags(x).strip() for x in re.findall(r'<div class="card-r3">(.*?)</div>', html, flags=re.S)]


def match_lines(html: str) -> list[str]:
    return [strip_tags(x).strip() for x in re.findall(r'<div class="match-line">(.*?)</div>', html, flags=re.S)]


def main() -> int:
    blockers: list[str] = []
    warnings: list[str] = []
    html = DASH.read_text(encoding='utf-8', errors='replace') if DASH.exists() else ''
    code127, body127 = curl('http://127.0.0.1:8765/intel_ops_console.html')
    code192, body192 = curl('http://192.168.1.2:8765/intel_ops_console.html')
    bodies = [('file', html)]
    if code127 == 200:
        bodies.append(('127', body127))
    else:
        blockers.append(f'http_127_not_200:{code127}')
    if code192 == 200:
        bodies.append(('192', body192))
    else:
        warnings.append(f'http_192_not_200:{code192}')

    validation = load(STATUS / f'v3v4_validation_summary_{DATE}.json')
    build = load(STATUS / f'v3v4_dashboard_compact_validation_remove_c_obs_build_{DATE}.json') or load(STATUS / f'v3v4_dashboard_brief_validation_auto_refresh_build_{DATE}.json')
    daily = load(STATUS / f'v3v4_dashboard_daily_refresh_{DATE}.json')
    brief = load(STATUS / f'v3v4_dashboard_brief_resolution_{DATE}.json')
    source = load(STATUS / f'v3v4_dashboard_source_date_resolution_{DATE}.json')
    candidate = load(STATUS / f'v3v4_dashboard_candidate_view_{DATE}.json')

    for label, text in bodies:
        if not text:
            blockers.append(f'{label}_html_empty')
            continue
        for token in FORBIDDEN_VISIBLE:
            if token in text:
                blockers.append(f'{label}_forbidden_visible:{token}')
        if re.search(r'候选结构</div><div class="value">[^<]*C\d+', text):
            blockers.append(f'{label}_candidate_structure_contains_c')
        if 'A级候选' not in text or 'B级候选' not in text:
            blockers.append(f'{label}_ab_candidate_groups_missing')
        if 'SKIP' not in text:
            blockers.append(f'{label}_skip_status_missing')
        if '昨日验证' not in text or '累计验证' not in text:
            blockers.append(f'{label}_compact_validation_blocks_missing')
        if 'validation-last7' in text:
            blockers.append(f'{label}_last7_dom_present')
        if 'V3 战备窗口' not in text or 'REPORT_ONLY' not in text:
            blockers.append(f'{label}_v3_or_report_only_missing')
        if '20260522' in text or '最近候选 / 数据日期 20260522' in text:
            blockers.append(f'{label}_stale_20260522_visible')
        if '今日候选' not in text:
            blockers.append(f'{label}_today_candidate_label_missing')
        for line in card_r3_lines(text):
            if any(bad in line for bad in ['强度 -', '球数 -', '剧本 -', 'HT -']):
                blockers.append(f'{label}_missing_field_rendered:{line}')
            if re.search(r'HT\s*\d+(?:\.\d+)?%', line):
                blockers.append(f'{label}_ht_rendered_as_percent:{line}')
        for line in match_lines(text):
            if re.search(r'\b[A-Za-z]{3,}\b', line):
                blockers.append(f'{label}_english_team_in_main_row:{line}')

    if validation.get('c_observation_active') is not False:
        blockers.append('validation_c_observation_active_not_false')
    if validation.get('last_7d_active') is not False:
        blockers.append('validation_last_7d_active_not_false')
    if validation.get('brief_used_for_hit_rate') is not False:
        blockers.append('brief_used_for_hit_rate')
    if validation.get('c_excluded_from_ab') is not True:
        blockers.append('c_not_excluded_from_ab')
    if not validation.get('source_files'):
        blockers.append('validation_source_files_missing')
    active = validation.get('dashboard_active', {}) if isinstance(validation.get('dashboard_active'), dict) else {}
    if set(active.keys()) != {'yesterday', 'cumulative'}:
        blockers.append(f'dashboard_active_keys_invalid:{sorted(active.keys())}')
    for key in ['yesterday', 'cumulative']:
        block = active.get(key, {}) if isinstance(active.get(key), dict) else {}
        if 'C_observation' in block:
            blockers.append(f'{key}_contains_c_observation')
        if not all(k in block for k in ['A','B','A_plus_B']):
            blockers.append(f'{key}_missing_ab_metrics')
    if build.get('C_active') is not False or build.get('c_active_in_dashboard') is not False:
        blockers.append('build_c_active_not_false')
    if build.get('last_7d_visible') is not False or build.get('c_validation_visible') is not False:
        blockers.append('build_compact_visibility_flags_not_false')
    if daily and (daily.get('C_active') is not False or daily.get('last_7d_active') is not False):
        blockers.append('daily_refresh_c_or_last7_active')
    if brief.get('brief_exists') is not True or brief.get('is_today_brief') is not True:
        blockers.append('today_brief_not_resolved')
    if source.get('scan_date') != DATE or source.get('display_label') != '今日候选':
        blockers.append('source_date_not_today_candidate')
    if int(candidate.get('A_count', -1)) != int(build.get('A', -2)) or int(candidate.get('B_count', -1)) != int(build.get('B', -2)) or int(candidate.get('SKIP_count', -1)) != int(build.get('SKIP', -2)):
        blockers.append('ab_skip_counts_do_not_match_source')
    for key in ['capture_ran','QQ_push','cloud_publish','cron_enabled','strategy_changed','v4_candidate_numbers_changed']:
        if build.get(key) is not False:
            blockers.append(f'build_{key}_not_false')

    status = 'BLOCKER' if blockers else ('WARN_ONLY' if warnings else 'PASS')
    result = {
        'checker':'tools/check_v3v4_dashboard_compact_validation_remove_c.py',
        'phase':'V3V4-DASHBOARD-VALIDATION-TWO-COLUMN-SCRIPT-HIGHLIGHT-20260523',
        'generated_at':datetime.now(TZ).isoformat(),
        'conclusion':status,
        'http_127_code':code127,
        'http_192_code':code192,
        'c_active_in_dashboard':False if not any('C级观察' in b[1] or 'C观察' in b[1] for b in bodies) else True,
        'candidate_structure':'A/B + SKIP status',
        'main_validation_blocks':['yesterday','cumulative'] if not blockers or True else [],
        'last_7d_visible':any('近7天验证' in b[1] or 'validation-last7' in b[1] for b in bodies),
        'c_validation_visible':any('C观察' in b[1] or 'C级观察' in b[1] for b in bodies),
        'c_observation_active':validation.get('c_observation_active'),
        'last_7d_active':validation.get('last_7d_active'),
        'brief_used_for_hit_rate':validation.get('brief_used_for_hit_rate'),
        'c_excluded_from_ab':validation.get('c_excluded_from_ab'),
        'ht_field_correct':not any(re.search(r'HT\s*\d+(?:\.\d+)?%', line) for line in card_r3_lines(html)),
        'strength_dash_visible':'强度 -' in html,
        'missing_fields_hidden':not any(bad in html for bad in ['强度 -','球数 -','剧本 -','HT -']),
        'brief_drives_dashboard':brief.get('is_today_brief') is True and source.get('scan_date') == DATE,
        'served_html_checked':bool(code127 == 200 or code192 == 200),
        'validation_layout': build.get('validation_layout'),
        'script_value_highlight': build.get('script_value_highlight'),
        'unknown_visible_main': build.get('unknown_visible_main'),
        'capture_ran':False,
        'QQ_push':False,
        'cloud_publish':False,
        'blockers':blockers,
        'warnings':warnings,
    }
    out = STATUS / f'check_v3v4_dashboard_compact_validation_remove_c_result_{DATE}.json'
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 1 if blockers else 0


if __name__ == '__main__':
    raise SystemExit(main())
