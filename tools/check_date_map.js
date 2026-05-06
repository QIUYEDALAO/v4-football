const { chromium } = require('playwright');

async function main() {
  const browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] });
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  
  for (let i = 1; i <= 7; i++) {
    const url = `https://live.nowscore.com/data/ft${i}.js?1777255917000`;
    await page.goto(url, { waitUntil: 'networkidle', timeout: 30000 });
    const text = await page.evaluate(() => document.body.innerText);
    
    // Find the first and last date in the data
    const dates = [...text.matchAll(/'(\d{2}:\d{2})','(\d{2}-\d{2})'/g)].slice(0, 1);
    // Also look for format: time, '', date (some use different format)
    const dates2 = [...text.matchAll(/'\d{2}:\d{2}'.*?'(\d{2}-\d{2})'/g)].slice(0, 1);
    
    const matches = text.match(/'(\d{2}:\d{2})','(\d{2}-\d{2})'/);
    const dateInfo = matches ? matches[2] : 'N/A';
    const timeInfo = matches ? matches[1] : 'N/A';
    
    // Check for the pattern: season, group, league info to know the date
    console.log(`ft${i}.js: First match time=${timeInfo}, date=${dateInfo}, total=${(text.match(/A\[\d+\]=/g) || []).length}`);
  }
  
  // Also check the schedule pages
  for (let i = 1; i <= 7; i++) {
    await page.goto(`https://live.nowscore.com/schedule.aspx?f=ft${i}`, { waitUntil: 'networkidle', timeout: 60000 });
    await page.waitForTimeout(3000);
    const text = await page.evaluate(() => document.body.innerText);
    const lines = text.split('\n').filter(l => l.trim());
    
    const dates = lines.filter(l => l.match(/2026-\d{2}-\d{2}/));
    const matchTimes = lines.filter(l => l.match(/\d{2}:\d{2}/));
    
    console.log(`\nschedule.aspx?f=ft${i}: ${matchTimes.length} matches, dates: ${dates.slice(0,4).join(', ')}`);
  }
  
  await browser.close();
}

main().catch(e => { console.error(e); process.exit(1); });
