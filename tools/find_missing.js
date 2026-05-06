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

  // Search the full page for these missing teams
  const fullText = await page.evaluate(() => document.body.innerText);
  
  const searches = [
    '布洛马波卡纳', 'Brommapojkarna', '瓦斯特拉斯', 'Vasteras',
    '利勒斯特罗姆', 'Lillestrom', '博德闪耀', 'Bodo',
    '巴拉纳竞技', 'Athletico Paranaense', '维多利亚', 'Vitoria'
  ];
  
  for (const s of searches) {
    const idx = fullText.indexOf(s);
    if (idx >= 0) {
      const context = fullText.substring(Math.max(0, idx-50), idx+200);
      console.log(`=== ${s} ===`);
      console.log(context.replace(/\n/g, ' | '));
      console.log('');
    } else {
      console.log(`${s}: NOT FOUND`);
    }
  }

  await browser.close();
})().catch(e => { console.error(e); process.exit(1); });
