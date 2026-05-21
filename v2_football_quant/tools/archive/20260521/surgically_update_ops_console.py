#!/usr/bin/env python3
"""Surgically update intel_ops_console.html data, keeping original UI."""
import re, hashlib, difflib
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
HTML_FILE = WORKSPACE / "v2_football_quant" / "data" / "runtime" / "dashboard" / "intel_ops_console.html"
BRIEF_FILE = WORKSPACE / "v2_football_quant" / "data" / "daily_reports" / "v4_openclaw_brief_20260521.txt"

# Load the team CN mapper
import sys
sys.path.insert(0, str(WORKSPACE / "v2_football_quant"))
# Manual team CN map supplement for teams not in team_cn_map.py
EXTRA_CN = {
    "Al-Fayha": "费哈",
    "Penarol": "佩纳罗尔",
    "Corinthians": "科林蒂安",
    "Brondby": "布隆德比",
    "FC Copenhagen": "哥本哈根",
    "Copenhagen": "哥本哈根",
    "MOIK": "MOIK",
    "Difai Ağsu": "阿格苏迪法伊",
    "Atromitos": "阿特罗米托斯",
    "潘塞拉伊科斯": "潘塞拉伊科斯",
    "Groningen": "格罗宁根",
    "瓦迪德格拉": "瓦迪德格拉",
    "Masr": "马斯尔",
    "Al Kholood": "阿尔科洛德",
    "Al-Hazm": "阿尔哈兹姆",
    "布赖代合作": "布赖代合作",
    "Atletico-MG": "米内罗竞技",
    "Cienciano": "西恩夏诺",
    "Železničar Pančevo": "泽莱兹尼察",
    "Cukaricki": "库卡里基",
    "帕纳托利科斯": "帕纳托利科斯",
    "阿斯特拉斯特里波利斯": "特里波利斯",
    "Asteras Tripolis": "特里波利斯",
    "阿贾克斯": "阿贾克斯",
    "利雅得新月": "利雅得新月",
    "利雅得胜利": "利雅得胜利",
    "达马克": "达马克",
    "吉达联合": "吉达联合",
    "卡迪西亚": "卡迪西亚",
    "梅赫伦": "梅赫伦",
    "布鲁日": "布鲁日",
}

def to_cn(name: str) -> str:
    """Convert team name to Chinese using mapping."""
    if name in EXTRA_CN:
        return EXTRA_CN[name]
    # Try team_cn_map if available
    try:
        from engine.team_cn_map import fuzzy_match
        result = fuzzy_match(name)
        if result:
            return result
    except:
        pass
    return name

def translate_match_name(match_str: str) -> str:
    """Translate 'TeamA vs TeamB' to Chinese."""
    if ' vs ' not in match_str:
        return match_str
    parts = match_str.split(' vs ')
    home = to_cn(parts[0].strip())
    away = to_cn(parts[1].strip())
    return f'{home} vs {away}'

brief = BRIEF_FILE.read_text(encoding="utf-8")

# Parse counts from brief
a_cnt = re.search(r'A级[^\d]*(\d+)', brief).group(1)
b_cnt = re.search(r'B级[^\d]*(\d+)', brief).group(1)
c_cnt = re.search(r'C级[^\d]*(\d+)', brief).group(1)
skip_cnt = re.search(r'SKIP[^\d]*(\d+)', brief).group(1)
total_cnt = re.search(r'全量扫描[^\d]*(\d+)', brief).group(1)

# Parse B matches
b_items = []
for sec in brief.split('🟢 B级上半场达标推荐')[1:]:
    lines = sec.strip().split('\n')
    name = lines[0].strip() if len(lines) > 0 else ''
    name = translate_match_name(name)
    meta = lines[1].strip() if len(lines) > 1 else ''
    score = lines[2].strip() if len(lines) > 2 else ''
    script = lines[3].strip() if len(lines) > 3 else ''
    dist = lines[4].strip() if len(lines) > 4 else ''
    league = meta.split('·')[0].strip() if '·' in meta else ''
    kickoff = meta.split('·')[1].strip() if '·' in meta and len(meta.split('·')) > 1 else ''
    s_ht = re.search(r'HT评分\s*(\d+)', score)
    s_rate = re.search(r'HT有球率\s*(\d+)%', score)
    ht_score = s_ht.group(1) if s_ht else '0'
    ht_rate = s_rate.group(1) if s_rate else '0'
    s_script = script.replace('剧本：', '').strip()
    # Keep distribution labels: "0-15m 20%｜16-30m 50%｜31-45m 40%"
    d0 = re.search(r'0-15m\s*\d+%', dist)
    d16 = re.search(r'16-30m\s*\d+%', dist)
    d31 = re.search(r'31-45m\s*\d+%', dist)
    d0_str = d0.group(0) if d0 else ''
    d16_str = d16.group(0) if d16 else ''
    d31_str = d31.group(0) if d31 else ''
    dist_str = f'{d0_str}｜{d16_str}｜{d31_str}'
    b_items.append({'name': name, 'league': league, 'kickoff': kickoff,
                    'ht': ht_score, 'rate': ht_rate, 'script': s_script, 'dist': dist_str})

