#!/usr/bin/env node
/**
 * 捷报比分数据采集器 v38 - 主入口 (分进程版)
 *
 * 通过子进程运行每批比赛，子进程退出后100%释放内存
 * 核心逻辑在 batch-worker-v38.js
 */

const { chromium } = require('playwright');
const { fork } = require('child_process');
const fs = require('fs');
const path = require('path');

const CFG = require('./v38-config.js');
const BATCH_SIZE = CFG.scraping.batchSize;
const BATCH_WORKER = path.join(__dirname, 'batch-worker-v38.js');
const ANALYSIS_FILE = '/tmp/jiebao-analysis-v38.json';

// ⚽ 联赛白名单 — 从锁定配置读取
function isLeagueAllowed(league) {
  if (!league) return false;
  const clean = league.replace(/[^\u4e00-\u9fa5a-zA-Z0-9]/g, '');
  return CFG.leagues.some(allowed => clean.startsWith(allowed));
}

function initFiles() {
  const today = new Date().toISOString().split('T')[0];
  fs.writeFileSync(ANALYSIS_FILE, JSON.stringify({
    date: today, version: 'v38',
    rules: 'V38: 分进程版 - 每批独立子进程防OOM',
    total: 0, matches: []
  }));
}

function saveAnalysis(results) {
  try {
    const d = JSON.parse(fs.readFileSync(ANALYSIS_FILE));
    d.matches = results;
    d.total = results.length;
    fs.writeFileSync(ANALYSIS_FILE, JSON.stringify(d));
  } catch (e) {}
}

async function pageWait(page, ms) {
  try { await page.waitForTimeout(ms); } catch (e) {}
}

// 全局异常保护 — 防止单个错误崩溃整个流程
process.on('uncaughtException', e => {
  console.error('[异常]', e.message.substring(0, 80));
});
process.on('unhandledRejection', e => {
  console.error('[异步异常]', String(e).substring(0, 80));
});

