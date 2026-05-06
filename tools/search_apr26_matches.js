const { chromium } = require('playwright');

async function main() {
  const browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] });
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  
  await page.goto('https://live.nowscore.com/data/ft1.js?1777255917000', { waitUntil: 'networkidle', timeout: 30000 });
  const text = await page.evaluate(() => document.body.innerText);
  
  // Parse the A array more carefully
  // Format: A[i]=[id,leagueIdx,homeId,awayId,'homeCN','homeTW','homeEN','awayCN','awayTW','awayEN','time','date',...]
  // After the 12th element (index 12 = date), we have numbers: status, homeTotal, awayTotal, halfHome, halfAway, ...
  
  const lines = text.split('\n');
  
  // Search terms for each V17 team (CN + EN variants)
  const searchTeams = [
    { home: ['根特','Gent','KAA'], away: ['布鲁日','Brugge','Club Brugge','Club Brugge KV'] },
    { home: ['莫尔德','Molde'], away: ['瓦勒伦加','Valerenga','Vålerenga'] },
    { home: ['SBV精英','精英','Excelsior','SBV Excelsior'], away: ['乌德勒支','Utrecht','FC Utrecht'] },
    { home: ['诺夫哥罗德','Nizhny','Novgorod','FK Nizhny'], away: ['斯巴达莫斯科','Spartak Moscow','莫斯科斯巴达','FK Spartak'] },
    { home: ['佛罗伦萨','Fiorentina','ACF Fiorentina'], away: ['萨索洛','Sassuolo','US Sassuolo'] },
    { home: ['流浪者','Rangers','Glasgow Rangers'], away: ['马瑟韦尔','Motherwell'] },
    { home: ['莫斯科迪纳摩','Dynamo Moscow','FC Dynamo Moscow'], away: ['索契','Sochi','FK Sochi'] },
    { home: ['克拉斯诺达尔','Krasnodar','FC Krasnodar'], away: ['马哈奇卡拉','Makhachkala','Dynamo Makhachkala'] },
    { home: ['布洛马','Brommapojkarna','BP'], away: ['瓦斯特拉斯','Vasteras','Västerås'] },
    { home: ['格拉茨','Sturm Graz','SK Sturm'], away: ['奥地利维也纳','Austria Vienna','FK Austria Wien'] },
    { home: ['汉坎','HamKam','Hamarkameratene'], away: ['斯达','Start','IK Start'] },
    { home: ['KFUM','KFUM Oslo'], away: ['萨普斯堡','Sarpsborg','Sarpsborg 08'] },
    { home: ['多特蒙德','Dortmund','Borussia Dortmund'], away: ['弗赖堡','Freiburg','SC Freiburg'] },
    { home: ['利勒斯特','Lillestrom','Lillestrøm'], away: ['博德闪耀','Bodo','Glint','Bodø/Glimt'] },
    { home: ['比利亚雷亚尔','Villarreal','Villarreal CF'], away: ['塞尔塔','Celta','Celta Vigo'] },
    { home: ['巴拉纳竞技','Athletico PR','Athletico Paranaense','Paranaense'], away: ['维多利亚','Vitoria','EC Vitoria'] },
    { home: ['布拉干蒂诺','Bragantino','Red Bull Bragantino'], away: ['帕尔梅拉斯','Palmeiras','SE Palmeiras'] },
    { home: ['洛杉矶银河','LA Galaxy','Galaxy'], away: ['盐湖城','Salt Lake','Real Salt Lake'] }
  ];
  
  // Find data for Apr 26 matches
  function findMatch(homeTeamName, awayTeamName) {
    // Search for line containing both team names on 04-26 date
    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed.startsWith('A[')) continue;
      
      // Check if contains both team names (any variant) and date 04-26
      const team1Match = homeTeamName.some(t => trimmed.includes(t));
      const team2Match = awayTeamName.some(t => trimmed.includes(t));
      
      if (team1Match && team2Match) {
        // Check if it's an Apr 26 match
        if (trimmed.includes("'04-26'") || trimmed.includes("'04-26,")) {
          return trimmed;
        }
      }
    }
    return null;
  }
  
  console.log('=== V17 TEAM SEARCH RESULTS ===');
  console.log('');
  
  for (const [idx, teams] of searchTeams.entries()) {
    const result = findMatch(teams.home, teams.away);
    const matchName = `Match ${idx+1}: ${teams.home[0]} vs ${teams.away[0]}`;
    
    if (result) {
      console.log(`${matchName} ✓`);
      console.log(`  ${result.substring(0, 350)}`);
    } else {
      console.log(`${matchName} ✗ NOT FOUND`);
    }
  }
  
  // ALSO search just for 04-26 matches in general to see what leagues are there
  console.log('\n\n=== SAMPLE OF 04-26 MATCHES IN ft1.js ===');
  let count = 0;
  for (const line of lines) {
    if (line.includes("'04-26'") && line.startsWith('A[')) {
      // Extract the Chinese team names
      const quoted = line.match(/'[^']*'/g);
      if (quoted && quoted.length >= 8) {
        const homeCN = quoted[0].replace(/'/g,'');
        const awayCN = quoted[3].replace(/'/g,'');
        const time = quoted[6].replace(/'/g,'');
        console.log(`  ${time} ${homeCN} vs ${awayCN}`);
        count++;
        if (count >= 30) break;
      }
    }
  }
  
  await browser.close();
}

main().catch(e => { console.error(e); process.exit(1); });
