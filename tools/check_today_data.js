const { chromium } = require('playwright');

async function main() {
  const browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] });
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  
  // First, load the default page and capture all network requests
  await page.route('**/data/*.js*', (route, request) => {
    console.log('Data JS request:', request.url());
    route.continue();
  });
  
  await page.goto('https://live.nowscore.com/schedule.aspx', { waitUntil: 'networkidle', timeout: 60000 });
  await page.waitForTimeout(5000);
  
  // Check what data scripts are on the page
  const scriptSrcs = await page.evaluate(() => {
    return Array.from(document.querySelectorAll('script[src]'))
      .filter(s => s.src.includes('data/'))
      .map(s => s.src);
  });
  
  console.log('\n=== Data scripts loaded ===');
  scriptSrcs.forEach(s => console.log(s));
  
  // Also check: is today's data in a different format?
  const pageContent = await page.evaluate(() => document.body.innerText);
  const times = pageContent.match(/\d{2}:\d{2}/g) || [];
  const matchData = await page.evaluate(() => {
    // Check if there's a data array loaded
    if (typeof A !== 'undefined') {
      return `A array found with ${A.length} entries, first entry time=${A[0] ? A[0][11] : 'N/A'}`;
    }
    if (typeof matchcount !== 'undefined') {
      return `matchcount=${matchcount}`;
    }
    return 'No data arrays found';
  });
  console.log('\nMatch data:', matchData);
  
  // Try loading ft1.js directly to see today's data
  console.log('\n=== Checking current date files ===');
  
  // Today is Apr 27 - maybe the date format is different (sc = schedule?)
  // Or maybe the page uses a different mechanism for today
  
  await browser.close();
}

main().catch(e => { console.error(e); process.exit(1); });
