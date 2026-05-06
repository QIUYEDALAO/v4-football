const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] });
  const ctx = await browser.newContext({
    userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
  });
  
  const page = await ctx.newPage();
  
  await page.goto('https://live.nowscore.com/2in1.aspx', { 
    waitUntil: 'networkidle', 
    timeout: 30000 
  });
  await page.waitForTimeout(3000);
  
  // Search for the remaining teams on the page
  const searchFor = ['阿尔克马尔', 'AZ', '博洛尼亚', '赫根', 'Hacken', '帕纳辛', 'Panathinaikos', 'AEK'];
  
  const results = await page.evaluate((teams) => {
    const allText = document.body.innerText;
    const lines = allText.split('\n');
    
    return teams.map(team => {
      const matches = lines.filter(l => l.includes(team));
      return { team, matches: matches.slice(0, 10) };
    });
  }, searchFor);
  
  for (const r of results) {
    console.log(`\n=== ${r.team} ===`);
    r.matches.forEach(m => console.log(m.substring(0, 300)));
  }
  
  // Also get all Eredivisie and Swedish matches that might have AZ/Hacken
  const leagueSections = await page.evaluate(() => {
    const text = document.body.innerText;
    const lines = text.split('\n');
    const results = [];
    
    // Find lines containing these leagues and extract surrounding context
    const leagues = ['荷甲', '瑞典超', '瑞典甲', '瑞超', '希腊超', '希超', '意甲'];
    
    leagues.forEach(league => {
      for (let i = 0; i < lines.length; i++) {
        if (lines[i].includes(league)) {
          // Show this line and the next few lines
          const section = lines.slice(Math.max(0, i-1), i+10).filter(l => l.trim());
          if (section.length > 0) {
            results.push({ league, content: section.join(' | ').substring(0, 300) });
          }
          break;
        }
      }
    });
    
    return results;
  });
  
  console.log('\n\n=== LEAGUE MATCHES ===');
  leagueSections.forEach(l => console.log(`${l.league}: ${l.content}`));
  
  await browser.close();
})();
