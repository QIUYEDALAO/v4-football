const { chromium } = require('playwright');

async function main() {
  const browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] });
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  
  // Try ft3.js
  for (let i = 0; i <= 5; i++) {
    const url = `https://live.nowscore.com/data/ft${i}.js?1777255917000`;
    await page.goto(url, { waitUntil: 'networkidle', timeout: 30000 });
    const text = await page.evaluate(() => document.body.innerText);
    
    // Extract first few matches to see which date data this is
    const matchInfo = text.substring(0, 200);
    const dateMatch = matchInfo.match(/'(\d{2}:\d{2})','(\d{2}-\d{2})'/);
    
    console.log(`ft${i}.js: ${matchInfo.substring(0, 80)}`);
    if (dateMatch) {
      console.log(`  First match: ${dateMatch[1]} on ${dateMatch[2]}`);
    }
    
    // Count total matches
    const matchCount = (text.match(/A\[\d+\]=/g) || []).length;
    console.log(`  Total matches: ${matchCount}`);
    
    // Check if the content looks right
    const hasVarA = text.startsWith('var A=Array');
    console.log(`  Valid data: ${hasVarA}`);
  }
  
  await browser.close();
}

main().catch(e => { console.error(e); process.exit(1); });
