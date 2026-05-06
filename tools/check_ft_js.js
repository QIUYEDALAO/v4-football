const { chromium } = require('playwright');

async function main() {
  const browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] });
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  
  // Look at jsdate.js to understand date system
  await page.goto('https://live.nowscore.com/data/jsdate.js', { waitUntil: 'networkidle', timeout: 60000 });
  let text = await page.evaluate(() => document.body.innerText);
  console.log('=== jsdate.js ===');
  console.log(text);
  
  // Now try ft1.js (the data file for today's finished matches)
  await page.goto('https://live.nowscore.com/data/ft1.js?1777255917000', { waitUntil: 'networkidle', timeout: 30000 });
  text = await page.evaluate(() => document.body.innerText);
  console.log('\n=== ft1.js (first 3000 chars) ===');
  console.log(text.substring(0, 3000));
  
  // Try ft2.js (Apr 25)
  await page.goto('https://live.nowscore.com/data/ft2.js?1777255917000', { waitUntil: 'networkidle', timeout: 30000 });
  text = await page.evaluate(() => document.body.innerText);
  console.log('\n=== ft2.js (first 3000 chars) ===');
  console.log(text.substring(0, 3000));
  
  await browser.close();
}

main().catch(e => { console.error(e); process.exit(1); });
