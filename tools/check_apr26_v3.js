const { chromium } = require('playwright');

async function main() {
  const browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] });
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  
  // The match data shows April 26 & 27 are confusable.
  // Let me directly go to the "近日赛程" (schedule) page for April 26  
  // The dates in nav have: Apr 27 → sc1, Apr 28 → sc2, etc. (future schedule)
  // Past: Apr 25 → ft1, Apr 24 → ft2, etc.
  // Apr 26 is not listed! This is strange.
  
  // Let me try sc1 to see if Apr 26 is accessible that way, or try to deduce
  // Maybe the URL format is just date-based
  
  // Try navigating with a date parameter
  await page.goto('https://live.nowscore.com/schedule.aspx?date=2026-04-26', { waitUntil: 'networkidle', timeout: 60000 });
  await page.waitForTimeout(8000);
  
  const text = await page.evaluate(() => document.body.innerText);
  const lines = text.split('\n').filter(l => l.trim());
  
  // Check dates
  console.log('=== DATES ON PAGE ===');
  lines.filter(l => l.includes('2026-')).forEach(l => console.log(l));
  
  // Also try the 2in1.aspx which has live + future matches
  // and check if we can navigate from there
  
  console.log('\n=== TRYING ANOTHER APPROACH ===');
  
  // Or maybe we need to look up each match individually from its analysis page
  // The V17 scraper works by clicking each team name to open analysis
  // Let me check analysis pages for key matches
  
  // For example: SBV精英 vs 乌德勒支
  // The analysis URL format is like: https://live.nowscore.com/analysis/2790974cn.html
  // We know the match ID from the earlier search
  
  await browser.close();
}

main().catch(e => { console.error(e); process.exit(1); });
