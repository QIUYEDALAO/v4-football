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
  
  const remaining = await page.evaluate(() => {
    const text = document.body.innerText;
    const results = {};
    
    // Search for remaining teams
    const queries = ['阿尔克马尔', '博洛尼亚', '赫根', '帕纳辛', 'AZ Alkmaar', 'Bologna', 'Roma', 'AEK'];
    
    lines = text.split('\n');
    
    for (const q of queries) {
      const matches = lines.filter(l => l.includes(q));
      if (matches.length > 0) {
        results[q] = matches.slice(0, 5);
      }
    }
    
    // Also search for the league entries
    const leagues = ['荷甲', '意甲', '瑞超'];
    for (const league of leagues) {
      const idx = lines.findIndex(l => l.includes(league));
      if (idx >= 0) {
        const context = lines.slice(Math.max(0, idx-2), idx+10);
        results['league_' + league] = context;
      }
    }
    
    return results;
  });
  
  for (const [key, val] of Object.entries(remaining)) {
    console.log(`\n=== ${key} ===`);
    if (Array.isArray(val)) {
      val.forEach(v => console.log(v));
    } else {
      val.forEach(v => console.log(v));
    }
  }
  
  await browser.close();
})();
