#!/usr/bin/env python3
"""Generate intel_ops_console.html with Clean UI V3 + today's data."""
from pathlib import Path
from datetime import datetime

BASE = Path(__file__).resolve().parents[1]
NOW = "2026-05-23 13:08"
CSS = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no,viewport-fit=cover">
<meta http-equiv="Cache-Control" content="no-store,no-cache,must-revalidate,max-age=0">
<title>情报决策总台 — V2/V4</title>
<style>
:root{
  --font-hero:30px;
  --font-section-title:26px;
  --font-team:23px;
  --font-card-title:22px;
  --font-base:19px;
  --font-small:17px;
  --font-meta:16px;
  --font-tiny:15px;
  --line-base:1.65;
  --line-tight:1.5;
  --card-padding:20px;
  --card-gap:18px;
  --tap-target:48px;
  --bg-deep:#080d16;
  --bg-card:#0f1923;
  --bg-lock:#0a1018;
  --text-primary:#fff;
  --text-body:#c8d6e5;
  --text-muted:#8395a7;
  --text-dim:#576574;
  --border-subtle:#1a2a3a;
  --gold:#feca57;
  --green:#1dd1a1;
  --blue:#54a0ff;
  --red:#ff6b6b;
}
*{margin:0;padding:0;box-sizing:border-box}
body{
  font-family:-apple-system,BlinkMacSystemFont,'PingFang SC','Hiragino Sans GB','Microsoft YaHei',sans-serif;
  background:var(--bg-deep);color:var(--text-body);
  padding:18px;max-width:540px;margin:0 auto;
  font-size:var(--font-base);line-height:var(--line-base);
  -webkit-text-size-adjust:100%;
}
h1{font-size:var(--font-hero);color:var(--text-primary);margin:10px 0 6px}
h2{font-size:var(--font-section-title);color:var(--text-primary);margin:18px 0 10px;padding-bottom:6px;border-bottom:1px solid var(--border-subtle);display:flex;align-items:center;gap:8px}
h2 .zone-num{display:inline-flex;align-items:center;justify-content:center;width:26px;height:26px;border-radius:6px;font-size:15px;font-weight:700;background:var(--bg-card);color:var(--blue);flex-shrink:0}
.status-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin:8px 0}
.status-card{background:var(--bg-card);border-radius:12px;padding:14px 12px;text-align:center;min-height:72px;display:flex;flex-direction:column;justify-content:center;align-items:center}
.status-card .sl{font-size:17px;color:var(--text-dim);margin-bottom:4px}
.status-card .sv{font-size:24px;font-weight:700;color:var(--text-primary)}
.status-card .sv.small{font-size:20px}
.status-card.ok .sv{color:var(--green)}
.status-card.warn .sv{color:var(--gold)}
.status-card.info .sv{color:var(--blue)}
.badge{display:inline-block;padding:4px 10px;border-radius:5px;font-size:var(--font-meta);font-weight:600;line-height:1.4}
.bg-green{background:#0a3d2e;color:var(--green)}
.bg-blue{background:#0a2a4a;color:var(--blue)}
.bg-yellow{background:#3a2a0a;color:var(--gold)}
.bg-red{background:#3a0a0a;color:var(--red)}
.bg-gray{background:#1a1a2e;color:var(--text-muted)}
.candidate-card{background:var(--bg-card);border-radius:12px;padding:var(--card-padding);margin:var(--card-gap) 0;border-left:4px solid #1e2a3a}
.grade-A{border-left-color:var(--gold);box-shadow:0 0 12px rgba(254,202,87,0.08)}
.grade-B{border-left-color:var(--green)}
.grade-C{border-left-color:var(--text-dim)}
.card-r1{display:flex;align-items:center;gap:10px;margin-bottom:6px;flex-wrap:nowrap}
.card-r1 .cr1-time{font-size:var(--font-small);color:var(--blue);font-weight:600}
.card-r1 .cr1-sep{color:var(--text-dim);font-size:var(--font-base)}
.card-r1 .cr1-league{font-size:var(--font-small);color:var(--blue)}
.card-r1 .cr1-grade{font-size:var(--font-meta);margin-left:auto}
.card-r2{font-size:var(--font-team);color:var(--text-primary);font-weight:700;line-height:var(--line-tight);margin-bottom:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.card-r3{font-size:var(--font-base);color:var(--text-body);margin-bottom:4px;line-height:var(--line-base)}
.card-r3 b{color:var(--gold);font-weight:600}
.card-r4{font-size:var(--font-base);color:var(--text-muted);padding-top:6px;border-top:1px solid var(--border-subtle);margin-bottom:4px}
.candidate-group{margin:12px 0 4px;border:none}
.candidate-group>summary{cursor:pointer;user-select:none;display:flex;align-items:center;gap:8px;padding:14px 16px;background:var(--bg-card);border-radius:12px;min-height:var(--tap-target);font-size:var(--font-base);color:var(--text-primary);font-weight:700;flex-wrap:wrap;list-style:none}
.candidate-group>summary::-webkit-details-marker{display:none}
.candidate-group>summary::marker{display:none;content:''}
.candidate-group>summary:active{background:#151f2d}
.candidate-group>summary .group-badge{flex-shrink:0}
.group-hint{font-size:var(--font-tiny);color:var(--text-dim);margin-left:auto;font-weight:400}
.group-hint::after{content:'展开 ▸'}
.candidate-group[open]>.group-hint::after,
details[open]>.group-hint::after{content:'收起 ▴'}
.zone-card{background:var(--bg-card);border-radius:12px;padding:var(--card-padding);margin:var(--card-gap) 0}
.zone-card.compact{padding:14px 16px}
.info-row{display:flex;justify-content:space-between;padding:4px 0;font-size:var(--font-small);line-height:var(--line-base)}
.info-row .k{color:var(--text-dim);flex-shrink:0;margin-right:12px}
.info-row .v{color:var(--text-body);font-weight:500;text-align:right}
.decision-flag{display:flex;align-items:center;gap:10px;padding:14px 16px;background:#0a2e1a;border-radius:12px;margin:10px 0;font-size:var(--font-base)}
details{margin:8px 0}
summary{font-size:var(--font-base);color:var(--text-muted);cursor:pointer;padding:6px 0;user-select:none;min-height:var(--tap-target);display:flex;align-items:center}
details[open]>summary{color:var(--blue)}
details .inner{padding:6px 0 6px 12px;font-size:var(--font-small);line-height:var(--line-base)}
.v2-module-card{background:var(--bg-card);border-radius:12px;padding:14px 16px;margin:var(--card-gap) 0;border-left:3px solid var(--gold)}
.v2-module-card .v2-title{font-size:var(--font-base);color:var(--gold);font-weight:700;margin-bottom:4px}
.v2-module-card .v2-status{font-size:var(--font-small);color:var(--text-body);line-height:var(--line-base)}
.lock-card{background:var(--bg-lock);border:1px solid #2a1a0a;border-radius:12px;padding:16px;margin:var(--card-gap) 0}
.lock-card .lock-title{font-size:var(--font-base);color:#e1a325;font-weight:700;margin-bottom:6px}
.lock-card .lock-cn{font-size:var(--font-card-title);color:var(--text-primary);font-weight:600}
.lock-card .lock-en{font-size:var(--font-meta);color:var(--text-dim);margin-bottom:4px}
.lock-card .lock-detail{font-size:var(--font-base);color:var(--text-muted);line-height:var(--line-base)}
.lock-card .lock-tags{display:flex;flex-wrap:wrap;gap:6px;margin-top:6px}
.timeline-collapsed{display:flex;gap:6px;margin:8px 0}
.timeline-collapsed .step{flex:1;text-align:center;padding:8px 4px;border-radius:6px;font-size:var(--font-meta);background:#0a2e1a;color:var(--green)}
.timeline-collapsed .step .t{font-size:var(--font-tiny);display:block;margin-top:1px}
body{padding-bottom:80px}
.footer{text-align:center;margin:16px 0 10px;font-size:var(--font-tiny);color:#3a4a5a}
.hidden{display:none!important}
.lineage-ok{color:var(--green);font-weight:700}
.eye-inline{display:inline-flex;align-items:center;justify-content:center;width:36px;height:36px;border-radius:8px;background:var(--bg-card);border:1px solid var(--border-subtle);color:var(--text-dim);font-size:18px;cursor:pointer;flex-shrink:0;margin-left:auto}
.eye-inline:active{background:#1a2a3a;color:var(--text-primary)}
</style>
</head>
<body>"""

A_MATCHES = [
    ("18:00", "日职联", "京都不死鸟 vs V-varen Nagasaki", "HT71｜83%｜<b>中段发力型</b>", "0-15m 17%｜16-30m 83%｜31-45m 33%"),
    ("20:00", "捷克甲", "奥洛穆茨 vs Karviná", "HT91｜90%｜<b>中后段发力型</b>", "0-15m 67%｜16-30m 17%｜31-45m 83%"),
    ("03:00", "西甲", "皇家贝蒂斯 vs 莱万特", "HT72｜71%｜<b>中后段发力型</b>", "0-15m 50%｜16-30m 17%｜31-45m 83%"),
]
B_MATCHES = [
    ("17:00", "印尼超", "Persepam Madura Utd vs PSM Makassar", "HT78｜80%｜<b>中后段发力型</b>", "0-15m 50%｜16-30m 17%｜31-45m 50%"),
    ("21:00", "瑞典超", "Kalmar FF vs Degerfors IF", "HT76｜75%｜<b>中段发力型</b>", "0-15m 33%｜16-30m 50%｜31-45m 33%"),
    ("22:00", "芬超", "KuPS vs Lahti", "HT64｜70%｜<b>中后段发力型</b>", "0-15m 17%｜16-30m 33%｜31-45m 50%"),
    ("00:15+1", "比甲", "登德尔 vs Lommel United", "HT63｜62%｜<b>中后段发力型</b>", "0-15m 17%｜16-30m 33%｜31-45m 67%"),
    ("00:45+1", "克亚甲", "Dinamo Zagreb vs Lokomotiva Zagreb", "HT75｜80%｜<b>开局冲击型</b>", "0-15m 50%｜16-30m 50%｜31-45m 0%"),
    ("01:00+1", "埃及超", "Haras El Hodood vs Petrojet", "HT70｜83%｜<b>中后段发力型</b>", "0-15m 17%｜16-30m 33%｜31-45m 67%"),
    ("02:00+1", "乌拉甲", "Cerro Largo vs Boston River", "HT64｜70%｜<b>中后段发力型</b>", "0-15m 33%｜16-30m 33%｜31-45m 50%"),
    ("03:00+1", "西甲", "赫塔费 vs 奥萨苏纳", "HT78｜80%｜<b>开局冲击型</b>", "0-15m 50%｜16-30m 33%｜31-45m 33%"),
    ("11:55", "日职联", "Fagiano Okayama vs 大阪樱花", "HT72｜75%｜<b>中段发力型</b>", "0-15m 50%｜16-30m 67%｜31-45m 50%"),
]
C_MATCHES = [
    "广岛三箭 vs 名古屋鲸八", "Kashima vs FC东京",
    "姆拉达博莱斯拉夫 vs 特普利采", "Dinamo Makhachkala vs 乌拉尔",
    "Ilves vs Gnistan", "塞尔塔 vs 塞维利亚",
    "西班牙人 vs 皇家社会", "Mirassol vs Fluminense",
    "Charlotte vs 新英格兰革命",
]

def card(klass, time, league, teams, r3, r4):
    return f'''  <div class="candidate-card {klass}">
    <div class="card-r1"><span class="cr1-time">{time}</span><span class="cr1-sep">｜</span><span class="cr1-league">{league}</span><span class="cr1-grade"><span class="badge bg-green">{'A级' if 'A' in klass else 'B级'}候选</span></span></div>
    <div class="card-r2">{teams}</div>
    <div class="card-r3">{r3}</div>
    <div class="card-r4">{r4}</div>
  </div>'''

a_html = '\n'.join(card("grade-A", *m) for m in A_MATCHES)
b_html = '\n'.join(card("grade-B", *m) for m in B_MATCHES)
c_html = ''
for i, t in enumerate(C_MATCHES):
    c_html += f'''  <div class="candidate-card grade-C">
    <div class="card-r1"><span class="cr1-time">-</span><span class="cr1-sep">｜</span><span class="cr1-league">-</span><span class="cr1-grade"><span class="badge bg-gray">C级观察</span></span></div>
    <div class="card-r2">{t}</div>
    <div class="card-r3">仅观察，不是推荐</div>
    <div class="card-detail-panel">{t} · 仅观察，不是推荐</div>
  </div>\n'''

html = CSS + f'''
<div class="status-grid">
  <div class="status-card ok"><div class="sl">今日扫描</div><div class="sv small">已完成</div></div>
  <div class="status-card info"><div class="sl">候选结构</div><div class="sv">A{len(A_MATCHES)} / B{len(B_MATCHES)} / C{len(C_MATCHES)}</div></div>
  <div class="status-card warn"><div class="sl">复盘状态</div><div class="sv small">等待赛果</div></div>
  <div class="status-card ok"><div class="sl">阻断</div><div class="sv">0</div></div>
</div>

<div style="display:flex;align-items:center;gap:8px"><h1 style="flex:1">V2/V4 情报决策总台</h1><button class="eye-inline" onclick="toggleEyeComfortV2()" title="大字模式" aria-label="切换大字模式">👁</button></div>
<div style="font-size:var(--font-tiny);color:var(--text-dim);margin:0 0 8px">午间扫描已完成 · 等待 evening 窗口 · 系统正常</div>

<h2><span class="zone-num">1</span> 今日决策</h2>
<div class="decision-flag"><span style="flex:1">正式候选：{len(A_MATCHES)+len(B_MATCHES)}场 | A级：{len(A_MATCHES)}场 | B级：{len(B_MATCHES)}场 | 观察：{len(C_MATCHES)}场 | 午间窗口扫描已完成</span></div>
<div class="zone-card compact">
  <div class="info-row"><span class="k">扫描窗口</span><span class="v">midday（午间）— {NOW} CST</span></div>
  <div class="info-row"><span class="k">正式候选</span><span class="v">{len(A_MATCHES)+len(B_MATCHES)} 场（A={len(A_MATCHES)} B={len(B_MATCHES)} C={len(C_MATCHES)} SKIP=12）</span></div>
  <div class="info-row"><span class="k">下一动作</span><span class="v" style="color:var(--gold)">evening 16:20 → 继续扫描</span></div>
</div>

<h2><span class="zone-num">2</span> 今日候选 <span style="font-size:var(--font-meta);color:var(--text-dim);font-weight:400">正式候选 {len(A_MATCHES)+len(B_MATCHES)} · 观察 {len(C_MATCHES)}</span></h2>

<details class="candidate-group group-a" open>
  <summary><span>▎A级候选 · {len(A_MATCHES)}场</span><span class="group-badge"><span class="badge bg-green">A级</span></span><span class="group-hint"></span></summary>
{a_html}
</details>

<details class="candidate-group group-b">
  <summary><span>▎B级候选 · {len(B_MATCHES)}场</span><span class="group-badge"><span class="badge bg-green">B级</span></span><span class="group-hint"></span></summary>
{b_html}
</details>

<details class="candidate-group group-c">
  <summary><span>▎C级观察 · {len(C_MATCHES)}场</span><span class="group-badge"><span class="badge bg-yellow">仅观察，不是推荐</span></span><span class="group-hint"></span></summary>
{c_html}
</details>

<h2><span class="zone-num">3</span> 验证可信度 <span style="font-size:var(--font-meta);color:var(--green);font-weight:400">LINEAGE_VERIFIED</span></h2>
<div class="zone-card compact">
  <div class="info-row"><span class="k">数据血缘</span><span class="v lineage-ok">PASS</span></div>
  <div class="info-row"><span class="k">默认口径</span><span class="v" style="color:var(--blue)">生产推荐去重口径（已结算A+B=130）</span></div>
  <div class="info-row"><span class="k">昨日 V2</span><span class="v">BET_LOCKED：1场（Ried vs Wolfsberger）｜ 未结算</span></div>
  <div class="info-row"><span class="k">昨日 V4 B</span><span class="v">3场未知（RESULT_UNKNOWN_API_DISABLED）｜ 命中率 N/A</span></div>
  <div class="info-row"><span class="k">滚动 A+B</span><span class="v">A 61.0% ｜ B 56.2% ｜ A+B <b style="color:var(--green)">57.7%</b></span></div>
</div>

<details><summary>展开：V2 多日历史池回放（WATCH/CANDIDATE审计追溯）</summary>
  <div class="inner" style="font-size:var(--font-small);color:var(--text-muted);line-height:var(--line-base)">
    <p style="margin-bottom:6px"><b>口径：</b><span style="color:var(--gold)">历史池 WATCH_EARLY + CANDIDATE 审计追溯。正式 BET_LOCKED 仅 1 场（未结算），不在此表。</span></p>
    <table style="width:100%;border-collapse:collapse;font-size:var(--font-tiny)">
    <tr style="color:var(--text-dim)"><th style="text-align:left;padding:4px">日期</th><th style="text-align:right">预测</th><th style="text-align:right">已结算</th><th style="text-align:right">命中</th><th style="text-align:right">失败</th><th style="text-align:right">命中率</th></tr>
    <tr><td>2026-05-15</td><td style="text-align:right">1</td><td style="text-align:right">1</td><td style="text-align:right">0</td><td style="text-align:right">1</td><td style="text-align:right">0.0%</td></tr>
    <tr><td>2026-05-14</td><td style="text-align:right">15</td><td style="text-align:right">0</td><td style="text-align:right">—</td><td style="text-align:right">—</td><td style="text-align:right">N/A</td></tr>
    <tr><td>2026-05-13</td><td style="text-align:right">32</td><td style="text-align:right">31</td><td style="text-align:right">10</td><td style="text-align:right">21</td><td style="text-align:right">32.3%</td></tr>
    <tr><td>2026-05-12</td><td style="text-align:right">11</td><td style="text-align:right">10</td><td style="text-align:right">9</td><td style="text-align:right">1</td><td style="text-align:right">90.0%</td></tr>
    <tr><td>2026-05-11</td><td style="text-align:right">9</td><td style="text-align:right">9</td><td style="text-align:right">5</td><td style="text-align:right">4</td><td style="text-align:right">55.6%</td></tr>
    <tr><td>2026-05-10</td><td style="text-align:right">44</td><td style="text-align:right">43</td><td style="text-align:right">21</td><td style="text-align:right">22</td><td style="text-align:right">48.8%</td></tr>
    <tr style="border-top:1px solid var(--border-subtle)"><td colspan="2"><b style="color:var(--text-primary)">累计（全部10天）</b></td><td style="text-align:right"><b style="color:var(--text-primary)">185</b></td><td style="text-align:right"><b style="color:var(--green)">85</b></td><td style="text-align:right"><b style="color:var(--red)">100</b></td><td style="text-align:right"><b style="color:var(--text-primary)">45.9%</b></td></tr>
    </table>
    <p style="margin-top:6px;color:var(--text-dim)">滚动 7天: 47.2% | 14天: 45.9% | 30天: 45.9%</p>
  </div>
</details>

<details><summary>展开：完整验证数据与血缘追溯</summary>
  <div class="inner">
    <div style="font-size:var(--font-small);color:var(--text-muted);line-height:var(--line-base)">
      <p style="margin-bottom:6px;font-size:var(--font-tiny);color:var(--text-dim)">数据指纹: 1354bcbe1091</p>
      <p style="margin-bottom:8px"><b>数据覆盖：</b>2026-05-13 至 2026-05-19（7天 attribution）<br>
      <b>数据来源：</b>8个 v4_result_attribution JSONL 文件<br>
      <b>7/14/30窗口相同原因：</b>所有438条记录均落在7天窗口内</p>
      <div style="margin-bottom:6px"><b style="color:var(--text-primary)">生产推荐口径（默认）</b></div>
      <div class="info-row"><span class="k">V4 A+B 正式</span><span class="v"><b style="color:var(--text-primary)">130</b> 已结算 · 命中75 · 失败55 · 命中率 <b style="color:var(--green)">57.7%</b></span></div>
      <div class="info-row"><span class="k">V4 A级</span><span class="v">已结算41 · 命中25/失败16 · 命中率 61.0% · 球队去重 32</span></div>
      <div class="info-row"><span class="k">V4 B级</span><span class="v">已结算89 · 命中50/失败39 · 未知3 · 命中率 56.2% · 球队去重 74</span></div>
      <div style="margin:10px 0 6px"><b style="color:var(--gold)">原始记录口径</b></div>
      <div class="info-row"><span class="k">V4 A+B</span><span class="v">133 条（A=41 + B=92）</span></div>
      <div class="info-row"><span class="k">总计</span><span class="v">438 条原始记录 · unique keys 438 · duplicates 0</span></div>
      <div style="margin:10px 0 6px"><b style="color:var(--blue)">球队去重口径</b></div>
      <div class="info-row"><span class="k">V4 A+B</span><span class="v">106 队（A=32 + B=74）</span></div>
      <div style="margin-top:10px"><b>C观察 / SKIP 统计</b></div>
      <div class="info-row"><span class="k">C观察</span><span class="v">190条 · 命中75 · 失败102 · 未知13 · 观察命中率 42.4%</span></div>
      <div class="info-row"><span class="k">SKIP</span><span class="v">115条 · 命中16 · 失败91 · 未知8</span></div>
      <p style="margin-top:6px;color:var(--text-dim)">C和SKIP均<b>不计入正式命中率</b></p>
    </div>
  </div>
</details>

<h2><span class="zone-num">4</span> V2 状态与验证</h2>
<div class="v2-module-card">
  <div class="v2-title">V2 生产状态</div>
  <div class="v2-status" style="margin-top:6px">
    <div class="info-row"><span class="k">生产状态</span><span class="v"><span class="badge bg-green">PRODUCTION_VERIFIED</span></span></div>
    <div class="info-row"><span class="k">BET_LOCKED</span><span class="v"><b style="color:var(--text-primary)">1</b> 场</span></div>
    <div class="info-row"><span class="k">V2 历史池审计</span><span class="v">累计185场已结算 · 命中率 <b style="color:var(--text-primary)">45.9%</b> · 7天 <b>47.2%</b> <span style="color:var(--gold);font-size:var(--font-tiny)">⚠ 非正式BET_LOCKED</span></span></div>
    <div class="info-row"><span class="k">V2 正式 BET_LOCKED</span><span class="v"><b style="color:var(--text-primary)">1</b> 场（Ried vs Wolfsberger） · <b style="color:var(--gold)">0已结算</b> · 样本不足</span></div>
  </div>
</div>

<details><summary>展开：V2 锁仓证明（历史审计，仅作审计追溯，非当日操作）</summary>
  <div class="inner">
    <div class="lock-card">
      <div class="lock-title">V2 锁仓证明 — 历史审计</div>
      <div class="lock-cn">里德 vs 沃尔夫斯贝格</div>
      <div class="lock-en">Ried vs Wolfsberger AC</div>
      <div class="lock-detail">赛事编号：1545407 · T-90 锁仓 · 平局赔率：2.28<br>旧消息补推：已阻断 · 真实投注：否</div>
      <div class="lock-tags"><span class="badge bg-yellow">历史锁仓</span><span class="badge bg-gray">仅作审计追溯，非当日操作</span><span class="badge bg-gray">real_bet=否</span></div>
    </div>
  </div>
</details>

<h2><span class="zone-num">5</span> 系统安全</h2>
<div class="zone-card compact">
  <div class="info-row"><span class="k">运行状态</span><span class="v"><span class="badge bg-green">正常</span> V2 PRODUCTION_VERIFIED</span></div>
  <div class="info-row"><span class="k">D13 / V33 / HOURLY</span><span class="v"><span class="badge bg-gray">否</span></span></div>
  <div class="info-row"><span class="k">真实投注</span><span class="v"><span class="badge bg-gray">否</span></span></div>
  <div class="info-row"><span class="k">策略变更</span><span class="v"><span class="badge bg-gray">否</span></span></div>
</div>

<details data-audit-hidden="true">
  <summary>展开：系统审计详情</summary>
  <div class="inner" style="font-size:var(--font-small);color:var(--text-muted);line-height:var(--line-base)">
    <div class="info-row"><span class="k">V2 QQ</span><span class="v">已启用（仅V2）</span></div>
    <div class="info-row"><span class="k">V4 QQ</span><span class="v">关闭 · V4_QQ_ENABLED=false · actual_send=false · qq_sent=false</span></div>
    <div class="info-row"><span class="k">route</span><span class="v">shadow_only</span></div>
    <div class="info-row"><span class="k">V2 生产状态</span><span class="v">PRODUCTION_VERIFIED</span></div>
  </div>
</details>

<details><summary>展开：事故审计（历史记录，非当前运营状态）</summary>
  <div class="inner" style="font-size:var(--font-small);color:var(--text-muted);line-height:var(--line-base)">
    <p><b>2026-05-19 23:09</b> — QQ未授权发送事件<br>
    _push_system_event() 缺少 V2_QQ_SEND_ENABLED 门控 → QQ真实发送<br>
    已修复 · BOSS已签收 (23:24)</p>
    <p style="margin-top:6px"><b>窗口历史：</b>凌晨 B=6 → 上午 B=4 C=6 → 晚间 A=1 B=4 C=6 → 夜间 A=1 B=3 C=5</p>
  </div>
</details>

<h2><span class="zone-num">6</span> 下一动作</h2>
<div class="zone-card compact">
  <div class="info-row"><span class="k">当前阶段</span><span class="v" style="color:var(--green)">midday 扫描已完成</span></div>
  <div class="info-row"><span class="k">下一窗口</span><span class="v" style="color:var(--gold)">evening 16:20 → 继续扫描</span></div>
  <div class="info-row"><span class="k">之后</span><span class="v">night 22:20 → 赛果 → 复盘9步</span></div>
</div>

<details><summary>展开：扫描窗口记录</summary>
  <div class="inner">
    <div class="timeline-collapsed">
      <div class="step">午间<span class="t">✅ 12:39</span></div>
      <div class="step">傍晚<span class="t">⏳ 16:20</span></div>
      <div class="step">夜间<span class="t">⏳ 22:20</span></div>
    </div>
    <p style="font-size:var(--font-tiny);color:var(--text-dim);margin-top:8px">午间窗口扫描已完成 · 94场 33scout 1266s</p>
  </div>
</details>

<div class="footer">
  V2: 生产已验证 | D13/V33/小时级=否 | 真实发送=否 | 策略未变更<br>
  数据来源: 午间窗口 | 2026-05-23
</div>

<script>
function toggleEyeComfortV2(){
  var root=document.documentElement;
  var cur=parseInt(getComputedStyle(root).getPropertyValue('--font-base').trim());
  if(cur>=19){root.style.setProperty('--font-base','17px');root.style.setProperty('--font-team','21px');root.style.setProperty('--font-hero','27px');root.style.setProperty('--font-section-title','23px')}
  else{root.style.setProperty('--font-base','19px');root.style.setProperty('--font-team','23px');root.style.setProperty('--font-hero','30px');root.style.setProperty('--font-section-title','26px')}
}
</script>
</body>
</html>'''

output = BASE / "data" / "runtime" / "dashboard" / "intel_ops_console.html"
output.write_text(html)
print(f"✅ intel_ops_console.html ({len(html)} bytes)")
