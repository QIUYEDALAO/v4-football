const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] });
  const ctx = await browser.newContext({
    userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
  });
  
  const page = await ctx.newPage();
  
  await page.goto('https://live.nowscore.com/2in1.aspx', { 
    waitUntil: 'networkidle', 
    timeout: 60000 
  });
  await page.waitForTimeout(5000);
  
  const v24Results = await page.evaluate(() => {
    const text = document.body.innerText;
    const lines = text.split('\n');
    const results = {};
    
    // V24 >=80% matches to look for
    const queries = [
      '汉坎', '斯达', 'KFUM奥斯陆', '萨普斯堡', '布拉干蒂诺', 
      '帕尔梅拉斯', '洛杉矶银河', '皇家盐湖城', '坎昆', '塔巴蒂奥',
      '比利亚雷亚尔', '塞尔塔'
    ];
    
    for (const q of queries) {
      for (let i = 0; i < lines.length; i++) {
        if (lines[i].includes(q)) {
          const ctx = [];
          for (let j = Math.max(0, i-2); j <= Math.min(lines.length-1, i+5); j++) {
            ctx.push(lines[j].trim());
          }
          results[q] = ctx.join(' | ').substring(0, 300);
          break;
        }
      }
    }
    
    return results;
  });
  
  console.log('=== V24 HIGH SCORE MATCHES FROM JIEBAO PAGE ===\n');
  for (const [team, data] of Object.entries(v24Results)) {
    if (data) {
      console.log(`--- ${team} ---`);
      console.log(data);
      console.log('');
    } else {
      console.log(`${team}: NOT FOUND ON PAGE`);
    }
  }
  
  await browser.close();
})();
