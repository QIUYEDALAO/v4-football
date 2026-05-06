const { chromium } = require('playwright');

async function main() {
  const browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] });
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  
  await page.goto('https://live.nowscore.com/data/ft1.js?1777255917000', { waitUntil: 'networkidle', timeout: 30000 });
  const text = await page.evaluate(() => document.body.innerText);
  
  // Extract ALL dates found in ft1.js
  const dates = [...text.matchAll(/'(\d{2}:\d{2})','(\d{2}-\d{2})'?/g)];
  console.log(`Total matches in ft1.js: ${dates.length}`);
  
  // Group by date
  const dateGroups = {};
  for (const [_, time, date] of dates) {
    if (!dateGroups[date]) dateGroups[date] = [];
    dateGroups[date].push(time);
  }
  
  console.log('\n=== Dates found in ft1.js ===');
  for (const [date, times] of Object.entries(dateGroups)) {
    console.log(`${date}: ${times.length} matches (${times[0]} - ${times[times.length-1]})`);
  }
  
  // Now find the specific V17 matches in ft1 data
  const v17Teams = [
    'SBV精英','Excelsior','烏德勒支','Utrecht','佛罗伦萨','Fiorentina','萨索洛','Sassuolo',
    '诺夫哥罗德','Nizhny','Nijni','斯巴达','Spartak Moscow',
    '根特','Gent','布鲁日','Brugge',
    '莫尔德','Molde','瓦勒伦加','Valerenga',
    '流浪者','Rangers','马瑟韦尔','Motherwell',
    '莫斯科迪纳摩','Dynamo Moscow','索契','Sochi'
  ];
  
  // Search in Chinese team names
  const lines = text.split('\n');
  console.log('\n=== Searching for V17 teams ===');
  for (const kw of v17Teams) {
    const found = lines.filter(l => l.toLowerCase().includes(kw.toLowerCase()));
    if (found.length > 0) {
      console.log(`${kw}: FOUND (${found.length} match(es))`);
      console.log(found[0].substring(0, 300));
    }
  }
  
  // Check the biggest match (checking for 俄超, 荷甲, 意甲 etc.)
  console.log('\n=== League sample in ft1 ===');
  const leagueSamples = lines.filter(l => l.includes('意甲') || l.includes('俄超') || l.includes('荷甲') || l.includes('比甲'));
  leagueSamples.slice(0, 10).forEach(l => console.log(l.substring(0, 250)));
  
  await browser.close();
}

main().catch(e => { console.error(e); process.exit(1); });
