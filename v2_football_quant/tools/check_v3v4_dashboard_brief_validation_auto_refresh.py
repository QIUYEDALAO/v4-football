#!/usr/bin/env python3
"""Check compact dashboard brief + validation auto-refresh contract."""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "data/runtime/status"
DATE = "20260523"
TZ = timezone(timedelta(hours=8))


def load(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def main() -> int:
    blockers: list[str] = []
    warnings: list[str] = []
    dry = subprocess.run([sys.executable, 'tools/run_v3v4_intel_ops_console_daily_refresh.py', '--date', DATE, '--mode', 'dry-run', '--source-window', 'auto', '--no-capture', '--no-push', '--no-cloud', '--strict'], cwd=str(ROOT), text=True, capture_output=True, timeout=30)
    dry_json = {}
    try:
        dry_json = json.loads(dry.stdout)
    except Exception:
        blockers.append('dry_run_output_not_json')
    if dry.returncode != 0:
        blockers.append(f'dry_run_returncode:{dry.returncode}')
    compact_run = subprocess.run([sys.executable, 'tools/check_v3v4_dashboard_compact_validation_remove_c.py'], cwd=str(ROOT), text=True, capture_output=True, timeout=30)
    compact = {}
    try:
        compact = json.loads(compact_run.stdout)
    except Exception:
        compact = load(STATUS / f'check_v3v4_dashboard_compact_validation_remove_c_result_{DATE}.json')
    if compact_run.returncode != 0:
        blockers.extend(compact.get('blockers', ['compact_checker_failed']))
    warnings.extend(compact.get('warnings', []))
    brief = load(STATUS / f'v3v4_dashboard_brief_resolution_{DATE}.json')
    validation = load(STATUS / f'v3v4_validation_summary_{DATE}.json')
    build = load(STATUS / f'v3v4_dashboard_compact_validation_remove_c_obs_build_{DATE}.json')
    if brief.get('brief_exists') is not True or brief.get('is_today_brief') is not True:
        blockers.append('today_brief_not_driving_dashboard')
    for key, expected in [('A',3),('B',9),('SKIP',12)]:
        if int(brief.get(key, -1)) != expected or int(build.get(key, -1)) != expected:
            blockers.append(f'{key}_count_not_from_today_brief')
    for key, expected in [('brief_used_for_hit_rate', False), ('c_observation_active', False), ('last_7d_active', False), ('c_excluded_from_ab', True)]:
        if validation.get(key) is not expected:
            blockers.append(f'validation_{key}_not_{expected}')
    for key in ['capture_ran','QQ_push','cloud_publish','cron_enabled','strategy_changed','v4_candidate_numbers_changed']:
        if dry_json.get(key) is not False:
            blockers.append(f'dry_run_{key}_not_false')
    status = 'BLOCKER' if blockers else ('WARN_ONLY' if warnings else 'PASS')
    result = {
        'checker':'tools/check_v3v4_dashboard_brief_validation_auto_refresh.py',
        'phase':'V3V4-DASHBOARD-VALIDATION-TWO-COLUMN-SCRIPT-HIGHLIGHT-20260523',
        'generated_at':datetime.now(TZ).isoformat(),
        'conclusion':status,
        'brief_path':brief.get('brief_path'),
        'brief_exists':brief.get('brief_exists'),
        'is_today_brief':brief.get('is_today_brief'),
        'dashboard_uses_today_data':compact.get('brief_drives_dashboard'),
        'display_label':'今日候选',
        'main_validation_blocks':['yesterday','cumulative'],
        'last_7d_visible':compact.get('last_7d_visible'),
        'c_validation_visible':compact.get('c_validation_visible'),
        'validation_source_files':validation.get('source_files',[]),
        'brief_used_for_hit_rate':validation.get('brief_used_for_hit_rate'),
        'c_observation_active':validation.get('c_observation_active'),
        'last_7d_active':validation.get('last_7d_active'),
        'c_excluded_from_ab':validation.get('c_excluded_from_ab'),
        'served_html_checked':compact.get('served_html_checked'),
        'http_127_code':compact.get('http_127_code'),
        'http_192_code':compact.get('http_192_code'),
        'capture_ran':False,
        'QQ_push':False,
        'cloud_publish':False,
        'cron_enabled':False,
        'blockers':blockers,
        'warnings':warnings,
    }
    out = STATUS / f'check_v3v4_dashboard_brief_validation_auto_refresh_result_{DATE}.json'
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 1 if blockers else 0

if __name__ == '__main__':
    raise SystemExit(main())