# Parse C matches (one-liner format)
c_items = []
c_sec = brief.split('👁️ C级观察池')[1].split('⚪')[0] if '👁️ C级观察池' in brief else ''
for line in c_sec.strip().split('\n'):
    if '—' in line:
        parts = line.strip().split('—')
        c_name = translate_match_name(parts[0].strip())
        c_items.append({'name': c_name, 'rest': parts[1].strip() if len(parts) > 1 else ''})

# Generate B section HTML (match original format exactly)
b_html = ''
for i, m in enumerate(b_items, 1):
    b_html += f'''  <!-- B{i} -->
  <div class="candidate-card grade-B">
    <div class="card-r1">
      <span class="cr1-time">{m['kickoff']}</span>
      <span class="cr1-sep">｜</span>
      <span class="cr1-league">{m['league']}</span>
      <span class="cr1-grade"><span class="badge bg-green">B级候选</span></span>
    </div>
    <div class="card-r2">{m['name']}</div>
    <div class="card-r3">HT{m['ht']}｜强度{m['rate']}%｜剧本：<b>{m['script']}</b></div>
    <div class="card-r4">{m['dist']}</div>
  </div>
'''

# Generate C section HTML
c_html = ''
for i, m in enumerate(c_items, 1):
    c_html += f'''  <div class="candidate-card grade-C">
    <div class="card-r1">
      <span class="cr1-time">-</span>
      <span class="cr1-sep">｜</span>
      <span class="cr1-league">-</span>
      <span class="cr1-grade"><span class="badge bg-gray">C级观察</span></span>
    </div>
    <div class="card-r2">{m['name']}</div>
    <div class="card-r3">{m['rest']}</div>
    <div class="card-detail-panel">{m['name']} · 仅观察，不是推荐</div>
  </div>
'''

# Read original HTML (already restored from cloud snapshot)
html = HTML_FILE.read_text()

# ---- Replace B section ----
b_start_marker = '<!-- ===== B组：B级候选 ·'
b_end_marker = '<!-- ===== C组：C级观察 ·'

si = html.find(b_start_marker)
ei = html.find(b_end_marker, si)

if si > -1 and ei > -1:
    old_b = html[si:ei]
    new_b = f'<!-- ===== B组：B级候选 · {b_cnt}场 ===== -->\n<details class="candidate-group group-b">\n  <summary>\n    <span>▎B级候选 · {b_cnt}场</span>\n    <span class="group-badge"><span class="badge bg-green">B级</span></span>\n    <span class="group-hint"></span>\n  </summary>\n{b_html}</details>\n'
    html = html[:si] + new_b + html[ei:]
    print(f'✅ B section: {len(b_items)} matches')
else:
    print(f'⚠️ B section not found')

# ---- Replace C section ----
c_start_marker = '<!-- ===== C组：C级观察 ·'
si = html.find(c_start_marker)
if si > -1:
    # Find next section after C
    ei = html.find('<!--', si + 30)
    ei = ei if ei > si else len(html)
    old_c = html[si:ei]
    new_c = f'<!-- ===== C组：C级观察 · {c_cnt}场 ===== -->\n<details class="candidate-group group-c">\n  <summary>\n    <span>▎C级观察 · {c_cnt}场</span>\n    <span class="group-badge"><span class="badge bg-yellow">仅观察，不是推荐</span></span>\n    <span class="group-hint"></span>\n  </summary>\n{c_html}</details>\n'
    html = html[:si] + new_c + html[ei:]
    print(f'✅ C section: {len(c_items)} matches')
else:
    print(f'⚠️ C section not found')

# ---- Replace A section ----
a_marker = 'class="candidate-group group-a"'
si = html.find(a_marker)
if si > -1:
    a_start = html.rfind('<details', 0, si)
    a_end = html.find('</details>', si) + len('</details>')
    old_a = html[a_start:a_end]
    new_a = f'<details class="candidate-group group-a">\n  <summary>\n    <span>▎A级候选 · {a_cnt}场</span>\n    <span class="group-badge"><span class="badge bg-green">A级</span></span>\n    <span class="group-hint"></span>\n  </summary>\n  <div class="candidate-card grade-A">\n    <div class="empty-state">今日无A级强推荐</div>\n  </div>\n</details>'
    html = html.replace(old_a, new_a)
    print(f'✅ A section: 今日无A级强推荐')

# ---- Replace summary counts ----
html = re.sub(r'A\d+ / B\d+ / C\d+', f'A{a_cnt} / B{len(b_items)} / C{len(c_items)}', html)

# Write
HTML_FILE.write_text(html)
print(f'\n✅ Done: {len(html)} bytes | A={a_cnt} B={len(b_items)} C={len(c_items)} SKIP={skip_cnt}')
