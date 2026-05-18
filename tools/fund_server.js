/**
 * 投注资金日报表 - 本地网页编辑服务
 * 数据直接保存到电脑上的 .xlsx 文件，不受浏览器缓存影响
 * V3: 当日盈利/累计盈利自动计算，修复空行跳跃/累计累加bug
 */
const http = require('http');
const fs = require('fs');
const path = require('path');
const XLSX = require('xlsx');

const PORT = 18900;
const XLSX_PATH = path.join(__dirname, '..', '投注资金日报表_2026年5月.xlsx');
const VERSION = 'v3-20260515';

function readExcel() {
  const wb = XLSX.readFile(XLSX_PATH);
  const ws = wb.Sheets['5月'];
  const data = XLSX.utils.sheet_to_json(ws, { header: 1 });
  return { wb, ws, data };
}

function saveExcel(data) {
  const wb = XLSX.readFile(XLSX_PATH);
  const ws = wb.Sheets['5月'];
  for (let r = 0; r < 50; r++)
    for (let c = 0; c < 10; c++)
      delete ws[XLSX.utils.encode_cell({ r, c })];
  for (let r = 0; r < data.length; r++)
    for (let c = 0; c < data[r].length; c++) {
      const val = data[r][c];
      if (val !== null && val !== undefined && val !== '') {
        ws[XLSX.utils.encode_cell({ r, c })] = { v: val, t: typeof val === 'number' ? 'n' : 's' };
      }
    }
  ws['!ref'] = XLSX.utils.encode_range({ s: { r: 0, c: 0 }, e: { r: data.length - 1, c: data.reduce((m, r) => Math.max(m, r.length - 1), 6) } });
  XLSX.writeFile(wb, XLSX_PATH);
}

