const { chromium } = require('playwright');

async function main() {
  const browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] });
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  
  // Try navigating to past finished matches. 
  // The date links show: 4/25→?f=ft1, 4/24→?f=ft2, etc.
  // So each click goes back one day. The current page shows today.
  // Let me try to figure out the exact URL for April 26
  // From the earlier output, April 26 matches appeared in lines 240-500 but mixed with other dates
  
  // First, load the default page
  await page.goto('https://live.nowscore.com/schedule.aspx?f=ft1', { waitUntil: 'networkidle', timeout: 60000 });
  await page.waitForTimeout(8000);
  
  const text1 = await page.evaluate(() => document.body.innerText);
  const lines1 = text1.split('\n').filter(l => l.trim());
  
  // Look for dates in the text
  const dateLines = lines1.filter(l => l.includes('2026-'));
  console.log('=== DATES FOUND ON PAGE ===');
  dateLines.forEach(l => console.log(l));
  
  // Check what date range matches are displayed
  console.log('\n=== FIRST 20 MATCH LINES ===');
  lines1.filter(l => l.includes('完') || l.includes('-')).slice(0, 20).forEach(l => console.log(l));
  
  // Find the "2026-04-26" link and click it
  const clicked = await page.evaluate(() => {
    const links = Array.from(document.querySelectorAll('a'));
    const target = links.find(l => l.textContent.trim() === '2026-04-26 (星期天)');
    if (target) { target.click(); return 'Y'; }
    return 'N';
  });
  console.log('\nClicked April 26:', clicked);
  await page.waitForTimeout(5000);
  
  const text2 = await page.evaluate(() => document.body.innerText);
  const lines2 = text2.split('\n').filter(l => l.trim());
  console.log('\n=== FIRST 20 LINES AFTER CLICK ===');
  lines2.slice(0, 20).forEach(l => console.log(l));
  
  // Check for key matches
  console.log('\n=== SEARCH KEY MATCHES ===');
  const keywords = ['SBV精英','佛罗伦萨','下诺夫哥罗德','根特','莫尔德','流浪者','莫斯科迪纳摩',
    '克拉斯诺达尔','布洛马波卡纳','格拉茨风暴','汉坎','KFUM奥斯陆','多特蒙德',
    '利勒斯特罗姆','比利亚雷亚尔','巴拉纳竞技','布拉干蒂诺','洛杉矶银河'];
  for (const kw of keywords) {
    const found = lines2.filter(l => l.includes(kw));
    if (found.length > 0) {
      console.log(kw + ' => ' + found[0]);
    } else {
      console.log(kw + ' => NOT FOUND');
    }
  }
  
  // Since the default page might be showing April 27 and we need April 26
  // Let me check if the date links exist on the page
  console.log('\n=== ALL DATE LINKS ===');
  const dtLinks = await page.evaluate(() => {
    return Array.from(document.querySelectorAll('a'))
      .filter(l => l.textContent.trim().match(/2026-\d{2}-\d{2}/))
      .map(l => ({ text: l.textContent.trim(), href: l.getAttribute('href') }));
  });
  dtLinks.forEach(l => console.log(JSON.stringify(l)));
  
  await browser.close();
}

main().catch(e => { console.error(e); process.exit(1); });
