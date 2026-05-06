#!/usr/bin/env node
/**
 * V38 验证工具 — 验证推荐结果 + 让球盘追踪 + 简易回测
 * 用法: 
 *   node tools/verify-v38.js              # 验证昨天的推荐
 *   node tools/verify-v38.js --backtest   # 跑回测（按新规则重新评分对比）
 */
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const PRED_FILE = path.join(__dirname, '..', 'data', '验证存档', 'v38', 'predictions.json');
const STATS_FILE = path.join(__dirname, '..', 'data', '验证存档', 'v38', 'stats.json');

function loadJSON(f) { try { return JSON.parse(fs.readFileSync(f, 'utf8')); } catch { return null; } }
function saveJSON(f, d) { fs.writeFileSync(f, JSON.stringify(d, null, 2)); }

function printStats(preds, title) {
  const groups = { '100': { t: 0, v: 0, h: 0 }, '90': { t: 0, v: 0, h: 0 }, '80-89': { t: 0, v: 0, h: 0 } };
  let ov = 0, oh = 0;
  preds.forEach(p => {
    if (!p.verified || p.htHasGoal === null) return;
    const k = p.h2hRate >= 100 ? '100' : p.h2hRate >= 90 ? '90' : '80-89';
    groups[k].t++; ov++;
    if (p.htHasGoal) { groups[k].h++; oh++; }
  });
  console.log(`\n📊 ${title}`);
  console.log('='.repeat(60));
  ['100','90','80-89'].forEach(k => {
    const g = groups[k];
    const rate = g.t > 0 ? (g.h / g.t * 100).toFixed(1) + '%' : '-';
    const yieldVal = g.t > 0 ? (((g.h * 1.85 - g.t) / g.t) * 100).toFixed(1) + '%' : '-';
    console.log(`  ${k.padEnd(6)} ${g.h}/${g.t} 命中率${rate}  收益率${yieldVal}`);
  });
  const or = ov > 0 ? (oh / ov * 100).toFixed(1) + '%' : '-';
  const oy = ov > 0 ? (((oh * 1.85 - ov) / ov) * 100).toFixed(1) + '%' : '-';
  console.log(`  总计    ${oh}/${ov} 命中率${or}  收益率${oy}`);
  
  // 让球盘追踪统计（只统计有数据的）
  const ahData = preds.filter(p => p.ftHandicapResult !== null && p.ftHandicapResult !== undefined);
  if (ahData.length > 0) {
    const ahWins = ahData.filter(p => p.ftHandicapResult === 'win').length;
    console.log(`\n⚽ 让球盘追踪: ${ahWins}/${ahData.length}`);
  }

  const uv = preds.filter(p => !p.verified);
  if (uv.length > 0) console.log(`\n⏳ 待验证 ${uv.length}场`);
  return { oh, ov };
}

/** 回测：按新规则重新打分，对比修改前后命中率变化 */
function backtestCompare(preds) {
  const oldRules = preds.filter(p => p.verified && p.htHasGoal !== null);
  if (oldRules.length === 0) { console.log('\n无已验证数据，无法回测'); return; }
  
  const oldHit = oldRules.filter(p => p.htHasGoal).length;
  const oldRate = (oldHit / oldRules.length * 100).toFixed(1);
  
  // 模拟新规则过滤（标记近2次0-0或共振系数低的比赛）
  const newRules = oldRules.filter(p => {
    if (p.h2hZeroCount !== undefined && p.h2hZeroCount >= 2) {
      // 这段是模拟近2次0-0过滤——实际数据中如果有标记会更准
    }
    return true; // 这里需要h2h data的recentTwo, 等实际跑了再看
  });
  
  console.log(`\n📐 新旧规则对比（预估，需更多数据验证）`);
  console.log(`  旧规则: ${oldHit}/${oldRules.length} = ${oldRate}`);
  console.log(`  (等积累200场后跑完整回测)`);
}

