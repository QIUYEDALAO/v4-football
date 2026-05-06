const { chromium } = require('playwright');

async function main() {
  const browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] });
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  
  // Go to the main page
  await page.goto('https://live.nowscore.com/schedule.aspx', { waitUntil: 'networkidle', timeout: 60000 });
  await page.waitForTimeout(8000);
  
  // Check what date the page shows (look at the match times)
  let text = await page.evaluate(() => document.body.innerText);
  let lines = text.split('\n').filter(l => l.trim());
  console.log('=== DEFAULT PAGE (schedule.aspx) - FIRST MATCH WITH TIME ===');
  const matchLines = lines.filter(l => l.match(/\d{2}:\d{2}/));
  matchLines.slice(0, 5).forEach(l => console.log(l.substring(0, 150)));
  
  // Now click on April 25 link
  await page.evaluate(() => {
    const links = Array.from(document.querySelectorAll('a'));
    const target = links.find(l => l.textContent.trim() === '2026-04-25 (星期六)');
    if (target) target.click();
  });
  await page.waitForTimeout(5000);
  
  text = await page.evaluate(() => document.body.innerText);
  lines = text.split('\n').filter(l => l.trim());
  console.log('\n=== AFTER CLICKING APR 25 - FIRST MATCHES ===');
  const matchLines2 = lines.filter(l => l.match(/\d{2}:\d{2}/));
  matchLines2.slice(0, 10).forEach(l => console.log(l.substring(0, 150)));
  
  console.log('\n=== TOTAL MATCHES on Apr25 page ===', matchLines2.length);
  console.log('\n=== 2026 dates on this page ===');
  lines.filter(l => l.includes('2026-')).forEach(l => console.log(l));
  
  await browser.close();
}

main().catch(e => { console.error(e); process.exit(1); });
