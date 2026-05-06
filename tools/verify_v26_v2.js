const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: false });
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  
  // Try different page
  await page.goto('https://live.nowscore.com/schedule.aspx?f=ft1', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(5000);
  
  // The page might have pagination for different days. Look for date controls
  const bodyText = await page.evaluate(() => document.body.innerText);
  
  // Look for our target matches
  const targets = ['阿拉尼亚', '巴蒂卡', '卡尔马', '赫根', '曼联', '贝西克塔斯', '科尼亚', '奥尔格里特'];
  for (const t of targets) {
    if (bodyText.includes(t)) {
      console.log(`✅ 找到: ${t}`);
    } else {
      console.log(`❌ 未找到: ${t}`);
    }
  }
  
  console.log('\n--- 前50行 ---');
  console.log(bodyText.split('\n').slice(0, 50).join('\n'));
  
  await browser.close();
})();