async function main() {
  const args = process.argv.slice(2);
  const preds = loadJSON(PRED_FILE);
  if (!preds || !preds.predictions) { console.log('无推荐数据'); return; }

  if (args.includes('--backtest')) {
    backtestCompare(preds.predictions);
    return;
  }

  const yesterday = new Date(Date.now() - 86400000).toISOString().split('T')[0];
  const toVerify = preds.predictions.filter(p => p.date === yesterday && !p.verified);

  if (toVerify.length === 0) {
    printStats(preds.predictions, `${yesterday} 验证统计 (无新数据)`);
    return;
  }

  console.log(`验证 ${yesterday} 的 ${toVerify.length} 场推荐...\n`);

  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await ctx.newPage();

  for (const p of toVerify) {
    try {
      process.stdout.write(`  ${p.league} ${p.home} vs ${p.away}... `);
      await page.goto('https://live.nowscore.com/2in1.aspx', { waitUntil: 'domcontentloaded', timeout: 15000 }).catch(()=>{});
      await new Promise(r => setTimeout(r, 2000));
      await page.evaluate(() => { for (const l of document.querySelectorAll('a')) { if (l.textContent.trim() === '精简') { l.click(); return; } } }).catch(()=>{});
      await new Promise(r => setTimeout(r, 1500));

      const found = await page.evaluate((home, away) => {
        for (const tr of document.querySelectorAll('tr')) {
          const tds = tr.querySelectorAll('td');
          if (tds.length < 8) continue;
          const hText = (tds[4]?.textContent || '').trim();
          const aText = (tds[6]?.textContent || '').trim();
          if ((hText.includes(home) || home.includes(hText)) &&
              (aText.includes(away) || away.includes(aText))) {
            return { score: (tds[5]?.textContent || '').trim() };
          }
        }
        return null;
      }, p.home, p.away);

      if (!found) {
        await page.goto('https://live.nowscore.com/schedule.aspx?f=ft1', { waitUntil: 'domcontentloaded', timeout: 15000 }).catch(()=>{});
        await new Promise(r => setTimeout(r, 2000));
        const foundFt = await page.evaluate((home, away) => {
          for (const tr of document.querySelectorAll('tr')) {
            const tds = tr.querySelectorAll('td');
            if (tds.length < 8) continue;
            const hText = (tds[3]?.textContent || '').trim();
            const aText = (tds[6]?.textContent || '').trim();
            if ((hText.includes(home) || home.includes(hText)) &&
                (aText.includes(away) || away.includes(aText))) {
              return { score: (tds[4]?.textContent || '').trim() };
            }
          }
          return null;
        }, p.home, p.away);
        if (!foundFt) { console.log('未找到\n'); continue; }
        const parts = foundFt.score.match(/(\d+)-(\d+)/);
        if (!parts) { console.log('比分异常\n'); continue; }
        p.verified = true;
        p.htScore = foundFt.score;
        p.htHasGoal = parseInt(parts[1]) + parseInt(parts[2]) > 0;
        // 尝试判断让球盘结果（如果初盘数据有）
        if (p.ftHandicapInit !== null && p.ftHandicapInit !== undefined) {
          const homeScore = parseInt(parts[1]);
          const awayScore = parseInt(parts[2]);
          const adjustedHome = homeScore + p.ftHandicapInit; // 让球方优势
          if (p.ftHandicapInit > 0) { // 主队让球
            p.ftHandicapResult = (homeScore - awayScore) > p.ftHandicapInit ? 'win' :
                                 (homeScore - awayScore) === p.ftHandicapInit ? 'push' : 'lose';
          } else { // 客队让球
            const handicapAbs = Math.abs(p.ftHandicapInit);
            p.ftHandicapResult = (awayScore - homeScore) > handicapAbs ? 'win' :
                                 (awayScore - homeScore) === handicapAbs ? 'push' : 'lose';
          }
        }
        console.log(`✅ ${foundFt.score}\n`);
      } else {
        const parts = found.score.match(/(\d+)-(\d+)/);
        if (!parts) { console.log('比分异常\n'); continue; }
        p.verified = true;
        p.htScore = found.score;
        p.htHasGoal = parseInt(parts[1]) + parseInt(parts[2]) > 0;
        console.log(`✅ ${found.score}\n`);
      }

      saveJSON(PRED_FILE, preds);
    } catch (e) {
      console.log(`错误: ${e.message.substring(0, 50)}\n`);
    }
  }

  await browser.close();
  const stats = printStats(preds.predictions, `${yesterday} 验证统计`);
  saveJSON(STATS_FILE, { version: 'v38', lastVerified: yesterday, ...stats });
}

main().catch(e => console.error('Fatal:', e.message));
