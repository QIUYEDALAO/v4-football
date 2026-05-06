const { chromium } = require('playwright');

async function main() {
  const browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] });
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  
  // Ah! I just realized - the default page might show "today" which is April 27
  // April 26 matches would have been on Sunday
  // Let me check if the sc1 (April 27 schedule) page actually contains yesterday's matches
  // April 26 might not have a link because it's between ft1 (Apr 25) and sc1 (Apr 27)
  
  // Let me check the "近日赛程" page (schedule) for the last few days
  await page.goto('https://live.nowscore.com/schedule.aspx?f=sc1', { waitUntil: 'networkidle', timeout: 60000 });
  await page.waitForTimeout(8000);
  
  const text = await page.evaluate(() => document.body.innerText);
  const lines = text.split('\n').filter(l => l.trim());
  
  console.log('=== DATES ON sc1 PAGE ===');
  lines.filter(l => l.includes('2026-')).forEach(l => console.log(l));
  
  console.log('\n=== FIRST 30 LINES ===');
  lines.slice(0, 30).forEach(l => console.log(l));
  
  // Check the page title/header
  console.log('\n=== MATCHES FROM RELEVANT LEAGUES ===');
  const v17Leagues = ['荷甲','意甲','俄超','比甲','挪超','苏超冠','瑞典超','奥甲冠',
    '德甲','西甲','巴西甲','美职业'];
  lines.forEach(l => {
    for (const league of v17Leagues) {
      if (l.includes(league)) {
        console.log(l.replace(/\t/g, ' | '));
        break;
      }
    }
  });
  
  // The match times will tell us the date
  // Need to find the correct page for April 26
  
  await browser.close();
}

main().catch(e => { console.error(e); process.exit(1); });
