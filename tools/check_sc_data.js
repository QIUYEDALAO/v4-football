const { chromium } = require('playwright');

async function main() {
  const browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] });
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  
  // Check sc data files - these are for future/schedule data
  for (let i = 0; i <= 3; i++) {
    const url = `https://live.nowscore.com/data/sc${i}.js?1777255917000`;
    await page.goto(url, { waitUntil: 'networkidle', timeout: 30000 });
    const text = await page.evaluate(() => document.body.innerText);
    
    const matchCount = (text.match(/A\[\d+\]=/g) || []).length;
    const dates = [...text.matchAll(/'(\d{2}:\d{2})','(\d{2}-\d{2})'/g)];
    const firstDate = dates.length > 0 ? dates[0][2] : 'N/A';
    const firstTime = dates.length > 0 ? dates[0][1] : 'N/A';
    
    console.log(`sc${i}.js: ${matchCount} matches, first: ${firstTime} on ${firstDate}`);
    
    // Show a sample of the data to understand the structure
    if (matchCount > 0) {
      const lines = text.split('\n').slice(0, 5);
      lines.forEach(l => console.log('  ' + l.substring(0, 100)));
    }
    console.log('');
  }
  
  await browser.close();
}

main().catch(e => { console.error(e); process.exit(1); });
