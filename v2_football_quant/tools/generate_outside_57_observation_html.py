#!/usr/bin/env python3
"""Generate outside-57 observation HTML page for Web display."""
from __future__ import annotations
import argparse, json, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "data/runtime/status"
DASHBOARD = ROOT / "data/runtime/dashboard"
TZ = timezone(timedelta(hours=8))

POOL_PATH = STATUS / "v4_outside_57_observation_pool_20260525.json"

HTML_HEAD = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<title>57联赛外观察池</title>
<style>
*{box-sizing:border-box}
body{margin:0;background:#0a0e17;color:#d0d8e0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;padding:12px;max-width:800px;margin-inline:auto;line-height:1.4}
h1{font-size:20px;margin:0 0 2px;color:#f0f4f8}
.badge{display:inline-block;font-size:10px;padding:2px 6px;border-radius:4px;margin-left:6px;vertical-align:middle}
.badge-warn{background:#5a3a00;color:#ffc107}
.badge-info{background:#003056;color:#6cb4ee}
.sub{color:#8899aa;font-size:12px;margin:2px 0 12px}
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin-bottom:14px}
.stat-card{background:#121a2a;border-radius:8px;padding:8px;text-align:center}
.stat-card .num{font-size:22px;font-weight:700}
.stat-card .lbl{font-size:11px;color:#8899aa;margin-top:2px}
.stat-A .num{color:#f05555}
.stat-B .num{color:#f2a640}
.stat-C .num{color:#8899aa}
.stat-SKIP .num{color:#556677}
.match{background:#121a2a;border-radius:8px;padding:10px;margin-bottom:8px}
.match-row{display:grid;grid-template-columns:auto auto 1fr auto;gap:6px;align-items:center}
.grade{font-size:13px;font-weight:700;padding:2px 6px;border-radius:4px;width:30px;text-align:center}
.grade-A{background:#5a1111;color:#ff6666}
.grade-B{background:#5a3a00;color:#f2a640}
.grade-C{background:#1a2a3a;color:#8899aa}
.grade-SKIP{background:#0a121a;color:#556677}
.league{font-size:11px;color:#667788}
.team{font-size:14px;font-weight:600}
.ht-score{font-size:12px;color:#aabbcc}
.detail{font-size:11px;color:#667788;margin-top:4px;display:grid;grid-template-columns:1fr 1fr;gap:2px}
.detail span{color:#8899aa}
.empty{padding:20px;text-align:center;color:#556677;font-size:14px}
.footer{margin-top:16px;padding:8px;border-top:1px solid #1a2a3a;font-size:11px;color:#556677;text-align:center}
</style>
</head>
<body>
"""

def generate_html(pool: dict) -> str:
    parts = [HTML_HEAD]
    # Title
    parts.append('<h1>57联赛外观察池</h1>')
    parts.append('<div><span class="badge badge-warn">非正式推荐</span><span class="badge badge-info">不自动下注</span><span class="badge badge-info">不进QQ</span></div>')
    parts.append(f'<p class="sub">仅观察，不进入正式推荐 | 数据日期 {pool.get("date","?")}</p>')
    
    # Stats
    a = pool.get('A_count', 0)
    b = pool.get('B_count', 0)
    c = pool.get('C_count', 0)
    s = pool.get('SKIP_count', 0)
    parts.append(f'''<div class="stats">
      <div class="stat-card stat-A"><div class="num">{a}</div><div class="lbl">A级强推荐</div></div>
      <div class="stat-card stat-B"><div class="num">{b}</div><div class="lbl">B级达标推荐</div></div>
      <div class="stat-card stat-C"><div class="num">{c}</div><div class="lbl">C级观察</div></div>
      <div class="stat-card stat-SKIP"><div class="num">{s}</div><div class="lbl">SKIP跳过</div></div>
    </div>''')
    
    # Matches
    fixtures = pool.get('fixtures', [])
    if not fixtures:
        parts.append('<div class="empty">今日无57联赛外比赛或扫描尚未包含57外联赛<br><small>页面框架已就绪，待扩展扫描范围后自动填充</small></div>')
    else:
        for m in fixtures:
            g = m.get('grade', 'SKIP')
            parts.append(f'''<div class="match">
              <div class="match-row">
                <div class="grade grade-{g}">{g}</div>
                <div class="league">{m.get('league','?')}</div>
                <div class="team">{m.get('home','?')} vs {m.get('away','?')}</div>
                <div class="ht-score">HT{m.get('ht_score','?')}</div>
              </div>
              <div class="detail">
                <div><span>开赛:</span> {m.get('kickoff','?')}</div>
                <div><span>HT分:</span> {m.get('ht_live_over','?')}</div>
                <div><span>剧本:</span> {m.get('script','?')}</div>
                <div><span>盘口:</span> {m.get('line_status','盘口待补')}</div>
                <div><span>夹具ID:</span> {m.get('fixture_id','?')}</div>
                <div><span>Paper:</span> {m.get('paper_status','未赛')}</div>
              </div>
            </div>''')
    
    parts.append(f'<div class="footer">仅观察 · 非正式推荐 · 不自动下注 · 不进QQ<br>生成时间: {pool.get("generated_at","?")}</div>')
    parts.append('</body></html>')
    return '\n'.join(parts)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=None)
    parser.add_argument("--mode", choices=["dry-run", "apply"], default="dry-run")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    
    pool = json.loads(POOL_PATH.read_text()) if POOL_PATH.exists() else {
        'date': args.date or 'unknown',
        'total_outside_matches': 0, 'A_count': 0, 'B_count': 0, 'C_count': 0, 'SKIP_count': 0,
        'fixtures': [], 'official_included': False, 'qq_push': False, 'real_bet': False,
        'note': 'Pool not generated yet'
    }
    
    html = generate_html(pool)
    
    if args.mode == "apply":
        out = DASHBOARD / "outside_57_observation.html"
        out.write_text(html, encoding="utf-8")
        print(f"✅ Written: {out} ({len(html)} bytes)")
    else:
        print(f"DRY-RUN: would write {len(html)} bytes to outside_57_observation.html")
    
    print(json.dumps({
        'date': pool.get('date'),
        'outside_matches': pool.get('total_outside_matches', 0),
        'A': pool.get('A_count', 0), 'B': pool.get('B_count', 0),
        'C': pool.get('C_count', 0), 'SKIP': pool.get('SKIP_count', 0),
        'official_included': False, 'qq_push': False, 'real_bet': False,
        'non_official_banner': True, 'mode': args.mode,
    }, indent=2))


if __name__ == "__main__":
    raise SystemExit(main())
