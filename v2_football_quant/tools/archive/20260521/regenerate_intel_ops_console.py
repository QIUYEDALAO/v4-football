#!/usr/bin/env python3
"""Regenerate intel_ops_console.html from latest V4 brief + INTEL_DASHBOARD"""
import json, os, re
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
HTML_FILE = BASE / "data" / "runtime" / "dashboard" / "intel_ops_console.html"
DASHBOARD_FILE = BASE / "reports" / "intel_desk" / "INTEL_DASHBOARD_20260521.json"
BRIEF_FILE = BASE / "data" / "daily_reports" / "v4_openclaw_brief_20260521.txt"
CANDIDATE_FILE = BASE / "data" / "runtime" / "status" / "intel_desk_v4_candidate_view_20260520.json"

def load_json(path):
    try: return json.loads(Path(path).read_text())
    except: return {}

def parse_brief():
    """Parse V4 brief to extract B and C matches"""
    text = Path(BRIEF_FILE).read_text() if BRIEF_FILE.exists() else ""
    b_matches, c_matches = [], []
    lines = text.split('\n')
    i = 0
    while i < len(lines):
        line = lines[i]
        bm = re.match(r'🟢 B级上半场达标推荐\n(.+)', lines[i] + '\n' + (lines[i+1] if i+1 < len(lines) else ''))
        # Check for B match pattern
        if line.startswith('🟢 B级上半场达标推荐'):
            i += 1
            name = lines[i].strip() if i < len(lines) else ""
            i += 1
            meta = lines[i].strip() if i < len(lines) else ""
            i += 1
            score_line = lines[i].strip() if i < len(lines) else ""
            i += 1
            script_line = lines[i].strip() if i < len(lines) else ""
            i += 1
            dist_line = lines[i].strip() if i < len(lines) else ""
            reason_line = lines[i+1].strip() if i+1 < len(lines) else ""
            risk_line = lines[i+2].strip() if i+2 < len(lines) else ""
            league = ""
            kickoff = ""
            if '·' in meta:
                parts = meta.split('·')
                if len(parts) >= 2:
                    league = parts[0].strip()
                    kickoff = parts[1].strip()
            ht_score = ""
            ht_rate = ""
            if 'HT评分' in score_line:
                s = re.search(r'HT评分\s*(\d+)', score_line)
                if s: ht_score = s.group(1)
            if 'HT有球率' in score_line:
                s = re.search(r'HT有球率\s*(\d+)%', score_line)
                if s: ht_rate = s.group(1)
            
            # Parse bins
            bins_0_15 = re.search(r'0-15m\s*(\d+)%', dist_line)
            bins_16_30 = re.search(r'16-30m\s*(\d+)%', dist_line)
            bins_31_45 = re.search(r'31-45m\s*(\d+)%', dist_line)
            
            b_matches.append({
                'name': name,
                'league': league,
                'kickoff': kickoff,
                'ht_score': f"HT{ht_score}" if ht_score else '',
                'ht_rate': f"{ht_rate}%" if ht_rate else '',
                'script': script_line.replace('剧本：', '').strip(),
                'dist_0_15': bins_0_15.group(1) if bins_0_15 else '0',
                'dist_16_30': bins_16_30.group(1) if bins_16_30 else '0',
                'dist_31_45': bins_31_45.group(1) if bins_31_45 else '0',
            })
        elif line.startswith('👁️ C级观察池'):
            c_text = lines[i] if i < len(lines) else ""
            i += 1
            while i < len(lines) and not line.startswith('📌') and not line.startswith('⚪'):
               c_line = lines[i].strip()
               if c_line and not c_line.startswith('━') and not c_line.startswith('📌') and not c_line.startswith('⚪') and not c_line.startswith('#'):
                   parts = c_line.split('—')
                   if len(parts) == 2:
                       name = parts[0].strip()
                       rest = parts[1].strip()
                       c_matches.append({'name': name, 'rest': rest})
               i += 1
            continue
        i += 1
    return b_matches, c_matches

# Load data
dash = load_json(DASHBOARD_FILE)
v4 = dash.get('v4_today', {})
b_list, c_list = parse_brief()

# Candidate view data
cv = load_json(CANDIDATE_FILE)
a_count = cv.get('A_count', v4.get('A_count', 0))
b_count = len(b_list) or v4.get('B_count', 6)
c_count = len(c_list) or v4.get('C_count', 9)
skip_count = v4.get('SKIP_count', 4)
total = v4.get('total_matches', max(int(a_count)+int(b_count)+int(c_count)+int(skip_count), 19))

# B card HTML
b_html = ""
for idx, m in enumerate(b_list, 1):
    b_html += f'''
<div class="candidate-card grade-B">
  <div class="cl">{m['league']} · {m['kickoff']}</div>
  <div class="cn">{m['name']}</div>
  <div class="ch">{m['ht_score']} | {m['ht_rate']} | {m['script']}</div>
  <div class="cd">0-15m {m['dist_0_15']}% | 16-30m {m['dist_16_30']}% | 31-45m {m['dist_31_45']}%</div>
</div>'''

# C card HTML
c_html = ""
for idx, m in enumerate(c_list, 1):
    c_html += f'<div class="no-card">C{idx} · {m["name"]} — {m["rest"]}</div>'

# Generate full HTML
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
.footer{{text-align:center;margin:16px 0;font-size:10px;color:#556}}
</style></head><body>
<div class="logo">V2/V4 情报决策总台</div>
<div class="tagline">今日扫描已完成 · A{a_count}/B{b_count}/C{c_count}/SKIP{skip_count} · {total}场</div>

<h2>🔥 A级上半场强推荐</h2>
<div class="card"><div class="m" style="color:#667">今日无A级强推荐</div></div>

<h2>🟢 B级上半场达标推荐 · {b_count}场</h2>
{b_html if b_html else '<div class="card"><div class="m">无B级推荐</div></div>'}

<h2>👁️ C级观察池 · {c_count}场（仅观察，不作为推荐）</h2>
{c_html if c_html else '<div class="card"><div class="m">无C级观察</div></div>'}

<h2>⚪ SKIP跳过 · {skip_count}场</h2>
<div class="card"><div class="m">HT有球率不足/回调适配偏弱/评分不足</div></div>

<div class="footer">
生成: {dash.get('generated_at', '2026-05-21')} | V4_QQ_ENABLED=false | actual_send=false<br>
数据来源: V4简报(PRIMARY) | A={a_count} B={b_count} C={c_count} SKIP={skip_count}
</div>
</body></html>'''

Path(HTML_FILE).write_text(html)
print(f"✅ intel_ops_console.html regenerated ({len(html)} bytes)")
print(f"A={a_count} B={b_count} C={c_count} SKIP={skip_count}")
print(f"B matches: {len(b_list)} C matches: {len(c_list)}")
