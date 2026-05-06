const { chromium } = require('playwright');

async function main() {
  const browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] });
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  
  // Let me check: the page might be showing Apr 26 already (Sunday).
  // The dates in the nav are what's available:
  // ft1=Apr25, ft2=Apr24, ..., ft7=Apr19
  // sc1=Apr27, sc2=Apr28, ..., sc7=May3
  // Apr 26 might be the current/default view (no f parameter)
  
  // Let's try loading the base URL without parameters
  await page.goto('https://live.nowscore.com/schedule.aspx', { waitUntil: 'networkidle', timeout: 60000 });
  await page.waitForTimeout(8000);
  
  const text = await page.evaluate(() => document.body.innerText);
  const lines = text.split('\n').filter(l => l.trim());
  
  // Find ALL matches with relevant leagues from the V17 list
  const v17Leagues = ['荷甲','意甲','俄超','比甲','挪超','苏超','瑞典超','奥甲冠','奥甲',
    '德甲','西甲','巴西甲','美职业'];
  
  console.log('=== MATCHES FROM RELEVANT LEAGUES ===');
  lines.forEach(l => {
    for (const league of v17Leagues) {
      if (l.includes(league) && l.includes('完')) {
        console.log(l.replace(/\t/g, ' | '));
        break;
      }
    }
  });
  
  console.log('\n=== DATES ON PAGE ===');
  lines.filter(l => l.includes('2026-')).forEach(l => console.log(l));
  
  // Try using f=ft0 to see if there's a further back option
  const allFtLinks = await page.evaluate(() => {
    return Array.from(document.querySelectorAll('a[href*="f=ft"]')).map(a => ({
      text: a.textContent.trim(),
      href: a.getAttribute('href')
    }));
  });
  console.log('\n=== ft links found ===');
  console.log(JSON.stringify(allFtLinks, null, 2));
  
  await browser.close();
}

main().catch(e => { console.error(e); process.exit(1); });
