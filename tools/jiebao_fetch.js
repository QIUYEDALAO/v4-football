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
  
  // Get ALL match data from the page
  const matchData = await page.evaluate(() => {
    const text = document.body.innerText;
    const lines = text.split('\n').filter(l => l.trim());
    
    // V17 teams to search for
    const v17Teams = ['根特', '莫尔德', 'SBV精英', '下诺夫哥罗德', '佛罗伦萨',
      '流浪者', '莫斯科迪纳摩', '克拉斯诺达尔', '塞维利亚', '多特蒙德',
      '阿尔克马尔', '格拉茨', '博洛尼亚', '塞尔塔', '圣吉罗斯', '特罗姆瑟',
      '赫根', '帕纳辛'];
    
    const results = {};
    
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      
      for (const team of v17Teams) {
        if (results[team]) continue; // already found
        if (line.includes(team)) {
          // Get context - show a few lines around it
          const context = [];
          for (let j = Math.max(0, i-2); j <= Math.min(lines.length-1, i+5); j++) {
            context.push(lines[j].trim());
          }
          results[team] = context.join('\n').substring(0, 500);
        }
      }
    }
    
    return results;
  });
  
  console.log('=== V17 MATCH DATA FROM JIEBAO ===\n');
  for (const [team, data] of Object.entries(matchData)) {
    console.log(`--- ${team} ---`);
    console.log(data);
    console.log('');
  }
  
  // List all matches that look like they have score data
  const allMatches = await page.evaluate(() => {
    const text = document.body.innerText;
    // Look for patterns like "主队 X-Y 客队" followed by corner data
    const lines = text.split('\n');
    console.log('Total lines:', lines.length);
    
    // Find all league-header like patterns
    const leagues = [];
    for (let i = 0; i < Math.min(lines.length, 300); i++) {
      if (lines[i].includes('完') && lines[i].match(/\d+-\d+/)) {
        const ctx = [];
        for (let j = Math.max(0, i-2); j <= Math.min(lines.length-1, i+5); j++) {
          ctx.push(lines[j]);
        }
        leagues.push(ctx.join(' | ').substring(0, 200));
      }
    }
    return leagues.slice(0, 40);
  });
  
  console.log('\n=== SAMPLE MATCHES (first 20) ===');
  allMatches.slice(0, 20).forEach(m => console.log(m));
  
  await browser.close();
})();
