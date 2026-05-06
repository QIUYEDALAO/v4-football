const { chromium } = require('playwright');

async function main() {
  const browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] });
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  
  // April 26 must be accessible. Let me check if clicking on sc pages goes backward
  // ft1=Apr25, ft2=Apr24... and sc1=Apr27, sc2=Apr28... 
  // So April 26 would be... maybe there's no direct link but we can navigate from 2in1 page
  // Or maybe the date links are different when we're on a different day
  
  // Let's try the 2in1 page (this shows live matches)
  await page.goto('https://live.nowscore.com/2in1.aspx', { waitUntil: 'networkidle', timeout: 60000 });
  await page.waitForTimeout(8000);
  
  // Look for the date in the 2in1 page - it should show today
  const text = await page.evaluate(() => document.body.innerText);
  const lines = text.split('\n').filter(l => l.trim());
  
  // Check what date is shown
  console.log('=== 2in1 DATES ===');
  lines.filter(l => l.includes('2026-') || l.includes('星期')).forEach(l => console.log(l));
  
  // Look for today's date
  console.log('\n=== TODAY INFO ===');
  const todayEl = await page.evaluate(() => {
    const all = document.querySelectorAll('*');
    for (const el of all) {
      if (el.textContent?.includes('2026-04-27') || el.textContent === '今天') {
        return {tag: el.tagName, text: el.textContent.trim().substring(0, 30), className: el.className};
      }
    }
    return null;
  });
  console.log(JSON.stringify(todayEl));
  
  // Try to find ALL the tab navigation at the top
  console.log('\n=== HEADER NAV ===');
  const headerNav = await page.evaluate(() => {
    const links = Array.from(document.querySelectorAll('a'));
    return links.filter(l => l.textContent.trim().match(/完场|近日|即时|比分/)).slice(0, 10).map(l => ({
      text: l.textContent.trim(),
      href: l.getAttribute('href'),
      className: l.className
    }));
  });
  console.log(JSON.stringify(headerNav, null, 2));
  
  // Try clicking the "完场比分" link
  console.log('\n=== TRYING 完场比分 ===');
  // On 2in1 page, the structure might be different
  // Let me check ALL links
  const allLinks = await page.evaluate(() => {
    return Array.from(document.querySelectorAll('a')).slice(100, 300)
      .filter(l => l.textContent.trim().length > 0 && l.textContent.trim().length < 30)
      .map(l => ({
        text: l.textContent.trim(),
        href: l.getAttribute('href') || '',
        id: l.id,
        className: l.className
      }));
  });
  
  // Show unique/interesting links
  const uniqueLinks = new Set();
  allLinks.forEach(l => uniqueLinks.add(l.text + ' -> ' + l.href));
  console.log([...uniqueLinks].slice(0, 30).join('\n'));
  
  await browser.close();
}

main().catch(e => { console.error(e); process.exit(1); });
