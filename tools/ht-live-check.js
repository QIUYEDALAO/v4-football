#!/usr/bin/env node
/**
 * HT Live Check v6 — 基于 Playwright DOM 解析
 * 
 * 表结构: 每个比赛行=联赛头+数据合一
 * cells: [0]checkbox [1]联赛名(sclassName) [2]时间 [3]状态(minute) [4]主队 [5]比分 [6]客队 [7]角/半 [8-13]其他
 *
 * 用法: node tools/ht-live-check.js
 */

const { chromium } = require('playwright');

const LEAGUE_WL = [
  '英超','西甲','意甲','德甲','法甲',
  '荷甲','葡超','比甲','苏超','土超','俄超',
  '挪超','瑞典超','丹超','奥甲','瑞士超',
  '英冠','德乙','西乙','意乙','法乙',
  '日职','韩K','澳超',
  '美职业','墨西联','巴西甲','阿甲',
];

const inWL = n => n ? LEAGUE_WL.some(w => n.includes(w)) : false;

async function main() {
  const bj = new Date(Date.now()+8*3600000);
  console.log(`⚽ 半场实时检查 — ${bj.toLocaleString('zh-CN')}`);
  console.log('='.repeat(60));

  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    viewport: { width: 1280, height: 900 },
  });

  await page.goto('https://live.nowscore.com/2in1.aspx', { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.waitForFunction(() => {
    const t = document.getElementById('table_live');
    return t && t.rows.length > 10 && t.rows[1].cells.length >= 8;
  }, { timeout: 15000 });
  await page.waitForTimeout(2000);

  const matches = await page.evaluate(() => {
    const table = document.getElementById('table_live');
    if (!table) return [];
    const rows = table.rows;
    const out = [];
    let currentLeague = '';

    for (let i = 0; i < rows.length; i++) {
      const row = rows[i];
      const cells = row.cells;
      if (cells.length < 8) continue; // skip separator/info rows

      // Cell indices as observed from the page:
      // [0]=checkbox, [1]=league name(sclassName), [2]=time, [3]=status(minute),
      // [4]=home team, [5]=score, [6]=away team, [7]=corner/half
      const cell1 = cells[1];
      const isLeagueHead = cell1 && cell1.className && cell1.className.includes('sclassName');

      if (isLeagueHead) {
        currentLeague = cell1.textContent.trim();
      }

      // Try to parse as match row regardless
      const scoreCell = cells[5];
      if (!scoreCell) continue;
      const scoreText = scoreCell.textContent.trim();
      const scoreParts = scoreText.split('-');
      if (scoreParts.length !== 2) continue;

      const hs = parseInt(scoreParts[0]), as = parseInt(scoreParts[1]);
      if (isNaN(hs) || isNaN(as)) continue;
      if (scoreText === '比分') continue; // header row

      // Minute/status
      const statusText = cells[3]?.textContent?.trim() || '';
      const minuteMatch = statusText.match(/(\d+)/);
      const minute = minuteMatch ? parseInt(minuteMatch[1]) : 0;
      if (minute < 1 || minute > 99) continue; // not a live match

      // Half time score from corner/half cell
      const extra = cells[7]?.textContent?.trim() || '';
      let htHome = null, htAway = null;
      const pairs = extra.match(/\d+-\d+/g);
      if (pairs && pairs.length >= 2) {
        // Last pair is usually the half score
        const last = pairs[pairs.length - 1].split('-');
        const lh = parseInt(last[0]), la = parseInt(last[1]);
        if (lh !== hs || la !== as) {
          htHome = lh; htAway = la;
        }
      }

      out.push({
        league: currentLeague,
        minute,
        homeName: cells[4]?.textContent?.trim() || '',
        awayName: cells[6]?.textContent?.trim() || '',
        homeScore: hs,
        awayScore: as,
        htHome,
        htAway,
        extra,
      });
    }
    return out;
  });

  await browser.close();

  console.log(`  获取 ${matches.length} 场比赛中`);

  const wl = matches.filter(m => inWL(m.league));
  const htList = wl.filter(m => 
    m.htHome !== null && m.htAway !== null &&
    m.homeScore === m.htHome && m.awayScore === m.htAway &&
    m.minute >= 40 && m.minute <= 52
  );
  const shList = wl.filter(m => !htList.includes(m) && m.minute >= 46);

  console.log(`  白名单进行中: ${wl.length} 场`);
  console.log(`  中场休息: ${htList.length} 场`);
  console.log(`  下半场: ${shList.length} 场`);

  if (htList.length > 0) {
    console.log('\n' + '🔴'.repeat(26));
    console.log('🔴  中场休息 — 下半场推荐');
    console.log('🔴'.repeat(26));
    for (const m of htList) {
      const ht = `${m.htHome}-${m.htAway}`;
      const total = m.htHome + m.htAway;
      console.log(`\n  ┌─ ${m.league}`);
      console.log(`  │ ${m.homeName}  ${m.homeScore}-${m.awayScore}  ${m.awayName}`);
      console.log(`  │ 半场: ${ht} | ${m.minute}' | 总进球: ${total}`);
      console.log(`  │ ${total >= 2 ? '✅🔥 半场≥2球, 下半场追大球' : total === 1 ? '✅ 半场1球, 观望前15分钟' : '❌ 半场0-0'}`);
      console.log(`  └─`);
    }
  }

  console.log('\n📋 白名单 — 全部进行中:');
  wl.sort((a,b) => a.minute - b.minute);
  for (const m of wl) {
    const ft = `${m.homeScore}-${m.awayScore}`;
    const ht = m.htHome !== null ? `半:${m.htHome}-${m.htAway}` : '';
    const tag = htList.includes(m) ? '⏸️' : '⚽';
    console.log(`  ${m.league.padEnd(10)} ${tag} ${String(m.minute).padStart(2)}' ${m.homeName.padEnd(14)} ${ft.padStart(5)} ${m.awayName.padEnd(14)} ${ht}`);
  }

  console.log(`\n${'='.repeat(60)}\n✅ 完成`);
}

main().catch(e => { console.error('❌', e.message); process.exit(1); });
