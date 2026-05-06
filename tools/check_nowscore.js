const { chromium } = require('playwright');

async function main() {
  const browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] });
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  
  // Navigate to schedule.aspx default page
  await page.goto('https://live.nowscore.com/schedule.aspx', { waitUntil: 'networkidle', timeout: 60000 });
  await page.waitForTimeout(8000);
  
  // Get the current URL
  console.log('Current URL:', page.url());
  
  // Check for any date-related elements or JS variables
  const dateInfo = await page.evaluate(() => {
    const scripts = Array.from(document.querySelectorAll('script'));
    let match;
    for (const s of scripts) {
      if (s.textContent && s.textContent.includes('2026')) {
        match = s.textContent.substring(0, 2000);
        break;
      }
    }
    return match || 'No script with 2026 found';
  });
  console.log('\n=== FIRST SCRIPT WITH 2026 ===');
  console.log(dateInfo);
  
  // Look at all script sources to find date handling
  const allScripts = await page.evaluate(() => {
    return Array.from(document.querySelectorAll('script[src]'))
      .filter(s => s.src.includes('.js'))
      .map(s => s.src);
  });
  console.log('\n=== JS FILES ===');
  allScripts.slice(0, 20).forEach(s => console.log(s));
  
  await browser.close();
}

main().catch(e => { console.error(e); process.exit(1); });
