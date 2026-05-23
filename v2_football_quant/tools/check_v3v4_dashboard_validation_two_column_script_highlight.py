#!/usr/bin/env python3
"""Check two-column validation card and highlighted script values for V3/V4 dashboard."""
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

FORBIDDEN_VISIBLE = ["V2 active", "BET_LOCKED", "V33 active", "C级观察", "C观察", "V4 C观察", "近7天验证"]


def load(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def curl(url: str) -> tuple[int, str]:
    out = Path('/tmp/v3v4_two_column_check.html')
    try:
        r = subprocess.run(['curl','-sS','-L','--max-time','3','-w','\n%{http_code}','-o',str(out),url],cwd=str(ROOT),text=True,capture_output=True,timeout=6)
        code = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else '000'
        return int(code) if code.isdigit() else 0, out.read_text(encoding='utf-8',errors='replace') if out.exists() else ''
    except Exception:
        return 0, ''


def strip_tags(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text)


def main_part(html: str) -> str:
    return html.split('<details class="validation-audit"', 1)[0]


def card_r3(html: str) -> list[str]:
    return re.findall(r'<div class="card-r3">(.*?)</div>', html, flags=re.S)


def match_lines(html: str) -> list[str]:
    return [strip_tags(x).strip() for x in re.findall(r'<div class="match-line">(.*?)</div>', html, flags=re.S)]


def css_text(html: str) -> str:
    m = re.search(r'<style>(.*?)</style>', html, flags=re.S)
    return m.group(1) if m else ''


def check_body(label: str, text: str, blockers: list[str]) -> dict[str, Any]:
    main = main_part(text)
    css = css_text(text)
    validation_grid = 'class="validation-grid"' in text
    same_card = bool(re.search(r'<section class="panel validation-panel[^>]*>.*?<div class="validation-grid">.*?validation-yesterday.*?validation-cumulative.*?</section>', text, flags=re.S))
    y_col = 'validation-col validation-yesterday' in text
    c_col = 'validation-col validation-cumulative' in text
    row_a = bool(re.search(r"<span>A</span>\s*<b>(?:N/A|\d+/\d+ · [^<]+)</b>", text))
    row_b = bool(re.search(r"<span>B</span>\s*<b>(?:N/A|\d+/\d+ · [^<]+)</b>", text))
    row_ab = bool(re.search(r"<span>A\+B</span>\s*<b>(?:N/A|\d+/\d+ · [^<]+)</b>", text))
    reason_visible = any(token in text for token in ["赛果数据未就绪", "样本不足", "等待赛果"])
    unknown_visible_main = 'unknown' in main.lower() or 'unknown_count' in main.lower()
    script_class = 'class=\'script-value\'' in text or 'class="script-value"' in text
    script_css = '.script-value' in css and 'font-weight:800' in css and ('var(--amber)' in css or 'color:' in css)
    script_in_cards = all(('script-value' in x or '等待下一次' in strip_tags(x)) for x in card_r3(text)) and bool(card_r3(text))
    for token in FORBIDDEN_VISIBLE:
        if token in text:
            blockers.append(f'{label}_forbidden_visible:{token}')
    if not validation_grid:
        blockers.append(f'{label}_validation_grid_missing')
    if not same_card:
        blockers.append(f'{label}_validation_not_same_card')
    if not y_col:
        blockers.append(f'{label}_yesterday_column_missing')
    if not c_col:
        blockers.append(f'{label}_cumulative_column_missing')
    if not row_a or not row_b or not row_ab:
        blockers.append(f'{label}_validation_rows_missing')
    if not reason_visible:
        blockers.append(f'{label}_validation_reason_missing')
    if unknown_visible_main:
        blockers.append(f'{label}_unknown_visible_main')
    if not script_class or not script_css or not script_in_cards:
        blockers.append(f'{label}_script_value_not_highlighted')
    if '强度 -' in text:
        blockers.append(f'{label}_strength_dash_visible')
    if re.search(r'HT\s*\d+(?:\.\d+)?%', text):
        blockers.append(f'{label}_ht_percent_visible')
    if re.search(r'候选结构</div><div class="value">[^<]*C\d+', text) or 'group-C' in text:
        blockers.append(f'{label}_c_candidate_visible')
    for line in match_lines(text):
        if re.search(r'\b[A-Za-z]{3,}\b', line):
            blockers.append(f'{label}_english_team_in_main_row:{line}')
    return {
        'validation_grid': validation_grid,
        'same_card': same_card,
        'yesterday_column': y_col,
        'cumulative_column': c_col,
        'validation_rows_visible': row_a and row_b and row_ab,
        'validation_reason_visible': reason_visible,
        'unknown_visible_main': unknown_visible_main,
        'script_value_highlight': script_class and script_css and script_in_cards,
    }


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
    body_results = [check_body(label, text, blockers) for label, text in bodies if text]

    validation = load(STATUS / f'v3v4_validation_summary_{DATE}.json')
    build = load(STATUS / f'v3v4_dashboard_validation_two_column_script_highlight_build_{DATE}.json') or load(STATUS / f'v3v4_dashboard_compact_validation_remove_c_obs_build_{DATE}.json')
    active = validation.get('dashboard_active', {}) if isinstance(validation.get('dashboard_active'), dict) else {}
    if set(active.keys()) != {'yesterday', 'cumulative'}:
        blockers.append(f'dashboard_active_keys_invalid:{sorted(active.keys())}')
    for key in ['yesterday', 'cumulative']:
        block = active.get(key, {}) if isinstance(active.get(key), dict) else {}
        if 'C' in block or 'C_observation' in block or 'last_7d' in block:
            blockers.append(f'dashboard_active_{key}_contains_forbidden_key')
        if not all(k in block for k in ['A','B','A_plus_B']):
            blockers.append(f'dashboard_active_{key}_missing_ab')
    if validation.get('brief_used_for_hit_rate') is not False:
        blockers.append('brief_used_for_hit_rate')
    if validation.get('c_excluded_from_ab') is not True:
        blockers.append('c_excluded_from_ab_not_true')
    if validation.get('c_observation_active') is not False or validation.get('last_7d_active') is not False:
        blockers.append('validation_c_or_last7_active')
    if build.get('validation_layout') != 'two_column':
        blockers.append('build_validation_layout_not_two_column')
    for key in ['C_active','c_active_in_dashboard','c_validation_visible','last_7d_visible','capture_ran','QQ_push','cloud_publish','cron_enabled','strategy_changed','v4_candidate_numbers_changed']:
        if build.get(key) is not False:
            blockers.append(f'build_{key}_not_false')
    if build.get('script_value_highlight') is not True or build.get('unknown_visible_main') is not False:
        blockers.append('build_script_or_unknown_flags_invalid')

    status = 'BLOCKER' if blockers else ('WARN_ONLY' if warnings else 'PASS')
    first = body_results[0] if body_results else {}
    result = {
        'checker':'tools/check_v3v4_dashboard_validation_two_column_script_highlight.py',
        'phase':'V3V4-DASHBOARD-VALIDATION-TWO-COLUMN-SCRIPT-HIGHLIGHT-20260523',
        'generated_at':datetime.now(TZ).isoformat(),
        'conclusion':status,
        'http_127_code':code127,
        'http_192_code':code192,
        'validation_layout':'two_column' if first.get('validation_grid') else 'missing',
        'yesterday_column':first.get('yesterday_column'),
        'cumulative_column':first.get('cumulative_column'),
        'same_card':first.get('same_card'),
        'dashboard_active_has_c': any('C' in (active.get(k, {}) if isinstance(active.get(k), dict) else {}) for k in active),
        'dashboard_active_has_last_7d': 'last_7d' in active,
        'unknown_visible_main':first.get('unknown_visible_main'),
        'script_value_highlight':first.get('script_value_highlight'),
        'strength_dash_visible':'强度 -' in html,
        'ht_field_correct':not bool(re.search(r'HT\s*\d+(?:\.\d+)?%', html)),
        'candidate_structure':'A/B + SKIP status',
        'c_candidate_visible':'group-C' in html or 'C级观察' in html,
        'skip_status_only':'SKIP' in html and 'group-SKIP' not in html,
        'served_html_checked':bool(code127 == 200 or code192 == 200),
        'capture_ran':False,
        'QQ_push':False,
        'cloud_publish':False,
        'blockers':blockers,
        'warnings':warnings,
    }
    out = STATUS / f'check_v3v4_dashboard_validation_two_column_script_highlight_result_{DATE}.json'
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 1 if blockers else 0


if __name__ == '__main__':
    raise SystemExit(main())
