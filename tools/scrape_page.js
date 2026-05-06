const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] });
  const ctx = await browser.newContext({
    userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
  });
  
  const page = await ctx.newPage();
  
  // Collect ALL loaded scripts
  const loadedJS = [];
  page.on('response', async res => {
    const url = res.url();
    if (url.includes('.js')) {
      loadedJS.push(url);
    }
    if (url.includes('.js') && !url.includes('jquery') && !url.includes('function')) {
      try {
        const body = await res.text();
        if (body.includes('A[') && body.length > 1000) {
          loadedJS.push(['MAIN_DATA', url.substring(0, 100)]);
        }
      } catch(e) {}
    }
  });
  
  await page.goto('https://live.nowscore.com/2in1.aspx', { 
    waitUntil: 'networkidle', 
    timeout: 30000 
  });
  await page.waitForTimeout(3000);
  
  // Now get all match data from the page DOM
  const matchData = await page.evaluate(() => {
    // Find all tr rows containing matches
    const rows = document.querySelectorAll('tr');
    const results = [];
    
    rows.forEach(tr => {
      // Look for rows with class or structure containing match info
      const text = tr.innerText.trim();
      if (!text) return;
      
      // Teams should have some pattern like "联赛名 主队 vs 客队 scores"
      // Look for non-numeric text followed by "vs" or direct team-score patterns
      const cells = tr.querySelectorAll('td');
      if (cells.length < 3) return;
      
      const fullText = Array.from(cells).map(c => c.innerText.trim()).join(' | ');
      
      // Find specific V17 teams
      const v17_teams = ['根特', '莫尔德', 'SBV精英', '下诺夫哥罗德', '佛罗伦萨', 
        '流浪者', '莫斯科迪纳摩', '克拉斯诺达尔', '塞维利亚', '多特', '阿尔克马尔',
        '格拉茨', '博洛尼亚', '塞尔塔', '圣吉罗斯', '特罗姆瑟', '赫根', '帕纳辛'];
      
      for (const team of v17_teams) {
        if (fullText.includes(team)) {
          results.push({ team, fullText });
          break;
        }
      }
    });
    
    return results;
  });
  
  console.log('=== V17 MATCHES FOUND ON PAGE ===');
  for (const m of matchData) {
    console.log(`${m.team}: ${m.fullText}`);
  }
  
  // Also dump all rows that look like match rows
  const allRows = await page.evaluate(() => {
    const rows = document.querySelectorAll('tr');
    const results = [];
    let count = 0;
    
    rows.forEach(tr => {
      const text = tr.innerText.trim();
      // Match row patterns: have league name, score, teams
      // Looks like: "英冠 考文垂 1-1 雷克瑟姆" with scores
      if (text.match(/[^\d]+\d+-\d+[^\d]/) && text.length < 200 && text.length > 5) {
        if (count < 3 && text.includes('英冠')) {
          results.push(text.substring(0, 200));
          count++;
        }
        if (text.includes('荷甲') || text.includes('挪超') || text.includes('意甲') || 
            text.includes('法甲') || text.includes('俄超') || text.includes('德乙') ||
            text.includes('苏超') || text.includes('英超') || text.includes('西甲') ||
            text.includes('比甲')) {
          results.push(text.substring(0, 200));
        }
      }
    });
    
    return results;
  });
  
  console.log('\n=== LEAGUE MATCH ROWS ON PAGE ===');
  allRows.forEach(r => console.log(r));
  
  // Take screenshot
  await page.screenshot({ path: '/tmp/jiebao_2in1.png', fullPage: true });
  console.log('\nScreenshot saved!');
  
  await browser.close();
})();
