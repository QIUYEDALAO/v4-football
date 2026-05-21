#!/usr/bin/env python3
"""Generate intel_ops_console.html from V4 brief + INTEL_DASHBOARD — full page"""
import json, re, hashlib
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
# Use workspace-level paths
WORKSPACE = BASE
DASHBOARD_JSON = WORKSPACE / "v2_football_quant" / "reports" / "intel_desk" / "INTEL_DASHBOARD_20260521.json"
BRIEF_FILE = WORKSPACE / "v2_football_quant" / "data" / "daily_reports" / "v4_openclaw_brief_20260521.txt"
OUTPUT_HTML = WORKSPACE / "v2_football_quant" / "data" / "runtime" / "dashboard" / "intel_ops_console.html"

brief = BRIEF_FILE.read_text(encoding="utf-8")

# Parse counts
a_cnt = re.search(r'A级[^\d]*(\d+)', brief).group(1)
b_cnt = re.search(r'B级[^\d]*(\d+)', brief).group(1)
c_cnt = re.search(r'C级[^\d]*(\d+)', brief).group(1)
skip_cnt = re.search(r'SKIP[^\d]*(\d+)', brief).group(1)
total_cnt = re.search(r'全量扫描[^\d]*(\d+)', brief).group(1)

# Parse B matches
b_items = []
for sec in brief.split('🟢 B级上半场达标推荐')[1:]:
    lines = sec.strip().split('\n')
    name = lines[0].strip() if lines else ''
    meta = lines[1].strip() if len(lines) > 1 else ''
    score = lines[2].strip() if len(lines) > 2 else ''
    script = lines[3].strip() if len(lines) > 3 else ''
    dist = lines[4].strip() if len(lines) > 4 else ''
    league = meta.split('·')[0].strip() if '·' in meta else ''
    kickoff = meta.split('·')[1].strip() if '·' in meta and len(meta.split('·')) > 1 else ''
    s_ht = re.search(r'HT评分\s*(\d+)', score)
    s_rate = re.search(r'HT有球率\s*(\d+)%', score)
    ht_score = f"HT{s_ht.group(1)}" if s_ht else ''
    ht_rate = f"{s_rate.group(1)}%" if s_rate else ''
    s_script = script.replace('剧本：', '').strip() if script else ''
    d0 = re.search(r'0-15m\s*(\d+)%', dist)
    d16 = re.search(r'16-30m\s*(\d+)%', dist)
    d31 = re.search(r'31-45m\s*(\d+)%', dist)
    b_items.append({'name': name, 'league': league, 'kickoff': kickoff, 'ht': ht_score, 'rate': ht_rate, 'script': s_script, 'd0': d0.group(1) if d0 else '0', 'd16': d16.group(1) if d16 else '0', 'd31': d31.group(1) if d31 else '0'})

# Parse C matches
c_items = []
c_sec = brief.split('👁️ C级观察池')[1].split('⚪')[0] if '👁️ C级观察池' in brief else ''
for line in c_sec.strip().split('\n'):
    if '—' in line:
        parts = line.strip().split('—')
        c_items.append({'name': parts[0].strip(), 'rest': parts[1].strip() if len(parts) > 1 else ''})

b_html = ''
for i, m in enumerate(b_items, 1):
    b_html += f'''
<div class="candidate-card grade-B">
  <div class="cl">{m['league']} · {m['kickoff']}</div>
  <div class="cn">{m['name']}</div>
  <div class="ch">{m['ht']} | {m['rate']} | {m['script']}</div>
  <div class="cd">0-15m {m['d0']}% | 16-30m {m['d16']}% | 31-45m {m['d31']}%</div>
</div>'''

c_html = ''
for i, m in enumerate(c_items, 1):
    c_html += f'<div class="no-card">C{i} · {m["name"]} — {m["rest"]}</div>'

source_hash = hashlib.md5(brief.encode()).hexdigest()[:12]

html = f'''<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta http-equiv="Cache-Control" content="no-store,no-cache,must-revalidate">
<title>V2/V4 情报决策总台</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,sans-serif;background:#0c1220;color:#e0e0e0;padding:8px;max-width:540px;margin:0 auto}}
.logo{{font-size:15px;color:#4fc3f7;font-weight:700;margin:4px 0 2px}}
.tagline{{font-size:10px;color:#667;margin-bottom:6px}}
h2{{font-size:13px;color:#4fc3f7;margin:8px 0 2px;border-bottom:1px solid #1a2a3a;padding-bottom:2px}}
.card{{background:#111a2a;border-radius:8px;padding:8px;margin:4px 0;font-size:12px}}
.r{{display:flex;justify-content:space-between;padding:2px 0}}
.l{{color:#8899aa}}.v{{color:#e0e0e0}}
.t{{display:inline-block;padding:1px 5px;border-radius:3px;font-size:10px;margin:1px}}
.g{{background:#1a3a1a;color:#4caf50}}.y{{background:#3a3a1a;color:#ff9800}}.n{{background:#1a2a3a;color:#8899aa}}
.m{{font-size:10px;color:#556}}.m2{{font-size:11px;color:#4fc3f7;margin:2px 0}}
.candidate-card{{background:#0d1a2a;border:1px solid #1a3a3a;border-radius:8px;padding:8px 10px;margin:6px 0;font-size:12px}}
.candidate-card .cl{{font-size:10px;color:#4fc3f7;font-weight:700;margin-bottom:2px}}
.candidate-card .cn{{font-size:13px;color:#fff;font-weight:600;margin-bottom:1px}}
.candidate-card .ch{{font-size:10px;color:#8899aa}}
.candidate-card .cd{{font-size:10px;color:#ff9800;margin-top:2px}}
.grade-A{{border-color:#4caf50}}
.grade-B{{border-color:#2196f3}}
.no-card{{background:#0c1a22;border-radius:4px;padding:4px 6px;margin:2px 0;font-size:10px;color:#8899aa}}
.footer{{text-align:center;margin:16px 0 8px;font-size:10px;color:#556}}
.source{{font-size:9px;color:#445;text-align:center;margin-bottom:8px}}
</style></head>
<body>
<div class="logo">V2/V4 情报决策总台</div>
<div class="tagline">今日扫描 已完成 · A{a_cnt} / B{b_cnt} / C{c_cnt} / SKIP{skip_cnt} · {total_cnt}场</div>

<h2>🔥 A级上半场强推荐</h2>
<div class="card"><div class="m" style="color:#667">今日无A级强推荐</div></div>

<h2>🟢 B级上半场达标推荐 · {b_cnt}场</h2>
{b_html if b_html else '<div class="card"><div class="m">无B级推荐</div></div>'}

<h2>👁️ C级观察池 · {c_cnt}场（仅观察，不作为推荐）</h2>
{c_html if c_html else '<div class="card"><div class="m">无C级观察</div></div>'}

<h2>⚪ HT_SKIP跳过 · {skip_cnt}场</h2>
<div class="card"><div class="m">HT有球率不足 · 回调适配偏弱 · 11-45分钟压力不足</div></div>

<div class="footer">
生成: 2026-05-21T13:42+08:00 | V4_QQ_ENABLED=false | actual_send=false<br>
数据来源: V4简报 midday 窗口 | source_hash={source_hash}
</div>
</body>
</html>'''

OUTPUT_HTML.write_text(html)
print(f"✅ Generated: {len(html)} bytes")
print(f"A={a_cnt} B={b_cnt} C={c_cnt} SKIP={skip_cnt} total={total_cnt}")
print(f"B items: {len(b_items)} C items: {len(c_items)}")
