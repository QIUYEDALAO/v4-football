const { chromium } = require('playwright');

async function main() {
  const browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] });
  const ctx = await browser.newContext({ userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36' });
  const page = await ctx.newPage();
  
  // We know from earlier that ft1 data has `'04-25'` and `'04-26'` dates
  // and 1807 total matches. But the V17 matches like Gent vs Brugge, 
  // Molde vs Valerenga etc were played on April 26.
  // Maybe the issue is that these matches have already been cleaned from the ft1 data
  // because it was a new day? Or the date marking is different?
  
  // Let me look at the raw data file directly - the A array structure
  await page.goto('https://live.nowscore.com/data/ft1.js?1777255917000', { waitUntil: 'networkidle', timeout: 30000 });
  const text = await page.evaluate(() => document.body.innerText);
  
  // Save the full raw data to analyze
  const fs = require('fs');
  fs.writeFileSync('/tmp/ft1_full.txt', text);
  
  // Simple string search - look for variants of team names in the entire file
  const searchQueries = [
    '根特', 'Gent', '莫尔德', 'Molde', 'Excelsior', '精英',
    '乌德勒支', 'Utrecht', '诺夫哥罗德', 'Nizhny', 'Novgorod',
    '佛罗伦萨', 'Fiorentina', '萨索洛', 'Sassuolo', '流浪者',
    'Rangers', 'Motherwell', '马瑟韦尔', '莫斯科迪纳摩',
    'Dynamo Moscow', '索契', 'Sochi', '克拉斯诺达尔', 'Krasnodar',
    '布洛马', 'Bromma', '瓦斯特拉斯', 'Vastera', '格拉茨',
    'Sturm Graz', '奥地利', 'Austria', '汉坎', 'HamKam',
    'KFUM', '奥斯陆', 'Sarpsborg', '多特蒙德', 'Dortmund',
    '弗赖堡', 'Freiburg', '利勒斯特', 'Lille', '博德', 'Bodo', 'Glimt',
    '比利亚雷亚尔', 'Villarre', '塞尔塔', 'Celta', '巴拉纳竞技',
    'Athletico PR', 'Paranaense', '维多利亚', 'Vitoria',
    '布拉干蒂诺', 'Bragantino', '帕尔梅拉斯', 'Palmeiras',
    '洛杉矶', 'Galaxy', '盐湖城', 'Salt Lake'
  ];
  
  for (const q of searchQueries) {
    const pos = text.indexOf(q);
    if (pos >= 0) {
      const context = text.substring(Math.max(0, pos - 20), pos + 100);
      console.log(`FOUND "${q}" at position ${pos}: ...${context}...`);
    }
  }
  
  // Also check sc1.js - this might have today's matches that include Apr 26 late matches
  await page.goto('https://live.nowscore.com/data/sc1.js?1777255917000', { waitUntil: 'networkidle', timeout: 30000 });
  const sc1Text = await page.evaluate(() => document.body.innerText);
  
  console.log('\n\n=== CHECKING sc1.js (today completed) ===');
  const sc1Time = sc1Text.match(/'(\d{2}:\d{2})'.*?'(\d{2}-\d{2})'/);
  console.log(`sc1 first match: ${sc1Time ? sc1Time[1] + ' ' + sc1Time[2] : 'N/A'}`);
  
  // Count future matches starting after certain hour (matches that started Apr 26 late)
  const sc1Matches = sc1Text.match(/A\[\d+\]=/g) || [];
  console.log(`sc1 total matches: ${sc1Matches.length}`);
  
  for (const q of ['根特', '莫尔德', 'Excelsior', '流浪者', 'Dortmund', 'Villarre', 'Galaxy']) {
    if (sc1Text.includes(q)) {
      console.log(`FOUND "${q}" in sc1!`);
    }
  }
  
  await browser.close();
}

main().catch(e => { console.error(e); process.exit(1); });
