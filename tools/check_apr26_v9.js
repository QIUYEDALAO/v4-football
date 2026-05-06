const { chromium } = require('playwright');

async function main() {
  const browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] });
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  
  // Directly navigate to different ft pages to understand the mapping
  // ft1=Apr25 based on the label
  for (let i = 0; i <= 3; i++) {
    const url = `https://live.nowscore.com/schedule.aspx?f=ft${i}`;
    await page.goto(url, { waitUntil: 'networkidle', timeout: 60000 });
    await page.waitForTimeout(5000);
    
    const text = await page.evaluate(() => document.body.innerText);
    const lines = text.split('\n').filter(l => l.trim());
    const matchCount = lines.filter(l => l.match(/\d{2}:\d{2}/)).length;
    const dates = lines.filter(l => l.includes('2026-'));
    
    console.log(`f=ft${i}: ${matchCount} matches, dates: ${dates.join(', ')}`);
    
    // Show first and last match times to see the range
    const times = lines.filter(l => l.match(/\d{2}:\d{2}/)).map(l => {
      const match = l.match(/(\d{2}:\d{2})/);
      return match ? match[1] : '';
    }).filter(Boolean);
    
    if (times.length > 0) {
      console.log(`  Times: ${times[0]} ... ${times[times.length-1]}`);
    }
  }
  
  // Also try sc0
  for (let i = 0; i <= 2; i++) {
    const url = `https://live.nowscore.com/schedule.aspx?f=sc${i}`;
    await page.goto(url, { waitUntil: 'networkidle', timeout: 60000 });
    await page.waitForTimeout(5000);
    
    const text = await page.evaluate(() => document.body.innerText);
    const lines = text.split('\n').filter(l => l.trim());
    const matchCount = lines.filter(l => l.match(/\d{2}:\d{2}/)).length;
    const dates = lines.filter(l => l.includes('2026-'));
    
    console.log(`f=sc${i}: ${matchCount} matches, dates: ${dates.join(', ')}`);
    const times = lines.filter(l => l.match(/\d{2}:\d{2}/)).map(l => {
      const match = l.match(/(\d{2}:\d{2})/);
      return match ? match[1] : '';
    }).filter(Boolean);
    if (times.length > 0) {
      console.log(`  Times: ${times[0]} ... ${times[times.length-1]}`);
    }
  }
  
  await browser.close();
}

main().catch(e => { console.error(e); process.exit(1); });
