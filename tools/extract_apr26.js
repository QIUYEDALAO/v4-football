const { chromium } = require('playwright');
const fs = require('fs');

async function main() {
  const browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] });
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  
  await page.goto('https://live.nowscore.com/data/ft1.js?1777255917000', { waitUntil: 'networkidle', timeout: 30000 });
  const text = await page.evaluate(() => document.body.innerText);
  
  // Save the raw data for analysis
  fs.writeFileSync('/tmp/ft1_raw.txt', text);
  
  // Parse A array (matches data)
  // Each A[i] = [id, leagueIdx, homeTeamId, awayTeamId, homeName_CN, homeName_TW, homeName_EN,
  //                awayName_CN, awayName_TW, awayName_EN, time, date, isFinished, totalHome, totalAway, 
  //                halfHome, halfAway, ...]
  // Position 11 = time (e.g. '10:30'), position 12 = date (e.g. '04-25')
  // Position 13 = status (-1 = finished, etc)
  // Position 14 = home total goals, 15 = away total goals
  // Position 16 = half time home, 17 = half time away
  
  const lines = text.split('\n');
  const v17TeamNames = {
    '格拉斯哥流浪者': 'Rangers',
    '马瑟韦尔': 'Motherwell',
    '莫尔德': 'Molde',
    '瓦勒伦加': 'Valerenga',
    'SBV精英': 'Excelsior',
    '乌德勒支': 'Utrecht',
    '根特': 'Gent',
    '布鲁日': 'Club Brugge',
    '佛罗伦萨': 'Fiorentina',
    '萨索洛': 'Sassuolo',
    '下诺夫哥罗德': 'Nizhny Novgorod',
    '莫斯科斯巴达': 'Spartak Moscow',
    '莫斯科迪纳摩': 'Dynamo Moscow',
    '索契': 'Sochi',
    '克拉斯诺达尔': 'Krasnodar',
    '马哈奇卡拉': 'Dynamo Makhachkala',
    '布洛马波卡纳': 'Brommapojkarna',
    '瓦斯特拉斯': 'Vasteras',
    '格拉茨风暴': 'Sturm Graz',
    '奥地利维也纳': 'Austria Vienna',
    '汉坎': 'HamKam',
    '斯达': 'Start',
    'KFUM奥斯陆': 'KFUM Oslo',
    '萨普斯堡': 'Sarpsborg',
    '多特蒙德': 'Dortmund',
    '弗赖堡': 'Freiburg',
    '利勒斯特罗姆': 'Lillestrom',
    '博德闪耀': 'Bodo/Glimt',
    '比利亚雷亚尔': 'Villarreal',
    '塞尔塔': 'Celta Vigo',
    '巴拉纳竞技': 'Athletico Paranaense',
    '维多利亚': 'Vitoria',
    '布拉干蒂诺RB': 'Bragantino',
    '帕尔梅拉斯': 'Palmeiras',
    '洛杉矶银河': 'LA Galaxy',
    '皇家盐湖城': 'Real Salt Lake'
  };
  
  // Extract ALL Apr 26 matches from ft1.js
  const allApr26Matches = [];
  
  for (const line of lines) {
    const trimmed = line.trim();
    if (trimmed.startsWith('A[')) {
      try {
        // Find date field (position 12) and time (position 11)
        // Format: A[i]=[id,league,htid,atid,'cn','tw','en','acn','atw','aen','time','date',...]
        const parts = trimmed.match(/'(.*?)'/g);
        if (!parts) continue;
        
        // Get date from positions
        // The quoted strings in order: homeCN, homeTW, homeEN, awayCN, awayTW, awayEN, time, date
        // But there could be escaping issues...
        const matchParts = trimmed.match(/'([^']*)'/g);
        if (matchParts && matchParts.length >= 12) {
          const homeCN = matchParts[0].replace(/'/g, '');
          const awayCN = matchParts[3].replace(/'/g, '');
          const timeVal = matchParts[6].replace(/'/g, '');
          const dateVal = matchParts[7].replace(/'/g, '');
          
          if (dateVal === '04-26') {
            allApr26Matches.push({
              line: trimmed.substring(0, 300),
              home: homeCN,
              away: awayCN,
              time: timeVal,
              date: dateVal
            });
          }
        }
      } catch(e) {}
    }
  }
  
  console.log(`Found ${allApr26Matches.length} matches on 04-26`);
  
  // Now search for our specific V17 matches
  // Better approach: use the regex to parse the JS arrays properly
  // A[i]=[id, leagueIdx, ...] format
  // Let me use a more direct approach
  
  const matchPattern = /A\[\d+\]=\[([^\]]+)\]/g;
  let match;
  const apr26Data = [];
  
  while ((match = matchPattern.exec(text)) !== null) {
    const arrStr = match[1];
    const parts = arrStr.split(',');
    
    // The array format is:
    // [matchId, leagueIdx, homeId, awayId, 'homeCN','homeTW','homeEN','awayCN','awayTW','awayEN','time','date',status, ...]
    // Quoted strings are single fields, but the ',' inside them are within quotes
    // So we need the 12th-13th quoted strings = time, date
    const quoted = arrStr.match(/'[^']*'/g);
    if (!quoted || quoted.length < 8) continue;
    
    const time = quoted[6].replace(/'/g, '');
    const date = quoted[7].replace(/'/g, '');
    
    if (date === '04-26') {
      const homeCN = quoted[0].replace(/'/g, '');
      const awayCN = quoted[3].replace(/'/g, '');
      
      // Get scores from the numeric parts
      const numParts = arrStr.split(',').filter(p => !p.includes("'") && !isNaN(parseInt(p)) && p.trim() !== '');
      // After the 10th quoted string and 12 date/time quotes, we have status, homeTotal, awayTotal, halfHome, halfAway
      // The numeric values after 'time','date' 
      
      // Let me just parse the full array
      try {
        const fullArr = JSON.parse('[' + arrStr + ']');
        const homeTotal = fullArr[13]; // index 13 = home total goals
        const awayTotal = fullArr[14]; // index 14 = away total goals
        const halfHome = fullArr[15];  // index 15 = half time home goals
        const halfAway = fullArr[16];  // index 16 = half time away goals
        
        apr26Data.push({
          home: homeCN,
          away: awayCN,
          time: time,
          homeTotal: homeTotal,
          awayTotal: awayTotal,
          halfHome: halfHome,
          halfAway: halfAway,
          hasHTGoal: halfHome + halfAway > 0
        });
      } catch(e) {
        // JSON parse might fail for arrays with empty strings
      }
    }
  }
  
  // Output all Apr 26 matches
  console.log(`\n=== PARSED ${apr26Data.length} Apr 26 matches ===`);
  
  // Now match against V17 matches
  const v17Matches = [
    { home: '根特', away: '布鲁日' },
    { home: '莫尔德', away: '瓦勒伦加' },
    { home: 'SBV精英', away: '乌德勒支' },
    { home: '下诺夫哥罗德', away: '莫斯科斯巴达' },
    { home: '佛罗伦萨', away: '萨索洛' },
    { home: '格拉斯哥流浪者', away: '马瑟韦尔' },
    { home: '莫斯科迪纳摩', away: '索契' },
    { home: '克拉斯诺达尔', away: '马哈奇卡拉' },
    { home: '布洛马波卡纳', away: '瓦斯特拉斯' },
    { home: '格拉茨风暴', away: '奥地利维也纳' },
    { home: '汉坎', away: '斯达' },
    { home: 'KFUM奥斯陆', away: '萨普斯堡' },
    { home: '多特蒙德', away: '弗赖堡' },
    { home: '利勒斯特罗姆', away: '博德闪耀' },
    { home: '比利亚雷亚尔', away: '塞尔塔' },
    { home: '巴拉纳竞技', away: '维多利亚' },
    { home: '布拉干蒂诺RB', away: '帕尔梅拉斯' },
    { home: '洛杉矶银河', away: '皇家盐湖城' }
  ];
  
  console.log('\n=== MATCHING V17 RESULTS ===');
  for (const vm of v17Matches) {
    const found = apr26Data.filter(m => 
      (m.home.includes(vm.home) || m.home.includes(vm.away)) ||
      (m.away.includes(vm.home) || m.away.includes(vm.away))
    );
    
    if (found.length > 0) {
      for (const f of found) {
        console.log(`${vm.home} vs ${vm.away} → FT ${f.homeTotal}-${f.awayTotal} HT ${f.halfHome}-${f.halfAway} (上半场${f.hasHTGoal ? '有✅' : '无❌'}进球)`);
      }
    } else {
      console.log(`${vm.home} vs ${vm.away} → NOT FOUND in ft1.js Apr 26 data`);
    }
  }
  
  await browser.close();
}

main().catch(e => { console.error(e); process.exit(1); });
