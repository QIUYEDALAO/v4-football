with open("data/runtime/dashboard/intel_ops_console.html") as f:
    content = f.read()

fixes = 0

# ---- A card: fix format ----
old_a = """<div class="candidate-card grade-A">
  <div class="cl">自由杯 · 05-21 08:30</div>
  <div class="cn">帕尔梅拉斯 vs 波特诺山丘</div>
  <div class="cnen">Palmeiras vs Cerro Porteno</div>
  <div class="cs">HT 79 ｜ 剧本：<b>中段压迫型</b> ｜ 16-30m 高峰</div>
  <div class="cdist">时段：0-15m 40% | 16-30m 60% | 31-45m 30%</div>
  <div class="ct"><span class="badge bg-yellow">A级候选</span> <span class="badge bg-gray">等待BOSS批准</span> <span class="badge bg-gray">QQ未发送</span></div>
</div>"""

new_a = """<div class="candidate-card grade-A">
  <div class="cl">05-21 08:30｜自由杯</div>
  <div class="cn">帕尔梅拉斯 vs 波特诺山丘</div>
  <div class="cs">HT79｜剧本：<b>中段压迫型</b>｜16-30m高峰</div>
  <div class="cdist">0-15m 40%｜16-30m 60%｜31-45m 30%</div>
  <div class="ct"><span class="badge bg-yellow">A级候选</span> <span class="badge bg-gray">等待BOSS批准</span> <span class="badge bg-gray">QQ未发送</span></div>
  <details class="card-detail"><summary style="font-size:8px;color:#576574">详情</summary><div class="inner" style="font-size:8px;color:#576574">Palmeiras vs Cerro Porteno · 来源：scout_v4 · factors.recent_time_bins · QQ未发送</div></details>
</div>"""

if old_a in content:
    content = content.replace(old_a, new_a)
    fixes += 1
    print("A card reformatted — OK")

# ---- B1: Hangzhou ----
old_b1 = """<div class="candidate-card grade-B">
  <div class="cl">中超 · 20:00</div>
  <div class="cn">浙江队 vs 山东泰山</div>
  <div class="cnen">Hangzhou Greentown vs Shandong Luneng</div>
  <div class="cs">HT61 ｜ 强度85.0% ｜ 2.12球 ｜ 剧本：<b>慢热绝杀型</b></div>
  <div class="cdist">时段：0-15m 20% | 16-30m 30% | 31-45m 60%</div>
  <div class="ct"><span class="badge bg-blue">B级候选</span></div>
</div>"""

new_b1 = """<div class="candidate-card grade-B">
  <div class="cl">20:00｜中超</div>
  <div class="cn">浙江队 vs 山东泰山</div>
  <div class="cs">HT61｜强度85.0%｜2.12球｜剧本：<b>慢热绝杀型</b></div>
  <div class="cdist">0-15m 20%｜16-30m 30%｜31-45m 60%</div>
  <div class="ct"><span class="badge bg-blue">B级候选</span></div>
  <details class="card-detail"><summary style="font-size:8px;color:#576574">详情</summary><div class="inner" style="font-size:8px;color:#576574">Hangzhou Greentown vs Shandong Luneng · FULLTIME_OVER · SH_OU · Best:85.0 · 来源：scout_v4 · factors.recent_time_bins · QQ未发送</div></details>
</div>"""

if old_b1 in content:
    content = content.replace(old_b1, new_b1)
    fixes += 1
    print("B1 reformatted — OK")

# ---- B2: Ilves ----
old_b2 = """<div class="candidate-card grade-B">
  <div class="cl">芬超 · 23:00</div>
  <div class="cn">伊尔韦斯 vs 图尔库国际</div>
  <div class="cnen">Ilves vs Inter Turku</div>
  <div class="cs">HT80 ｜ 强度80.5% ｜ 2.01球 ｜ 剧本：<b>开局冲击型（高压）</b></div>
  <div class="cdist">时段：0-15m 60% | 16-30m 50% | 31-45m 40%</div>
  <div class="ct"><span class="badge bg-blue">B级候选</span></div>
</div>"""

new_b2 = """<div class="candidate-card grade-B">
  <div class="cl">23:00｜芬超</div>
  <div class="cn">伊尔韦斯 vs 图尔库国际</div>
  <div class="cs">HT80｜强度80.5%｜2.01球｜剧本：<b>开局冲击型（高压）</b></div>
  <div class="cdist">0-15m 60%｜16-30m 50%｜31-45m 40%</div>
  <div class="ct"><span class="badge bg-blue">B级候选</span></div>
  <details class="card-detail"><summary style="font-size:8px;color:#576574">详情</summary><div class="inner" style="font-size:8px;color:#576574">Ilves vs Inter Turku · FULLTIME_OVER · SH_OU · Best:80.5 · 来源：scout_v4 · factors.recent_time_bins · QQ未发送</div></details>
</div>"""