function renderPage(rawData) {
  return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>投注资金日报表 · 2026年5月 (${VERSION})</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;background:#f5f5f7;padding:20px;color:#1d1d1f}
.container{max-width:1200px;margin:0 auto}
h1{font-size:22px;font-weight:600;margin-bottom:4px}
.version{font-size:12px;color:#86868b;margin-bottom:12px}
.controls{display:flex;gap:10px;margin-bottom:12px;align-items:center;flex-wrap:wrap}
button{background:#007aff;color:#fff;border:none;padding:8px 18px;border-radius:8px;font-size:14px;cursor:pointer}
button:hover{background:#0062cc}
.btn-green{background:#34c759}
.btn-green:hover{background:#28a745}
.btn-danger{background:#ff3b30}
.btn-danger:hover{background:#d63031}
table{width:100%;border-collapse:collapse;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,0.08)}
th,td{padding:7px 8px;text-align:center;border-bottom:1px solid #e8e8ed;font-size:13px}
th{background:#f0f0f5;font-weight:600;position:sticky;top:0}
td input{width:100%;border:1px solid #d1d1d6;border-radius:6px;padding:5px 6px;font-size:13px;text-align:center;background:#fff}
td input:focus{outline:2px solid #007aff;border-color:transparent}
td input.num{font-variant-numeric:tabular-nums}
td .auto-val{display:block;padding:5px 6px;font-size:13px;font-weight:600;text-align:center;color:#555;min-height:28px}
td .auto-val.green{color:#34c759}
td .auto-val.red{color:#ff3b30}
td .input-col{background:#f2fff2}
.status{padding:10px 14px;border-radius:8px;margin-bottom:12px;font-size:14px;display:none}
.status.success{display:block;background:#d1fae5;color:#065f46}
.status.error{display:block;background:#fee2e2;color:#991b1b}
.status.saving{display:block;background:#e0f2fe;color:#075985}
.summary{display:grid;grid-template-columns:repeat(auto-fit,minmax(110px,1fr));gap:10px;margin-bottom:12px}
.card{background:#fff;border-radius:10px;padding:10px 14px;box-shadow:0 1px 6px rgba(0,0,0,0.06)}
.card .label{font-size:11px;color:#86868b;margin-bottom:2px}
.card .value{font-size:20px;font-weight:700}
.card .value.green{color:#34c759}
.card .value.red{color:#ff3b30}
.hint{font-size:12px;color:#86868b;margin-left:10px}
@media(max-width:768px){body{padding:12px}th,td{padding:4px 5px;font-size:12px}td input{font-size:12px;padding:4px}}
</style>
</head>
<body>
<div class="container">
<h1>📊 投注资金日报表 · 2026年5月</h1>
<div class="version">${VERSION} — 只需输入 <strong>入金 · 提款 · 余额</strong>，当日盈利和累计盈利自动计算</div>
<div style="margin-bottom:12px;display:flex;gap:10px;flex-wrap:wrap;">
<a href="/dashboard" target="_blank" style="text-decoration:none;"><button type="button" style="background:#5856d6;font-size:13px;padding:6px 14px;">📡 V4 完整仪表盘</button></a>
<a href="/v4-brief" target="_blank" style="text-decoration:none;"><button type="button" style="background:#ff9500;font-size:13px;padding:6px 14px;">⚽ V4 今日简报</button></a>
</div>
<div class="summary" id="summary"></div>
<div class="controls">
<button class="btn-green" onclick="saveAll()">💾 保存到电脑</button>
<button onclick="resetAll()">🔄 全部重算</button>
<span class="hint">数据直接存电脑文件，清浏览器历史不会丢</span>
</div>
<div class="status" id="status"></div>
<table>
<thead><tr>
<th style="width:45px">日期</th>
<th style="width:75px">入金</th>
<th style="width:75px">提款</th>
<th style="width:85px">余额</th>
<th style="width:85px">当日盈利</th>
<th style="width:85px">累计盈利</th>
<th>备注</th>
</tr></thead>
<tbody id="tableBody"></tbody>
</table>
</div>

<script>
const raw = ${JSON.stringify(rawData)};
const data = raw.map(row => [...row]);

// ======== 核心计算逻辑 ========

// 找前日余额：跳过空白行，取最近一个有余额的日期
function getPrevBalance(ri) {
  for (let r = ri - 1; r >= 1; r--) {
    const v = data[r]?.[3];
    if (v !== null && v !== undefined && v !== '' && !isNaN(Number(v))) return Number(v);
  }
  return 0;
}

// 计算单行当日盈利
function calcRow(ri) {
  if (ri === 0 || ri >= data.length - 1) return;
  const prevBal = getPrevBalance(ri);
  const curBal = Number(data[ri][3]) || 0;
  const dep = Number(data[ri][1]) || 0;
  const wd = Number(data[ri][2]) || 0;
  // 余额 = 前日余额 + 入金 - 提款 + 当日盈利
  // => 当日盈利 = 余额 - 前日余额 - 入金 + 提款
  data[ri][4] = Math.round((curBal - prevBal - dep + wd) * 100) / 100;
  recalcCumulativeAll();
  calcTotalRow();
}

// 从第一天逐行累加累计盈利
function recalcCumulativeAll() {
  let cum = 0;
  for (let r = 1; r < data.length - 1; r++) {
    const dp = data[r][4];
    if (dp !== null && dp !== undefined && dp !== '') cum = Math.round((cum + dp) * 100) / 100;
    data[r][5] = cum;
  }
}

// 合计行
function calcTotalRow() {
  const last = data.length - 1;
  let sumD = 0, sumW = 0, sumP = 0, lastBal = 0, lastCum = 0;
  for (let r = 1; r < last; r++) {
    sumD += Number(data[r][1]) || 0;
    sumW += Number(data[r][2]) || 0;
    const dp = data[r][4];
    if (dp !== null && dp !== undefined && dp !== '') sumP += dp;
    const b = data[r][3];
    if (b !== null && b !== undefined && b !== '' && !isNaN(Number(b))) lastBal = Number(b);
    const c = data[r][5];
    if (c !== null && c !== undefined && c !== '' && !isNaN(Number(c))) lastCum = Number(c);
  }
  data[last][1] = sumD;
  data[last][2] = sumW;
  data[last][3] = lastBal;
  data[last][4] = Math.round(sumP * 100) / 100;
  data[last][5] = lastCum;
}

// ======== UI 渲染 ========

function renderTable() {
  const tbody = document.getElementById('tableBody');
  tbody.innerHTML = '';
  // 跳过data[0]（表头），因为<thead>已经有表头了
  for (let ri = 1; ri < data.length; ri++) {
    const row = data[ri];
    const tr = document.createElement('tr');
    const isTotal = ri === data.length - 1;
    if (isTotal) tr.style.background = '#f8f8fa';
    tr.style.fontWeight = isTotal ? 600 : 'normal';

    // 日期
    const td0 = document.createElement('td'); td0.textContent = row[0]||''; tr.appendChild(td0);
    // 入金 (col1)
    const td1 = document.createElement('td'); td1.className = 'input-col';
    const i1 = document.createElement('input'); i1.type='text'; i1.className='num';
    i1.value = (row[1]!==null&&row[1]!==undefined) ? row[1] : '';
    i1.disabled = isTotal;
    i1.addEventListener('input', ()=>{ row[1]=i1.value===''?null:Number(i1.value); calcRow(ri); refreshUI(); });
    td1.appendChild(i1); tr.appendChild(td1);
    // 提款 (col2)
    const td2 = document.createElement('td'); td2.className = 'input-col';
    const i2 = document.createElement('input'); i2.type='text'; i2.className='num';
    i2.value = (row[2]!==null&&row[2]!==undefined) ? row[2] : '';
    i2.disabled = isTotal;
    i2.addEventListener('input', ()=>{ row[2]=i2.value===''?null:Number(i2.value); calcRow(ri); refreshUI(); });
    td2.appendChild(i2); tr.appendChild(td2);
    // 余额 (col3)
    const td3 = document.createElement('td'); td3.className = 'input-col';
    const i3 = document.createElement('input'); i3.type='text'; i3.className='num';
    i3.value = (row[3]!==null&&row[3]!==undefined) ? row[3] : '';
    i3.disabled = isTotal;
    i3.addEventListener('input', ()=>{ row[3]=i3.value===''?null:Number(i3.value); calcRow(ri); refreshUI(); });
    td3.appendChild(i3); tr.appendChild(td3);
    // 当日盈利 (col4) — 自动
    const td4 = document.createElement('td'); const sp4 = document.createElement('span'); sp4.className = 'auto-val'; sp4.id='p'+ri;
    td4.appendChild(sp4); tr.appendChild(td4);
    // 累计盈利 (col5) — 自动
    const td5 = document.createElement('td'); const sp5 = document.createElement('span'); sp5.className = 'auto-val'; sp5.id='cp'+ri;
    td5.appendChild(sp5); tr.appendChild(td5);
    // 备注 (col6)
    const td6 = document.createElement('td'); const i6 = document.createElement('input'); i6.type='text';
    i6.value = row[6]||''; i6.disabled = isTotal;
    i6.addEventListener('change', ()=>{ row[6]=i6.value; });
    td6.appendChild(i6); tr.appendChild(td6);
    tbody.appendChild(tr);
  }
  refreshUI();
  updateSummary();
}

function refreshUI() {
  for (let ri = 1; ri < data.length; ri++) {
    const sp = document.getElementById('p'+ri); if (sp) { const v = data[ri][4]; sp.textContent = (v!==null&&v!==undefined&&v!=='') ? Number(v).toLocaleString() : ''; sp.className='auto-val'+(v>=0?' green':' red'); }
    const sc = document.getElementById('cp'+ri); if (sc) { const v = data[ri][5]; sc.textContent = (v!==null&&v!==undefined&&v!=='') ? Number(v).toLocaleString() : ''; sc.className='auto-val'+(v>=0?' green':' red'); }
  }
}

function updateSummary() {
  let dep=0, wd=0, bal=0, cum=0;
  for (let r=1; r<data.length-1; r++) {
    dep += Number(data[r][1])||0; wd += Number(data[r][2])||0;
    const b=data[r][3]; if (b!==null&&b!==undefined&&b!==''&&!isNaN(Number(b))) bal=Number(b);
    const c=data[r][5]; if (c!==null&&c!==undefined&&c!==''&&!isNaN(Number(c))) cum=Number(c);
  }
  document.getElementById('summary').innerHTML =
    '<div class="card"><div class="label">💰 总入金</div><div class="value">'+dep.toLocaleString()+'</div></div>'+
    '<div class="card"><div class="label">🏦 总提款</div><div class="value">'+wd.toLocaleString()+'</div></div>'+
    '<div class="card"><div class="label">📊 最新余额</div><div class="value">'+bal.toLocaleString()+'</div></div>'+
    '<div class="card"><div class="label">📈 累计盈利</div><div class="value'+(cum>=0?' green':' red')+'">'+cum.toLocaleString()+'</div></div>';
}

function resetAll() {
  for (let r = 1; r < data.length - 1; r++) calcRow(r);
  refreshUI(); updateSummary();
  showMsg('🔄 已全部重算', 'success');
}

function showMsg(msg, type) {
  const el=document.getElementById('status'); el.textContent=msg; el.className='status '+type;
  clearTimeout(el._t); el._t=setTimeout(()=>{if(el.className!=='status saving')el.style.display='none';},4000);
}

async function saveAll() {
  const el=document.getElementById('status'); el.textContent='⏳ 保存中...'; el.className='status saving';
  try {
    const r=await fetch('/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({data})});
    const j=await r.json();
    showMsg(j.ok?'✅ 已保存到电脑文件！':'❌ 保存失败: '+j.error, j.ok?'success':'error');
  } catch(e) { showMsg('❌ 请求失败: '+e.message,'error'); }
}

renderTable();
</script>
</body>
</html>`;
}

// ======== HTTP Server ========
const server = http.createServer((req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') { res.writeHead(204); res.end(); return; }

  if (req.method === 'POST' && req.url === '/save') {
    let body = '';
    req.on('data', c => body += c);
    req.on('end', () => {
      try {
        const { data: newData } = JSON.parse(body);
        saveExcel(newData);
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ ok: true, path: XLSX_PATH }));
      } catch (e) {
        res.writeHead(500, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ ok: false, error: e.message }));
      }
    });
    return;
  }

  // V4 情报仪表盘路由
  if (req.url === '/dashboard') {
    const dashPath = path.join(__dirname, '..', 'v2_football_quant', 'docs', 'v4_dashboards', 'v4_dashboard_latest.html');
    if (fs.existsSync(dashPath)) {
      const content = fs.readFileSync(dashPath, 'utf-8');
      res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-cache' });
      res.end(content);
    } else {
      res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
      res.end('暂无仪表盘文件');
    }
    return;
  }

  // V4 情报简报路由（精简版）
  if (req.url === '/v4-brief') {
    const briefDir = path.join(__dirname, '..', 'v2_football_quant', 'data', 'daily_reports');
    const files = fs.readdirSync(briefDir).filter(f => f.startsWith('v4_openclaw_brief_qq_') && f.endsWith('.txt')).sort().reverse();
    if (files.length > 0) {
      const content = fs.readFileSync(path.join(briefDir, files[0]), 'utf-8');
      res.writeHead(200, { 'Content-Type': 'text/plain; charset=utf-8', 'Cache-Control': 'no-cache' });
      res.end(content);
    } else {
      res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
      res.end('暂无V4情报简报');
    }
    return;
  }

  try {
    const { data } = readExcel();
    const html = renderPage(data);
    res.writeHead(200, {
      'Content-Type': 'text/html; charset=utf-8',
      'Cache-Control': 'no-store, no-cache, must-revalidate, max-age=0',
      'Pragma': 'no-cache',
      'Expires': '0'
    });
    res.end(html);
  } catch (e) {
    res.writeHead(500, { 'Content-Type': 'text/plain' });
    res.end('读取文件失败: ' + e.message);
  }
});

server.listen(PORT, '127.0.0.1', () => {
  console.log(`✅ 资金报表编辑页面: http://127.0.0.1:${PORT}/`);
  console.log(`   版本: ${VERSION}`);
  console.log(`   数据文件: ${XLSX_PATH}`);
  console.log(`   按 Ctrl+C 停止服务`);
});
