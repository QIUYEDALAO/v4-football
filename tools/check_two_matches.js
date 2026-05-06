const { chromium } = require('playwright');

(async () => {
  const b = await chromium.launch({ headless: true });
  const p = await b.newPage();
  
  // 意甲: 亚特兰大 vs 热那亚
  await p.goto('https://live.nowscore.com/detail/2784823.html', { waitUntil: 'domcontentloaded', timeout: 30000 });
  await p.waitForTimeout(3000);
  const text1 = await p.evaluate(() => document.body.innerText);
  console.log("=== 亚特兰大 vs 热那亚 ===");
  // Extract H2H and stats
  const lines1 = text1.split('\n').filter(l => l.includes('往绩') || l.includes('交锋') || l.includes('历史') || l.includes('H2H') || l.includes('半场'));
  console.log(lines1.slice(0,10).join('\n'));
  // Print first 2000 chars
  console.log(text1.substring(0, 2000));

  console.log("\n\n");
  
  // 法甲: 尼斯 vs 朗斯
  await p.goto('https://live.nowscore.com/detail/2800303.html', { waitUntil: 'domcontentloaded', timeout: 30000 });
  await p.waitForTimeout(3000);
  const text2 = await p.evaluate(() => document.body.innerText);
  console.log("=== 尼斯 vs 朗斯 ===");
  console.log(text2.substring(0, 2000));
  
  await b.close();
})();