if old_b2 in content:
    content = content.replace(old_b2, new_b2)
    fixes += 1
    print("B2 reformatted — OK")

# ---- B3: Start ----
old_b3 = """<div class="candidate-card grade-B">
  <div class="cl">挪超 · 00:00+1</div>
  <div class="cn">斯达 vs 博德闪耀</div>
  <div class="cnen">Start vs Bodo/Glimt</div>
  <div class="cs">HT70 ｜ 强度80.8% ｜ 2.02球 ｜ 剧本：<b>中段压迫型</b></div>
  <div class="cdist">时段：0-15m 10% | 16-30m 50% | 31-45m 40%</div>
  <div class="ct"><span class="badge bg-blue">B级候选</span></div>
</div>"""

new_b3 = """<div class="candidate-card grade-B">
  <div class="cl">00:00+1｜挪超</div>
  <div class="cn">斯达 vs 博德闪耀</div>
  <div class="cs">HT70｜强度80.8%｜2.02球｜剧本：<b>中段压迫型</b></div>
  <div class="cdist">0-15m 10%｜16-30m 50%｜31-45m 40%</div>
  <div class="ct"><span class="badge bg-blue">B级候选</span></div>
  <details class="card-detail"><summary style="font-size:8px;color:#576574">详情</summary><div class="inner" style="font-size:8px;color:#576574">Start vs Bodo/Glimt · FULLTIME_OVER · FT_OU · Best:80.8 · 来源：scout_v4 · factors.recent_time_bins · QQ未发送</div></details>
</div>"""

if old_b3 in content:
    content = content.replace(old_b3, new_b3)
    fixes += 1
    print("B3 reformatted — OK")

# ---- B4: Santos ----
old_b4 = """<div class="candidate-card grade-B">
  <div class="cl">南美杯 · 06:00+1</div>
  <div class="cn">桑托斯 vs 圣洛伦索</div>
  <div class="cnen">Santos vs San Lorenzo</div>
  <div class="cs">HT64 ｜ 强度71.0% ｜ 1.77球 ｜ 剧本：<b>中段压迫型</b></div>
  <div class="cdist">时段：0-15m 10% | 16-30m 60% | 31-45m 40%</div>
  <div class="ct"><span class="badge bg-blue">B级候选</span></div>
</div>"""

new_b4 = """<div class="candidate-card grade-B">
  <div class="cl">06:00+1｜南美杯</div>
  <div class="cn">桑托斯 vs 圣洛伦索</div>
  <div class="cs">HT64｜强度71.0%｜1.77球｜剧本：<b>中段压迫型</b></div>
  <div class="cdist">0-15m 10%｜16-30m 60%｜31-45m 40%</div>
  <div class="ct"><span class="badge bg-blue">B级候选</span></div>
  <details class="card-detail"><summary style="font-size:8px;color:#576574">详情</summary><div class="inner" style="font-size:8px;color:#576574">Santos vs San Lorenzo · FULLTIME_OVER · FT_OU · Best:71.0 · 来源：scout_v4 · factors.recent_time_bins · QQ未发送</div></details>
</div>"""

if old_b4 in content:
    content = content.replace(old_b4, new_b4)
    fixes += 1
    print("B4 reformatted — OK")

# ---- Add CSS for card-detail ----
old_css = ".ct{display:flex;flex-wrap:wrap;gap:3px;margin-top:2px}"
new_css = """.ct{display:flex;flex-wrap:wrap;gap:3px;margin-top:2px}
.card-detail{margin-top:3px}
.card-detail summary{cursor:pointer;font-size:8px;color:#576574;user-select:none}
.card-detail .inner{font-size:8px;color:#576574;padding:2px 0}"""

if old_css in content:
    content = content.replace(old_css, new_css)
    fixes += 1
    print("Added card-detail CSS — OK")

# ---- Also update C card format to remove "时段：" prefix ----
for i in range(6):
    old_prefix = "<div class=\"cdist\">时段："
    new_prefix = "<div class=\"cdist\">"
    content = content.replace(old_prefix, new_prefix)

with open("data/runtime/dashboard/intel_ops_console.html", "w") as f:
    f.write(content)
print(f"\nTotal fixes applied: {fixes}")
