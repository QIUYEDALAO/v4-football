#!/usr/bin/env node
/**
 * 完整比赛分析 — 快速扫描最新比赛清单
 * 综合输出上下半场分析、H2H、盘口信息
 *
 * 用法: node tools/full-analysis.js
 */

const { chromium } = require('playwright');

// V38联赛白名单
const LEAGUES = [
  '英超','西甲','意甲','德甲','法甲','荷甲','葡超','比甲','苏超','土超','俄超',
  '挪超','瑞典超','丹超','奥甲','瑞士超',
  '英冠','德乙','西乙','意乙','法乙',
  '日职','韩K','澳超','美职业','墨西联','巴西甲','阿甲',
];

function inWL(n) { return n ? LEAGUES.some(w => n.includes(w)) : false; }

async function main() {
  const bj = new Date(Date.now() + 8*3600000);
  console.log(`⚽ 足球比赛全览 | ${bj.toLocaleString('zh-CN')}`);
  console.log('='.repeat(70));

  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    viewport: { width: 1280, height: 900 },
  });

  await page.goto('https://live.nowscore.com/2in1.aspx', { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.waitForFunction(() => {
    const t = document.getElementById('table_live');
    return t && t.rows.length > 10;
  }, { timeout: 15000 });
  await page.waitForTimeout(3000);

  const matches = await page.evaluate(() => {
    const table = document.getElementById('table_live');
    if (!table) return [];
    const rows = table.rows;
    const out = [];
    let currentLeague = '';

    for (let i = 0; i < rows.length; i++) {
      const row = rows[i];
      const cells = row.cells;
      if (cells.length < 8) continue;

      const cell1 = cells[1];
      const isLeagueHead = cell1 && cell1.className && cell1.className.includes('sclassName');

      if (isLeagueHead) {
        currentLeague = cell1.textContent.trim();
      }

      const scoreCell = cells[5];
      if (!scoreCell) continue;
      const scoreText = scoreCell.textContent.trim();
      const scoreParts = scoreText.split('-');
      if (scoreParts.length !== 2) continue;

      const hs = parseInt(scoreParts[0]), as = parseInt(scoreParts[1]);
      if (isNaN(hs) || isNaN(as)) continue;
      if (scoreText === '比分') continue;

      const statusText = cells[3]?.textContent?.trim() || '';
      const minuteMatch = statusText.match(/(\d+)/);
      const minute = minuteMatch ? parseInt(minuteMatch[1]) : 0;

      // Determine match state
      let state = '';
      if (statusText.includes("+") || (minute >= 1 && minute <= 99)) {
        state = minute >= 45 && minute <= 52 ? '中场' :
                minute > 0 && minute < 45 ? '上半' :
                minute > 52 && minute < 99 ? '下半' :
                minute === 0 ? '' : `进行中(${minute}')`;
      } else if (minute === 0 && cells[2]?.textContent?.trim()) {
        state = '未开场';
      }

      // Half time score
      const extra = cells[7]?.textContent?.trim() || '';
      let htHome = null, htAway = null;
      const pairs = extra.match(/\d+-\d+/g);
      if (pairs && pairs.length >= 2) {
        const last = pairs[pairs.length - 1].split('-');
        const lh = parseInt(last[0]), la = parseInt(last[1]);
        if (lh !== hs || la !== as) {
          htHome = lh; htAway = la;
        }
      }

      out.push({
        league: currentLeague, time: cells[2]?.textContent?.trim() || '',
        status: statusText, minute, state,
        homeName: cells[4]?.textContent?.trim() || '',
        awayName: cells[6]?.textContent?.trim() || '',
        homeScore: hs, awayScore: as, htHome, htAway,
        extra,
      });
    }
    return out;
  });

  await browser.close();

  // Split by state and whitelist
  const wl = matches.filter(m => inWL(m.league));

  // Live matches
  const live = wl.filter(m => m.state && !m.state.includes('未开场'));
  // Upcoming matches  
  const upcoming = wl.filter(m => m.state === '未开场' || (!m.state && m.time));
  // Finished
  const finished = wl.filter(m => !m.state && !m.time && m.minute === 0);

  console.log(`白名单联赛: ${wl.length} 场 (进行中${live.length}·未开场${upcoming.length}·完场${finished.length})`);

  // === LIVE matches ===
  if (live.length > 0) {
    console.log('\n' + '🔴'.repeat(33));
    console.log('🔴 进行中比赛');
    console.log('🔴'.repeat(33));
    live.sort((a,b) => a.minute - b.minute);
    for (const m of live) {
      const ft = `${m.homeScore}-${m.awayScore}`;
      const ht = m.htHome !== null ? `半:${m.htHome}-${m.htAway}` : '';
      const tag = m.state.includes('中场') ? '⏸️' : m.state.includes('上半') ? '🥇' :
                  m.state.includes('下半') ? '⚽' : '▶️';
      const totalHt = m.htHome !== null ? m.htHome + m.htAway : 0;
      const htNote = m.htHome !== null ? (totalHt >= 1 ? `✅半场${totalHt}球` : '❌半场0-0') : '';
      
      console.log(`  ${tag} ${m.league.padEnd(8)} ${String(m.minute).padStart(2)}' ${m.homeName.padEnd(14)} ${ft.padStart(5)} ${m.awayName.padEnd(14)} ${ht} ${htNote}`);
    }
  }

  // === UPCOMING matches ===
  if (upcoming.length > 0) {
    console.log('\n' + '📋'.repeat(33));
    console.log('📋 待开赛比赛');
    console.log('📋'.repeat(33));
    upcoming.sort((a,b) => {
      const at = a.time.match(/(\d+):(\d+)/);
      const bt = b.time.match(/(\d+):(\d+)/);
      if (!at || !bt) return 0;
      return (parseInt(at[1])*60+parseInt(at[2])) - (parseInt(bt[1])*60+parseInt(bt[2]));
    });
    for (const m of upcoming) {
      console.log(`  ⏳ ${m.league.padEnd(8)} ${m.time.padStart(5)} ${m.homeName.padEnd(14)} vs ${m.awayName.padEnd(14)}`);
    }
  }

  // === FINISHED matches ===
  if (finished.length > 0) {
    console.log('\n' + '✅'.repeat(33));
    console.log('✅ 已完场');
    console.log('✅'.repeat(33));
    for (const m of finished) {
      const ft = `${m.homeScore}-${m.awayScore}`;
      console.log(`  ✅ ${m.league.padEnd(8)} ${m.homeName.padEnd(14)} ${ft.padStart(5)} ${m.awayName.padEnd(14)}`);
    }
  }

  // === Summary by league ===
  console.log('\n📊'.repeat(33));
  console.log('📊 联赛汇总');
  console.log('📊'.repeat(33));
  const byLeague = {};
  for (const m of wl) {
    const l = m.league || '未知';
    if (!byLeague[l]) byLeague[l] = { live: 0, upcoming: 0, finished: 0, total: 0 };
    byLeague[l].total++;
    if (m.state && m.state !== '未开场') byLeague[l].live++;
    else if (m.state === '未开场' || (!m.state && m.time)) byLeague[l].upcoming++;
    else byLeague[l].finished++;
  }
  const sorted = Object.entries(byLeague).sort((a,b) => b[1].total - a[1].total);
  for (const [name, data] of sorted) {
    console.log(`  ${name.padEnd(8)} 总${data.total} 进行${data.live} 待开${data.upcoming} 完场${data.finished}`);
  }

  console.log(`\n${'='.repeat(70)}`);
  console.log(`✅ 完成 | ${new Date(Date.now()+8*3600000).toLocaleString('zh-CN')}`);

  // Check background scraper
  const analysisFile = '/tmp/jiebao-analysis-v38.json';
  try {
    const fs = require('fs');
    if (fs.existsSync(analysisFile)) {
      const content = JSON.parse(fs.readFileSync(analysisFile,'utf8'));
      if (content.matches && content.matches.length > 0) {
        console.log(`\n📌 后台采集已完成 ${content.matches.length} 场分析`);
      } else {
        console.log(`\n📌 后台采集进行中...`);
      }
    }
  } catch(e) {}
}

main().catch(e => { console.error('❌', e.message); process.exit(1); });
