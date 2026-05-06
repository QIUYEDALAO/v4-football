const { chromium } = require('playwright');

async function main() {
  const browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] });
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  
  await page.goto('https://live.nowscore.com/schedule.aspx?f=ft1', { waitUntil: 'networkidle', timeout: 60000 });
  await page.waitForTimeout(10000);
  
  // Look for date navigation elements
  const html = await page.content();
  
  // Find all date-related elements
  const dates = await page.evaluate(() => {
    const result = [];
    // Find date navigation - usually in a calendar picker or tabs
    const all = document.querySelectorAll('*');
    for (const el of all) {
      const text = el.textContent?.trim() || '';
      if (text.match(/2026-04-2[0-9]/)) {
        result.push({
          tag: el.tagName,
          text: text.substring(0, 50),
          id: el.id,
          className: el.className
        });
      }
    }
    return result.slice(0, 20);
  });
  console.log('Date elements found:', JSON.stringify(dates, null, 2));
  
  // Try clicking the calendar/date picker button
  // Look for calendar icon or date display
  const calLinks = await page.evaluate(() => {
    return Array.from(document.querySelectorAll('*')).filter(el => {
      const t = el.textContent?.trim() || '';
      return t.includes('星期') || t.includes('历') || t.includes('日期') || t === '2026-04-27';
    }).slice(0, 30).map(el => ({
      tag: el.tagName,
      text: el.textContent?.trim().substring(0, 50),
      id: el.id,
      className: el.className
    }));
  });
  console.log('\nCalendar/date links:', JSON.stringify(calLinks, null, 2));
  
  // Find where the date shows "2026-04-27"  
  const dateText = await page.evaluate(() => {
    // Look for element containing current date
    const body = document.body;
    const walker = document.createTreeWalker(body, NodeFilter.SHOW_TEXT);
    let node;
    while (node = walker.nextNode()) {
      if (node.textContent.includes('2026-04-27')) {
        return {
          text: node.textContent.trim().substring(0, 50),
          parent: node.parentElement?.tagName,
          parentId: node.parentElement?.id,
          parentClass: node.parentElement?.className
        };
      }
    }
    return null;
  });
  console.log('\nDate text location:', JSON.stringify(dateText, null, 2));
  
  // Try to click date button
  // Check if there's a "今天" button or a calendar icon
  const navButtons = await page.evaluate(() => {
    return Array.from(document.querySelectorAll('a, input, img, span')).filter(el => {
      const t = el.textContent?.trim() || '';
      const alt = el.getAttribute('alt') || '';
      const src = el.getAttribute('src') || '';
      return t.includes('日') || t.includes('期') || t === '今天' || 
             t === '昨' || t.includes('昨天') || 
             src.includes('calendar') || src.includes('cal') ||
             t.match(/^\d{4}[-\/]/) || t.includes('2026-04');
    }).slice(0, 20).map(el => ({
      tag: el.tagName,
      text: el.textContent?.trim().substring(0, 40),
      src: el.getAttribute('src'),
      id: el.id,
      className: el.className,
      href: el.getAttribute('href'),
      onclick: el.getAttribute('onclick')?.substring(0, 100)
    }));
  });
  console.log('\nDate nav buttons:', JSON.stringify(navButtons, null, 2));
  
  // Try to find the schedule navigation area
  const scheduleNav = await page.evaluate(() => {
    // Find elements containing "近日赛程" (recent schedule)
    const links = Array.from(document.querySelectorAll('a'));
    const scheduleLinks = links.filter(l => l.textContent.trim() === '近日赛程');
    return scheduleLinks.map(l => ({
      text: l.textContent.trim(),
      href: l.getAttribute('href'),
      id: l.id,
      onclick: l.getAttribute('onclick'),
      className: l.className
    }));
  });
  console.log('\nSchedule nav:', JSON.stringify(scheduleNav, null, 2));
  
  await browser.close();
}

main().catch(e => { console.error(e); process.exit(1); });
