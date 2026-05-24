#!/usr/bin/env python3
from __future__ import annotations
import json,re
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
STATUS=ROOT/'data/runtime/status'
HTML=ROOT/'data/runtime/dashboard/intel_ops_console.html'
TZ=timezone(timedelta(hours=8))
DATE=datetime.now(TZ).strftime('%Y%m%d')


def main()->int:
    blockers=[]
    text=HTML.read_text(encoding='utf-8',errors='replace') if HTML.exists() else ''
    if not HTML.exists(): blockers.append('dashboard_html_missing')
    # Primary row should not render bare english-vs-english in match-line.
    import re
    for m in re.finditer(r'<div class=\"match-line\">([^<]+)<span>vs</span>([^<]+)</div>', text):
        left = m.group(1).strip()
        right = m.group(2).strip()
        if left.startswith('中文名缺失：') or right.startswith('中文名缺失：'):
            continue
        if re.fullmatch(r"[A-Za-z0-9 .'/&-]+", left) and re.fullmatch(r"[A-Za-z0-9 .'/&-]+", right):
            blockers.append(f'english_main_match_line:{left} vs {right}')

    out={
      'checker':'tools/check_v3v4_dashboard_team_cn_display.py',
      'phase':'V3V4-DASHBOARD-YESTERDAY-VALIDATION-VISIBILITY-HOTFIX-20260524',
      'date':DATE,
      'team_cn_main_display':len(blockers)==0,
      'blockers':blockers,
      'conclusion':'PASS' if not blockers else 'BLOCKER'
    }
    (STATUS/f'check_v3v4_dashboard_team_cn_display_result_{DATE}.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(out,ensure_ascii=False,indent=2))
    return 0 if not blockers else 2


if __name__=='__main__':
    raise SystemExit(main())
