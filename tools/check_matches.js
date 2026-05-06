const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: false });
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  await page.goto('https://live.nowscore.com/2in1.aspx', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(5000);

  // Click 精简
  try {
    await page.evaluate(() => { for (const el of document.querySelectorAll('a')) { if (el.textContent.trim() === '精简') { el.click(); return; } } });
    await page.waitForTimeout(3000);
  } catch (e) {}

  const text = await page.evaluate(() => document.body.innerText);
  const lines = text.split('\n');
  
  // Count all lines matching match pattern
  const allMatches = [];
  const upcomingMatches = [];
  
  for (const line of lines) {
    const raw = line.split('\t');
    if (raw.length >= 7) {
      const league = raw[1]?.trim() || '';
      const time = raw[2]?.trim() || '';
      const home = raw[3]?.trim() || raw[4]?.trim() || '';
      const status = raw[5]?.trim() || '';
      const away = raw[6]?.trim() || '';
      
      // try detect match line: has league, time, home, away
      if (league && time && home && away && time.match(/^\d{2}:\d{2}$/)) {
        allMatches.push({ league, time, home, status, away });
        
        // 未开赛: 阵容 或 -
        if (status === '阵容' || status === '-') {
          upcomingMatches.push({ league, time, home, away });
        }
      }
    }
  }

  console.log(`总比赛行: ${allMatches.length}`);
  console.log(`未开赛(阵容/-): ${upcomingMatches.length}`);
  console.log();
  
  // Show status distribution
  const statusCount = {};
  for (const m of allMatches) {
    statusCount[m.status] = (statusCount[m.status] || 0) + 1;
  }
  console.log('状态分布:', JSON.stringify(statusCount, null, 2));
  console.log();
  
  // Show all upcoming matches
  console.log('=== 全部未开赛比赛 ===');
  for (const m of upcomingMatches) {
    console.log(`${m.time} | ${m.league.padEnd(10)} | ${m.home} vs ${m.away}`);
  }
  
  // Show by time range
  const byHour = {};
  for (const m of upcomingMatches) {
    const h = m.time.split(':')[0];
    byHour[h] = (byHour[h] || 0) + 1;
  }
  console.log('\n按时段分布:', JSON.stringify(byHour, null, 2));
  
  // Check: time filter in V26 is 03:30+ (210 min)
  const after0330 = upcomingMatches.filter(m => {
    const [hh, mm] = m.time.split(':').map(Number);
    return hh * 60 + mm >= 210;
  });
  console.log(`\n03:30之后未开赛: ${after0330.length}场`);
  
  await browser.close();
})();
