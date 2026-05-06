const { chromium } = require('playwright');

async function main() {
  const browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] });
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  
  // Go to the 完场比分 page  
  await page.goto('https://live.nowscore.com/schedule.aspx?f=ft1', { waitUntil: 'networkidle', timeout: 60000 });
  await page.waitForTimeout(10000);
  
  // First page always shows today. Let me see the HTML structure better
  const text = await page.evaluate(() => document.body.innerText);
  const lines = text.split('\n').filter(l => l.trim());
  
  console.log('=== FIRST 50 LINES ===');
  lines.slice(0, 50).forEach((l, i) => {
    console.log(i+':', l.substring(0, 120));
  });
  
  console.log('\n=== LINES WITH "2026-" ===');
  lines.filter(l => l.includes('2026-')).forEach((l, i) => {
    console.log(l.substring(0, 120));
  });
  
  // Now try clicking "2026-04-25 (星期六)" - it has href="?f=ft1"
  // which would show April 25 data
  // Since April 26 just finished yesterday, maybe we need to navigate to a specific page
  
  // Let's look at the HTML to understand date picker structure
  const htmlSnippet = await page.evaluate(() => {
    const links = Array.from(document.querySelectorAll('a'));
    const dateLinks = links.filter(l => l.textContent.trim().match(/2026-\d{2}-\d{2}/));
    return dateLinks.map(l => ({
      text: l.textContent.trim(),
      href: l.getAttribute('href'),
      position: {
        x: l.getBoundingClientRect().x,
        y: l.getBoundingClientRect().y,
        visible: l.getBoundingClientRect().width > 0 && l.getBoundingClientRect().height > 0
      }
    }));
  });
  console.log('\n=== DATE LINKS ===');
  console.log(JSON.stringify(dateLinks, null, 2));
  
  await browser.close();
}

main().catch(e => { console.error(e); process.exit(1); });
