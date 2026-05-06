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
  
  // The page might only show part of the data at the top.
  // Scroll down to load more
  await page.evaluate(() => {
    window.scrollTo(0, document.body.scrollHeight);
  });
  await page.waitForTimeout(3000);
  
  // Now try to get ALL match data from the full page
  const allData = await page.evaluate(() => {
    const text = document.body.innerText;
    const lines = text.split('\n');
    
    // Also try to extract Match schedule data from the page script context
    // The page loads ft1.js which contains A array
    // Let me check if ft1 data is available in global scope
    const ftData = typeof A !== 'undefined' ? A : null;
    
    return {
      totalLines: lines.length,
      textSample: lines.slice(0, 500).join('\n').substring(0, 10000),
      hasGlobalA: ftData !== null
    };
  });
  
  console.log('Total lines in page:', allData.totalLines);
  console.log('Has global A data:', allData.hasGlobalA);
  
  // If A is available, try to get it
  if (allData.hasGlobalA) {
    const aData = await page.evaluate(() => {
      const data = [];
      // A is the ft1.js array loaded by the page
      // Let's try window.A or just A
      const arr = typeof A !== 'undefined' ? A : null;
      if (arr && arr.length) {
        for (let i = 0; i < Math.min(arr.length, 5000); i++) {
          const item = arr[i];
          if (item && item.length >= 17) {
            const homeCN = item[4];
            const awayCN = item[7];
            const time = item[10];
            const date = item[11];
            const status = item[12];
            const homeTotal = item[13];
            const awayTotal = item[14];
            const halfHome = item[15];
            const halfAway = item[16];
            
            if (date === '04-26' && status === -1) {
              data.push({
                homeCN, awayCN, time, date,
                homeTotal, awayTotal, halfHome, halfAway
              });
            }
          }
        }
      }
      return data;
    });
    
    console.log(`\nFound ${aData.length} Apr 26 completed matches from A array`);
    aData.forEach(m => {
      const hasHTGoal = m.halfHome + m.halfAway > 0;
      console.log(`${m.time} ${m.homeCN} vs ${m.awayCN} FT ${m.homeTotal}-${m.awayTotal} HT ${m.halfHome}-${m.halfAway} ${hasHTGoal ? '✅' : '❌'}`);
    });
  }
  
  // Search the page text for remaining missing teams
  const searchMore = await page.evaluate(() => {
    const text = document.body.innerText;
    const lines = text.split('\n');
    const found = {};
    
    ['阿尔克马尔', '博洛尼亚', '赫根', '帕纳辛', '罗马', 'Roma', 'AZ'].forEach(team => {
      for (let i = 0; i < lines.length; i++) {
        if (lines[i].includes(team)) {
          const ctx = lines.slice(Math.max(0, i-2), i+5).join(' | ');
          found[team] = ctx.substring(0, 200);
          break;
        }
      }
    });
    
    return found;
  });
  
  console.log('\n=== REMAINING TEAMS SEARCH ===');
  for (const [team, ctx] of Object.entries(searchMore)) {
    console.log(`${team}: ${ctx}`);
  }
  
  await browser.close();
})();
