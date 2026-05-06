const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: false });
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  await page.goto('https://live.nowscore.com/schedule.aspx?f=ft1', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(5000);
  
  const text = await page.evaluate(() => document.body.innerText);
  const lines = text.split('\n');
  
  // Parse matches: league \t time \t 完 \t home \t ftScore \t away \t htScore
  const matches = [];
  for (const line of lines) {
    const parts = line.split('\t');
    if (parts.length >= 7 && parts[2]?.trim() === '完') {
      const league = parts[0]?.trim() || '';
      const time = parts[1]?.trim() || '';
      const home = (parts[3]?.trim() || '').replace(/\[.*\]/, '').trim();
      const ftScore = parts[4]?.trim() || '';
      const away = (parts[5]?.trim() || '').replace(/\[.*\]/, '').trim();
      const htScore = parts[6]?.trim() || '';
      if (ftScore.match(/^\d+-\d+$/) && htScore.match(/^\d+-\d+$/)) {
        matches.push({ league, time, home, away, ft: ftScore, ht: htScore });
      }
    }
  }
  
  // Also check ongoing matches (进行中)
  for (const line of lines) {
    const parts = line.split('\t');
    if (parts.length >= 7) {
      const status = parts[2]?.trim() || '';
      if (status.includes('中') || status.includes('半场') || status.match(/^\d+$/)) {
        const league = parts[0]?.trim() || '';
        const home = (parts[3]?.trim() || '').replace(/\[.*\]/, '').trim();
        const ftScore = parts[4]?.trim() || '';
        const away = (parts[5]?.trim() || '').replace(/\[.*\]/, '').trim();
        const htScore = parts[6]?.trim() || '';
        if (ftScore.match(/^\d+-\d+$/) && htScore.match(/^\d+-\d+$/)) {
          matches.push({ league, time: parts[1]?.trim() || '', home, away, ft: ftScore, ht: htScore, status });
        }
      }
    }
  }
  
  console.log(`完场比赛: ${matches.length} 场\n`);
  
  // V26 recommendations to verify
  const targets = [
    { home: '阿拉尼亚体育', away: '萨姆松体育', league: '土超', rate: 100, type: '⭐推荐' },
    { home: '卡尔马', away: '埃尔夫斯堡', league: '瑞典超', rate: 90, type: '⭐推荐' },
    { home: '巴蒂卡', away: '阿克伦陶里亚蒂', league: '俄超', rate: 83, type: '⭐推荐' },
    { home: '赫根', away: '天狼星', league: '瑞典超', rate: 78, type: '关注' },
    { home: '曼彻斯特联', away: '布伦特福德', league: '英超', rate: 78, type: '关注' },
    { home: '奥尔格里特', away: '代格福什', league: '瑞典超', rate: 75, type: '关注' },
    { home: '贝西克塔斯', away: '卡拉古拉克', league: '土超', rate: 75, type: '关注' },
    { home: '科尼亚体育', away: '特拉布宗体育', league: '土超', rate: 70, type: '关注' },
  ];
  
  console.log('=== V26 验证结果 (2026-04-27) ===\n');
  
  let totalStrong = 0, hitStrong = 0;
  let totalWatch = 0, hitWatch = 0;
  
  for (const t of targets) {
    let found = null;
    for (const m of matches) {
      const hMatch = m.home.includes(t.home) || t.home.includes(m.home);
      const aMatch = m.away.includes(t.away) || t.away.includes(m.away);
      if (hMatch && aMatch) { found = m; break; }
    }
    
    if (found) {
      const [h, a] = found.ht.split('-').map(Number);
      const hasGoal = h + a > 0;
      const icon = hasGoal ? '✅' : '❌';
      const stat = found.status ? found.status : '完';
      console.log(`${icon} ${t.type} | ${t.rate}% | ${t.league} ${t.home} vs ${t.away} | FT:${found.ft} HT:${found.ht} | ${stat}`);
      
      if (t.type === '⭐推荐' || t.rate >= 80) {
        totalStrong++;
        if (hasGoal) hitStrong++;
      } else {
        totalWatch++;
        if (hasGoal) hitWatch++;
      }
    } else {
      console.log(`⏳ ${t.type} | ${t.rate}% | ${t.league} ${t.home} vs ${t.away} | 未找到赛果（可能尚未开赛或进行中）`);
    }
  }
  
  console.log(`\n=== 命中率统计 ===`);
  console.log(`⭐强烈推荐 (≥80%): ${hitStrong}/${totalStrong} = ${totalStrong>0?(hitStrong/totalStrong*100).toFixed(1):'N/A'}%`);
  console.log(`👀关注参考 (70-79%): ${hitWatch}/${totalWatch} = ${totalWatch>0?(hitWatch/totalWatch*100).toFixed(1):'N/A'}%`);
  console.log(`📊 全部: ${hitStrong+hitWatch}/${totalStrong+totalWatch} = ${(totalStrong+totalWatch)>0?((hitStrong+hitWatch)/(totalStrong+totalWatch)*100).toFixed(1):'N/A'}%`);
  
  await browser.close();
})();
