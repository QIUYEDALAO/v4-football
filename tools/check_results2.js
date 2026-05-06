const { chromium } = require('playwright');

async function main() {
  const browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] });
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  
  await page.goto('https://live.nowscore.com/schedule.aspx?f=ft1', { waitUntil: 'networkidle', timeout: 60000 });
  await page.waitForTimeout(10000);
  
  // First, try to find dates in the page HTML
  const html = await page.content();
  const dateLinks = html.match(/<a[^>]*>[\s]*2026-04-26[^<]*<\/a>/gi);
  console.log('Date links found:', dateLinks ? dateLinks.length : 0);
  if (dateLinks) dateLinks.forEach(d => console.log('  Date:', d.substring(0, 200)));
  
  // Find all <a> elements and their positions
  const allLinks = await page.evaluate(() => {
    return Array.from(document.querySelectorAll('a')).map((a, i) => ({
      idx: i, 
      text: a.textContent.trim().substring(0, 50),
      onclick: a.getAttribute('onclick')?.toString().substring(0, 100) || '',
      id: a.id,
      className: a.className
    })).filter(a => a.text.length > 0);
  });
  
  console.log('\n=== FIRST 50 LINKS ===');
  allLinks.slice(0, 50).forEach(l => console.log(l.idx+':', JSON.stringify(l)));
  
  console.log('\n=== Looking for recent dates within 70-140 ===');
  allLinks.slice(70, 140).forEach(l => console.log(l.idx+':', JSON.stringify(l)));
  
  // Get all text
  const text = await page.evaluate(() => document.body.innerText);
  const lines = text.split('\n').filter(l => l.trim());
  console.log('\n=== LINE COUNT ===', lines.length);
  console.log('=== FIRST 30 LINES ===');
  lines.slice(0, 30).forEach((l, i) => console.log(i+':', l));
  
  // Lines 400-500 (where we might see more)
  console.log('\n=== LINES 400-500 ===');
  lines.slice(400, 500).forEach((l, i) => console.log((i+400)+':', l));
  
  await browser.close();
}

main().catch(e => { console.error(e); process.exit(1); });