async function main() {
  const startTime = Date.now();
  console.log('='.repeat(70));
  console.log('捷报比分 V38 - 分进程版 (每批独立子进程防OOM)');
  console.log(`启动: ${new Date().toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' })}`);
  console.log(`分批: 每${BATCH_SIZE}场 → 子进程独立运行 → 退出即释放内存`);
  console.log('='.repeat(70) + '\n');

  initFiles();

  // === Step 1: 获取比赛列表 ===
  console.log('获取比赛列表...');
  const listBrowser = await chromium.launch({ headless: true });
  const listCtx = await listBrowser.newContext();
  const listPage = await listCtx.newPage();
  await listPage.goto('https://live.nowscore.com/2in1.aspx',
    { waitUntil: 'domcontentloaded', timeout: 25000 });
  await pageWait(listPage, 3000);
  await listPage.evaluate(() => {
    for (const el of document.querySelectorAll('a')) {
      if (el.textContent.trim() === '精简') { el.click(); return; }
    }
  });
  await pageWait(listPage, 2500);

  // 获取所有matchId映射
  const idMap = await listPage.evaluate(() => {
    const map = {};
    for (const a of document.querySelectorAll('a[id^=team1_]')) {
      const onclick = a.getAttribute('onclick') || '';
      const m = onclick.match(/TeamPanlu_10\((\d+)\)/);
      if (m) map[a.textContent.trim()] = parseInt(m[1]);
    }
    return map;
  });

  const text = await listPage.evaluate(() => document.body.innerText);
  const seen = new Set();
  const allMatches = [];
  for (const line of text.split('\n')) {
    const raw = line.split('\t');
    if (raw.length < 7) continue;
    const league = (raw[1] || '').trim();
    const time = (raw[2] || '').trim();
    const status = (raw[5] || '').trim().replace(/\s/g, '');
    const home = (raw[4] || '').trim();
    const away = (raw[6] || '').trim();
    if (!['阵容', '-', '暂停'].includes(status)) continue;
    if (!home || !away) continue;
    if (!isLeagueAllowed(league)) continue;
    const key = home + away + time;
    if (seen.has(key)) continue;
    seen.add(key);
    const id = idMap[home] || idMap[away] || 0;
    allMatches.push({ league, time, home, away, id });
  }

  await listBrowser.close();
  if (global.gc) global.gc();

  const total = allMatches.length;
  console.log(`未开赛比赛: ${total} 场\n`);
  if (total === 0) return;

  // === Step 2: 分批次 ===
  const batches = [];
  for (let i = 0; i < total; i += BATCH_SIZE) {
    batches.push(allMatches.slice(i, i + BATCH_SIZE));
  }
  console.log(`分 ${batches.length} 批，每批${BATCH_SIZE}场 → 独立子进程运行\n`);

  const allResults = [];

  for (let bn = 0; bn < batches.length; bn++) {
    const batch = batches[bn];
    console.log(`[批次 ${bn + 1}/${batches.length}] ${batch.length}场比赛 (总计${total}场)`);

    // 写入临时数据文件供子进程读取
    const dataFile = `/tmp/jiebao-batch-${bn}.json`;
    fs.writeFileSync(dataFile, JSON.stringify(batch));

    // fork子进程（含超时保护）
    let results = [];
    try {
      results = await new Promise((resolve) => {
        const child = fork(BATCH_WORKER, ['--worker', String(bn), String(total), dataFile], {
          stdio: ['pipe', 'pipe', 'pipe', 'ipc']
        });

        const WORKER_TIMEOUT = 6 * 60 * 1000; // 6分钟超时
        let output = '';
        let settled = false;

        child.stdout.on('data', data => {
          const str = data.toString();
          output += str;
          process.stdout.write(str);
        });
        child.stderr.on('data', data => process.stderr.write(data.toString()));

        const finish = (res) => {
          if (settled) return;
          settled = true;
          clearTimeout(timer);
          try { child.kill(); } catch (e) {}
          resolve(res);
        };

        child.on('exit', (code) => {
          if (settled) return;
          settled = true;
          clearTimeout(timer);
          // 解析最后一行JSON
          const lines = output.trim().split('\n');
          let batchResults = [];
          for (let i = lines.length - 1; i >= 0; i--) {
            try {
              const parsed = JSON.parse(lines[i]);
              if (parsed.batchIndex !== undefined && parsed.results) {
                batchResults = parsed.results;
                break;
              }
            } catch (e) {}
          }
          resolve(batchResults);
        });
        child.on('error', () => finish([]));

        const timer = setTimeout(() => {
          console.log(`  ⏰ 批次 ${bn + 1} 超时(${WORKER_TIMEOUT/1000}s)，强制跳过`);
          finish([]);
        }, WORKER_TIMEOUT);
      });
    } catch (batchErr) {
      console.log(`  ❌ 批次 ${bn + 1} 异常: ${batchErr.message.substring(0,60)}`);
      results = [];
    }

    // 清理
    try { fs.unlinkSync(dataFile); } catch (e) {}

    // 收集结果
    if (results && results.length > 0) {
      allResults.push(...results);
      saveAnalysis(allResults);
    }

    console.log(`批次 ${bn + 1} 完成 → 累计${bn+1}/${batches.length}批 | ${results.length}场推荐 | 总计${allResults.length}场\n`);

    // 批次之间等待一下，让系统喘口气
    if (bn < batches.length - 1) {
      await new Promise(r => setTimeout(r, 2000));
    }
  }

  // === Step 3: 输出报告 ===
  const elapsed = ((Date.now() - startTime) / 1000).toFixed(0);

  console.log(`\n${'='.repeat(70)}`);
  console.log(`  V38 推荐清单 (${elapsed}s, ${allResults.length}场推荐)`);
  console.log(`${'='.repeat(70)}\n`);

  if (allResults.length === 0) {
    console.log('无符合条件比赛。');
    return;
  }

  allResults.sort((a, b) => {
    const ah = parseInt(a.time), am = parseInt((a.time || '').split(':')[1] || 0);
    const bh = parseInt(b.time), bm = parseInt((b.time || '').split(':')[1] || 0);
    return (ah * 60 + am) - (bh * 60 + bm);
  });

  const h100 = allResults.filter(r => r.h2hRate === 100);
  const other = allResults.filter(r => r.h2hRate !== 100);

  if (h100.length > 0) {
    console.log('🔥🔥 100%进球率（优先推荐）');
    console.log('-'.repeat(120));
    const hdr = `${'时间'.padEnd(6)}|${'联赛'.padEnd(14)}|${'对阵'.padEnd(30)}|${'H2H'.padEnd(6)}|${'场均'.padEnd(6)}|${'盘口'.padEnd(12)}|${'盘口信号'.padEnd(18)}|${'买入'.padEnd(14)}|${'建议'}`;
    console.log(hdr);
    console.log('-'.repeat(120));
    h100.forEach(r => {
      const o = r.oddsCur ? `大${r.oddsCur}` : '-';
      console.log(`${r.time.padEnd(6)}|${r.league.padEnd(14)}|${(`${r.home} vs ${r.away}`).padEnd(30)}|${`${r.h2hCount}场`.padEnd(6)}|${`${r.h2hAvg}`.padEnd(6)}|${o.padEnd(12)}|${(r.oddsSignalDetail || '').padEnd(18)}|${(r.buyTiming || '').padEnd(14)}|${r.advice}`);
    });
    console.log();
  }

  if (other.length > 0) {
    console.log('✅ 80-89%进球率');
    console.log('-'.repeat(120));
    const hdr = `${'时间'.padEnd(6)}|${'联赛'.padEnd(14)}|${'对阵'.padEnd(30)}|${'进球率'.padEnd(8)}|${'H2H'.padEnd(6)}|${'场均'.padEnd(6)}|${'盘口'.padEnd(12)}|${'盘信号'.padEnd(18)}|${'买入'.padEnd(14)}|${'建议'}`;
    console.log(hdr);
    console.log('-'.repeat(120));
    other.forEach(r => {
      const o = r.oddsCur ? `大${r.oddsCur}` : '-';
      console.log(`${r.time.padEnd(6)}|${r.league.padEnd(14)}|${(`${r.home} vs ${r.away}`).padEnd(30)}|` +
        `${`${r.h2hRate}%`.padEnd(8)}|${`${r.h2hCount}场`.padEnd(6)}|${`${r.h2hAvg}`.padEnd(6)}|` +
        `${o.padEnd(12)}|${(r.oddsSignalDetail || '').padEnd(18)}|${(r.buyTiming || '').padEnd(14)}|${r.advice}`);
    });
    console.log();
  }

  console.log(`共推荐 ${allResults.length} 场（100%: ${h100.length}场 | 80-89%: ${other.length}场）`);

  const buyNow = allResults.filter(r => r.buyTiming?.includes('买入') || r.buyTiming?.includes('直接'));
  const wait = allResults.filter(r => r.buyTiming?.includes('观望'));
  const cautious = allResults.filter(r => r.buyTiming?.includes('谨慎'));
  if (buyNow.length > 0) console.log(`💰 建议立即投: ${buyNow.length}场`);
  if (wait.length > 0) console.log(`⏳ 建议等待降盘: ${wait.length}场`);
  if (cautious.length > 0) console.log(`⚠️ 需要谨慎: ${cautious.length}场`);
}

main().catch(e => {
  console.error('Fatal:', e.message.substring(0, 80));
  process.exit(1);
});

// 保持进程存活直到所有子进程结束
process.on('beforeExit', () => {});
