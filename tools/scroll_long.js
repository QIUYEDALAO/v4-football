const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] });
  const ctx = await browser.newContext({
    userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
  });
  const page = await ctx.newPage();
  await page.goto('https://live.nowscore.com/2in1.aspx', { 
    waitUntil: 'networkidle', timeout: 60000 
  });
  await page.waitForTimeout(3000);

  // Scroll to bottom gradually to load all data
  for (let i = 0; i < 5; i++) {
    await page.evaluate(() => {
      window.scrollTo(0, document.body.scrollHeight * (i+1) / 5);
    });
    await page.waitForTimeout(1000);
  }

  const fullText = await page.evaluate(() => document.body.innerText);
  
  // Search for the missing matches
  const searches = [
    '布洛马波卡纳', '瓦斯特拉斯', 
    '利勒斯特罗姆', '博德闪耀',
    '巴拉纳竞技'
  ];
  
  for (const s of searches) {
    const idx = fullText.indexOf(s);
    if (idx >= 0) {
      const context = fullText.substring(Math.max(0, idx-80), idx+300);
      console.log(`=== ${s} ===`);
      console.log(context.replace(/\n/g, ' | '));
      console.log('');
    } else {
      console.log(`${s}: NOT FOUND`);
    }
  }

  await browser.close();
})().catch(e => { console.error(e); process.exit(1); });
