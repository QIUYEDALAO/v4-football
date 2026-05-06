#!/usr/bin/env node
/**
 * 赛前盘口二次检查 — 在比赛开赛前30分钟检查盘口变化
 *
 * 对于"⏳观望等降"的比赛，如果盘口降下来了，通知用户买入
 *
 * 用法: node tools/prematch-check.js
 */
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const PREDICTIONS_FILE = path.join(__dirname, '..', 'data', '验证存档', 'v33', 'predictions.json');

const NOW = new Date();
const NOW_CN = new Date(NOW.getTime() + 8 * 3600000); // 北京时间

function loadTodaysWaiting() {
  try {
    const today = NOW_CN.toISOString().split('T')[0];
    const db = JSON.parse(fs.readFileSync(PREDICTIONS_FILE, 'utf8'));
    return db.predictions.filter(p => p.date === today && !p.verified &&
      (p.buyTiming === '⏳观望' || p.buyTiming?.includes('等待降盘')));
  } catch { return []; }
}

function normalizeOdds(val) {
  if (!val || val === '-') return null;
  const s = String(val).trim();
  if (s.includes('/')) {
    const p = s.split('/');
    return (parseFloat(p[0]) + parseFloat(p[1])) / 2;
  }
  return parseFloat(s);
}

function parseTime(timeStr) {
  // time format: "00:00"
  const parts = timeStr.split(':');
  const hour = parseInt(parts[0]), min = parseInt(parts[1] || 0);
  // 赛前30分钟 = 比赛时间 - 30分钟
  return { matchMinute: hour * 60 + min, checkMinute: hour * 60 + min - 30 };
}

async function checkOdds(page, match) {
  try {
    const curCN = new Date(Date.now() + 8 * 3600000);
    const curMin = curCN.getHours() * 60 + curCN.getMinutes();
    const { matchMinute, checkMinute } = parseTime(match.time);

    // 只在赛前30分钟到开赛之间检查
    if (curMin < checkMinute) return { status: 'too_early', detail: `距离开赛还有${matchMinute - curMin}分钟` };
    if (curMin > matchMinute) return { status: 'started', detail: '已开赛' };

    // 去2in1页面找这场比赛
    await page.goto('https://live.nowscore.com/2in1.aspx', { waitUntil: 'domcontentloaded', timeout: 20000 });
    await page.waitForTimeout(2000);
    await page.evaluate(() => {
      for (const l of document.querySelectorAll('a')) { if (l.textContent.trim() === '精简') { l.click(); return; } }
    });
    await page.waitForTimeout(1500);

    // 找队伍名点进去
    const clicked = await page.evaluate(m => {
      for (const l of document.querySelectorAll('a')) {
        if (l.textContent.trim() === m.home) { l.click(); return true; }
        if (l.textContent.trim() === m.away) { l.click(); return true; }
      }
      return false;
    }, match);

    if (!clicked) return { status: 'not_found', detail: `未找到 ${match.home} vs ${match.away}` };

    await page.waitForTimeout(2000);
    const pages = page.context().pages();
    if (pages.length < 2) return { status: 'no_detail', detail: '详情页未打开' };

    const np = pages[pages.length - 1];
    await np.waitForTimeout(800);

    // 获取盘口
    await np.evaluate(() => {
      for (const l of document.querySelectorAll('a')) { if (l.textContent.trim() === '指数三合一') { l.click(); return; } }
    });
    await np.waitForTimeout(1200);
    await np.evaluate(() => {
      for (const l of document.querySelectorAll('a')) { if (l.textContent.trim() === '半场') { l.click(); return; } }
    });
    await np.waitForTimeout(1200);

    const text = await np.evaluate(() => document.body.innerText);
    try { await np.close(); } catch (e) {}

    // 提取盘口
    for (const line of text.split('\n')) {
      const t = line.trim();
      if (!t.startsWith('Crow*')) continue;
      const parts = t.split('\t').filter(x => x.trim());
      if (parts.length >= 18) {
        const init = normalizeOdds(parts[14]);
        const cur = normalizeOdds(parts[17]);
        if (init !== null && cur !== null) {
          const diff = cur - init;
          if (diff < -0.01) {
            // 降盘了！
            const action = cur <= 0.75 ? '⚠️谨慎' : '✅买入时机';
            return { status: 'dropped', oldInit: init, cur, detail: `✅ 降盘了！${init}→${cur} (${diff.toFixed(2)})，${action === '✅买入时机' ? '可以入' : '盘口过低谨慎'}` };
          }
          if (cur >= 1.5) return { status: 'still_high', cur, detail: `仍偏高：大${cur}` };
          if (cur <= 1) return { status: 'good', cur, detail: `盘口${cur}适中，可以投了` };
          return { status: 'stable', cur, detail: `盘口${cur}未变` };
        }
      }
    }
    return { status: 'no_odds', detail: '盘口数据异常' };
  } catch (e) {
    return { status: 'error', detail: e.message.substring(0, 50) };
  }
}

async function main() {
  console.log(`盘口二次检查 | ${NOW_CN.toLocaleString('zh-CN')}\n`);

  const matches = loadTodaysWaiting();
  if (matches.length === 0) {
    console.log('没有等待降盘的比赛');
    return;
  }

  console.log(`待检查 ${matches.length} 场（⏳观望等降）:`);
  matches.forEach(m => console.log(`  ${m.time} ${m.league} ${m.home} vs ${m.away} (原盘口:大${m.oddsCur})`));
  console.log();

  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await ctx.newPage();

  for (const m of matches) {
    process.stdout.write(`[${m.time}] ${m.league} ${m.home} vs ${m.away}... `);
    const r = await checkOdds(page, m);
    console.log(r.detail);
  }

  await browser.close();
}

main().catch(e => console.error('Fatal:', e.message));
