// Try the main 2in1 page of nowscore
const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] });
  const ctx = await browser.newContext({
    userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
  });
  
  const page = await ctx.newPage();
  
  // Intercept the data file loading
  const loadedScripts = [];
  page.on('response', async response => {
    const url = response.url();
    if (url.includes('ft') && url.includes('.js')) {
      console.log('Data loaded:', url);
      loadedScripts.push(url);
    }
  });
  
  await page.goto('https://live.nowscore.com/2in1.aspx', { 
    waitUntil: 'networkidle', 
    timeout: 30000 
  });
  await page.waitForTimeout(3000);
  
  console.log('\nLoaded JS data files:');
  loadedScripts.forEach(s => console.log(' -', s));
  
  // Take a screenshot
  await page.screenshot({ path: '/tmp/jiebao_page.png', fullPage: false });
  console.log('\nScreenshot saved to /tmp/jiebao_page.png');
  
  // Dump the text content
  const text = await page.evaluate(() => document.body.innerText);
  console.log('\n=== PAGE TEXT (first 2000 chars) ===');
  console.log(text.substring(0, 2000));
  
  // Check if there are date navigation links
  const links = await page.evaluate(() => {
    const anchors = Array.from(document.querySelectorAll('a'));
    return anchors.map(a => ({ text: a.innerText.trim(), href: a.href })).filter(a => a.text);
  });
  console.log('\n=== ALL LINKS ===');
  links.forEach(l => console.log(`  "${l.text}" -> ${l.href}`));
  
  await browser.close();
})();
