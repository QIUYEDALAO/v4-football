const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: false });
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  await page.goto('https://live.nowscore.com/', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(5000);

  // Try the 2in1 page (today's matches)
  await page.goto('https://live.nowscore.com/2in1.aspx', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(5000);
  
  const text = await page.evaluate(() => document.body.innerText);
  
  // Look for our matches in text
  const allTargets = [
    { home: '阿拉尼亚', away: '萨姆松' },
    { home: '巴蒂卡', away: '阿克伦' },
    { home: '卡尔马', away: '埃尔夫' },
    { home: '赫根', away: '天狼星' },
    { home: '曼彻斯特联', away: '布伦特' },
    { home: '奥尔格里特', away: '代格福' },
    { home: '贝西克塔斯', away: '卡拉古' },
    { home: '科尼亚', away: '特拉布' },
  ];
  
  console.log('=== 搜索完整赛果 ===\n');
  
  const lines = text.split('\n');
  for (const t of allTargets) {
    let found = false;
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      if (line.includes(t.home) && line.includes(t.away)) {
        // Found the match line - get context (next few lines for score)
        const context = lines.slice(Math.max(0,i-1), Math.min(lines.length, i+4)).join(' | ');
        console.log(`${t.home} vs ${t.away}:`);
        console.log(`  ${context.substring(0, 200)}`);
        found = true;
        break;
      }
    }
    if (!found) console.log(`${t.home} vs ${t.away}: 未找到`);
    console.log();
  }
  
  await browser.close();
})();
