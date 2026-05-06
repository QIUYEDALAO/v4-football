const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] });
  const ctx = await browser.newContext({
    userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
  });
  const page = await ctx.newPage();
  await page.goto('https://live.nowscore.com/2in1.aspx', { 
    waitUntil: 'networkidle', timeout: 60000 
  });
  await page.waitForTimeout(3000);

  // Get match data from page
  const matchData = await page.evaluate(() => {
    const text = document.body.innerText;
    const lines = text.split('\n');
    return lines;
  });

  // Known results from earlier page scrape
  const results = {
    'SBV精英': 'FT 5-0 乌德勒支 corner 3-2 HT 2-0',
    '佛罗伦萨': 'FT 0-0 萨索洛 corner 7-4 HT 0-0',
    '下诺夫哥罗德': 'FT 1-2 莫斯科斯巴达 corner 3-7 HT 1-1',
    '根特': 'FT 0-2 布鲁日 corner 7-9 HT 0-1',
    '莫尔德': 'FT 5-1 瓦勒伦加 corner 2-5 HT 1-1',
    '格拉斯哥流浪者': 'FT 2-3 马瑟韦尔 corner 8-5 HT 0-2',
    '莫斯科迪纳摩': 'FT 2-0 索契 corner 5-5 HT 1-0',
    '克拉斯诺达尔': 'FT 2-1 马哈奇卡拉 corner 8-4 HT 1-1',
    '布洛马波卡纳': 'NOT FOUND ON PAGE',
    '格拉茨风暴': 'FT 1-1 奥地利维也纳 corner 4-3 HT 0-0',
    '汉坎': 'FT 2-1 斯达 corner 5-1 HT 0-0',
    'KFUM奥斯陆': 'FT 1-0 萨普斯堡 corner 1-2 HT 1-0',
    '多特蒙德': 'FT 4-0 弗赖堡 corner 5-0 HT 3-0',
    '利勒斯特罗姆': 'NOT FOUND ON PAGE - check below',
    '比利亚雷亚尔': 'FT 2-1 塞尔塔 corner 7-5 HT 2-0',
    '巴拉纳竞技': 'NOT FOUND ON PAGE - check below',
    '布拉干蒂诺RB': 'FT 0-1 帕尔梅拉斯 corner 9-4 HT 0-1',
    '洛杉矶银河': 'FT 2-1 皇家盐湖城 corner 7-0 HT 1-1'
  };

  // Check for missing teams
  console.log('=== SEARCHING FOR MISSING TEAMS ===\n');
  const missingTeams = ['布洛马波卡纳', '利勒斯特罗姆', '博德闪耀', '巴拉纳竞技', '维多利亚'];
  for (const team of missingTeams) {
    for (let i = 0; i < matchData.length; i++) {
      if (matchData[i].includes(team)) {
        const ctx = [];
        for (let j = Math.max(0, i-2); j <= Math.min(matchData.length-1, i+5); j++) {
          ctx.push(matchData[j].trim());
        }
        console.log(`Found ${team}: ${ctx.join(' | ').substring(0, 200)}`);
        break;
      }
    }
  }

  // Print table
  console.log('\n\n=== V17 18场完整验证 ===\n');
  
  const v17Matches = [
    [1,  '18:15', '荷甲', 'SBV精英 vs 乌德勒支', '1.34球', '81%', '大1', '投大1'],
    [2,  '18:30', '意甲', '佛罗伦萨 vs 萨索洛', '1.23球', '80%', '大1', '投大1'],
    [3,  '19:00', '俄超', '下诺夫哥罗德 vs 莫斯科斯巴达', '1.51球', '81%', '大1', '强烈推荐'],
    [4,  '19:30', '比甲冠', '根特 vs 布鲁日', '1.40球', '84%', '大1/1.5', '投大1/1.5'],
    [5,  '20:30', '挪超', '莫尔德 vs 瓦勒伦加', '1.39球', '84%', '大1/1.5', '投大1/1.5'],
    [6,  '22:00', '苏超冠', '格拉斯哥流浪者 vs 马瑟韦尔', '1.57球', '87%', '大1/1.5', '强烈推荐'],
    [7,  '22:00', '俄超', '莫斯科迪纳摩 vs 索契', '1.65球', '84%', '大1/1.5', '强烈推荐'],
    [8,  '22:00', '俄超', '克拉斯诺达尔 vs 马哈奇卡拉', '1.26球', '80%', '大1', '投大1'],
    [9,  '22:30', '瑞典超', '布洛马波卡纳 vs 瓦斯特拉斯', '1.69球', '87%', '大1', '强烈推荐'],
    [10, '23:00', '奥甲冠', '格拉茨风暴 vs 奥地利维也纳', '1.63球', '83%', '大1', '强烈推荐'],
    [11, '23:00', '挪超', '汉坎 vs 斯达', '1.51球', '83%', '大1', '强烈推荐'],
    [12, '23:00', '挪超', 'KFUM奥斯陆 vs 萨普斯堡', '1.63球', '85%', '大1/1.5', '强烈推荐'],
    [13, '23:30', '德甲', '多特蒙德 vs 弗赖堡', '1.32球', '83%', '大1/1.5', '投大1/1.5'],
    [14, '01:15', '挪超', '利勒斯特罗姆 vs 博德闪耀', '1.39球', '80%', '大0.5', '投大0.5'],
    [15, '03:00', '西甲', '比利亚雷亚尔 vs 塞尔塔', '1.66球', '87%', '大1', '强烈推荐'],
    [16, '05:30', '巴西甲', '巴拉纳竞技 vs 维多利亚', '1.59球', '83%', '大1', '强烈推荐'],
    [17, '05:30', '巴西甲', '布拉干蒂诺RB vs 帕尔梅拉斯', '1.29球', '81%', '大1', '投大1'],
    [18, '07:00', '美职业', '洛杉矶银河 vs 皇家盐湖城', '1.63球', '80%', '大1/1.5', '强烈推荐']
  ];

  console.log('序号 | 时间 | 联赛 | 比赛 | 预测进球 | 有进球率 | 盘口 | 投注建议 | 实际半场 | 结果');
  console.log('--- | --- | --- | --- | --- | --- | --- | --- | --- | ---');

  let hits = 0, misses = 0, notFound = 0;

  for (const m of v17Matches) {
    const [no, time, league, match, predGoals, rate, handicap, suggestion] = m;
    const homeTeam = match.split(' vs ')[0];
    
    let htScore = 'N/A';
    let result = '⚪';
    
    for (const [key, val] of Object.entries(results)) {
      if (homeTeam.includes(key) || key.includes(homeTeam)) {
        const htMatch = val.match(/HT\s+(\d+-\d+)/);
        if (htMatch) {
          htScore = htMatch[1];
          const [h, a] = htScore.split('-').map(Number);
          if (h + a > 0) { result = '✅'; hits++; }
          else { result = '❌'; misses++; }
        }
        break;
      }
    }
    
    if (result === '⚪') {
      // Search in matchData
      let found = false;
      for (let i = 0; i < matchData.length; i++) {
        if (matchData[i].includes(homeTeam)) {
          const htMatch = matchData[i+2] ? matchData[i+2].match(/^(\d+)-(\d+)$/) : null;
          if (htMatch) {
            htScore = htMatch[0];
            const h = parseInt(htMatch[1]);
            const a = parseInt(htMatch[2]);
            if (h + a > 0) { result = '✅'; hits++; }
            else { result = '❌'; misses++; }
            found = true;
          }
          break;
        }
      }
      if (!found) {
        result = '⚪(查不到)';
        notFound++;
      }
    }

    console.log(`${no} | ${time} | ${league} | ${match} | ${predGoals} | ${rate} | ${handicap} | ${suggestion} | ${htScore} | ${result}`);
  }

  console.log(`\n\n统计: ✅命中 ${hits} | ❌未中 ${misses} | ⚪查不到 ${notFound} | 总 ${v17Matches.length}`);
  console.log(`命中率: ${(hits/(hits+misses)*100).toFixed(1)}% (仅计有数据比赛)`);
  
  await browser.close();
})().catch(e => { console.error(e); process.exit(1); });
