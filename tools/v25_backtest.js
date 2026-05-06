const { chromium } = require('playwright');
const fs = require('fs');

(async () => {
  const browser = await chromium.launch({ headless: false });
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  await page.goto('https://live.nowscore.com/schedule.aspx?f=ft1', { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.waitForTimeout(5000);
  
  const text = await page.evaluate(() => document.body.innerText);
  fs.writeFileSync('/tmp/ft1_yesterday_full.txt', text);
  
  const lines = text.split('\n');
  const matches = [];
  
  for (let i = 0; i < lines.length; i++) {
    const l = lines[i].trim();
    const tabParts = l.split('\t');
    // Format: league \t time \t 完 \t home[rank] \t ftScore \t away[rank] \t htScore \t ...
    if (tabParts.length >= 7 && tabParts[2]?.trim() === '完') {
      const league = tabParts[0]?.trim() || '';
      const time = tabParts[1]?.trim() || '';
      const homeRaw = tabParts[3]?.trim() || '';
      const ftScore = tabParts[4]?.trim() || '';
      const awayRaw = tabParts[5]?.trim() || '';
      const htScore = tabParts[6]?.trim() || '';
      
      // Clean team names (remove [rank])
      const home = homeRaw.replace(/\[.*\]/, '').trim();
      const away = awayRaw.replace(/\[.*\]/, '').trim();
      
      if (ftScore.match(/^\d+-\d+$/) && htScore.match(/^\d+-\d+$/)) {
        matches.push({ league, time, home, away, ft: ftScore, ht: htScore });
      }
    }
  }
  
  console.log(`解析到 ${matches.length} 场完场比赛\n`);
  
  // Now cross-reference with V17's 18 recommendations from yesterday
  const v17Recs = [
    { home: 'SBV精英', away: '乌德勒支', league: '荷甲' },
    { home: '佛罗伦萨', away: '萨索洛', league: '意甲' },
    { home: '下诺夫哥罗德', away: '莫斯科斯巴达', league: '俄超' },
    { home: '根特', away: '布鲁日', league: '比甲冠' },
    { home: '莫尔德', away: '瓦勒伦加', league: '挪超' },
    { home: '格拉斯哥流浪者', away: '马瑟韦尔', league: '苏超冠' },
    { home: '莫斯科迪纳摩', away: '索契', league: '俄超' },
    { home: '克拉斯诺达尔', away: '马哈奇卡拉', league: '俄超' },
    { home: '布洛马波卡纳', away: '瓦斯特拉斯', league: '瑞典超' },
    { home: '格拉茨风暴', away: '奥地利维也纳', league: '奥甲冠' },
    { home: '汉坎', away: '斯达', league: '挪超' },
    { home: 'KFUM奥斯陆', away: '萨普斯堡', league: '挪超' },
    { home: '多特蒙德', away: '弗赖堡', league: '德甲' },
    { home: '利勒斯特罗姆', away: '博德闪耀', league: '挪超' },
    { home: '比利亚雷亚尔', away: '塞尔塔', league: '西甲' },
    { home: '巴拉纳竞技', away: '维多利亚', league: '巴西甲' },
    { home: '布拉干蒂诺RB', away: '帕尔梅拉斯', league: '巴西甲' },
    { home: '洛杉矶银河', away: '皇家盐湖城', league: '美职业' },
  ];
  
  console.log('=== V17推荐 vs 实际赛果 ===\n');
  let hits = 0, misses = 0, notFound = 0;
  
  for (const rec of v17Recs) {
    let found = null;
    for (const m of matches) {
      if (m.home.includes(rec.home) || rec.home.includes(m.home)) {
        if (m.away.includes(rec.away) || rec.away.includes(m.away)) {
          found = m; break;
        }
      }
      // Try reverse (home/away might be swapped)
      if (m.home.includes(rec.away) || rec.away.includes(m.home)) {
        if (m.away.includes(rec.home) || rec.home.includes(m.away)) {
          found = m; break;
        }
      }
    }
    
    if (found) {
      const [h, a] = found.ht.split('-').map(Number);
      const hasGoal = h + a > 0;
      if (hasGoal) { hits++; status = '✅'; }
      else { misses++; status = '❌'; }
      console.log(`${status} ${rec.league.padEnd(6)} ${rec.home} vs ${rec.away} | FT:${found.ft} HT:${found.ht}`);
    } else {
      notFound++;
      console.log(`⚪ ${rec.league.padEnd(6)} ${rec.home} vs ${rec.away} | NOT FOUND`);
    }
  }
  
  console.log(`\n统计: ✅${hits} ❌${misses} ⚪${notFound} | 命中率 ${(hits/(hits+misses)*100).toFixed(1)}%`);
  
  // Save all matches for reference
  fs.writeFileSync('/tmp/ft1_all_matches.json', JSON.stringify(matches, null, 2));
  console.log(`\n${matches.length}场比赛数据已保存`);
  
  await browser.close();
})().catch(e => { console.error(e); process.exit(1); });
