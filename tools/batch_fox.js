const { chromium } = require('playwright');

async function main() {
  const browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] });
  const ctx = await browser.newContext({
    userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
  });
  
  const matches = [
    { name: '格拉斯哥流浪者 vs 马瑟韦尔', url: 'https://www.foxsports.com/soccer/scottish-premier-rangers-vs-motherwell-apr-26-2026-game-boxscore-776852' },
    { name: '莫尔德 vs 瓦勒伦加', url: 'https://www.foxsports.com/soccer/norway-eliteserien-molde-vs-valerenga-apr-26-2026-game-boxscore-628250' },
    { name: '根特 vs 布鲁日', url: 'https://www.foxsports.com/soccer/belgian-pro-league-kaa-gent-vs-club-brugge-apr-26-2026-game-boxscore-625926' },
    { name: 'SBV精英 vs 乌德勒支', url: 'https://www.foxsports.com/soccer/eredivisie-excelsior-vs-fc-utrecht-apr-26-2026-game-boxscore-627530' },
    { name: '下诺夫哥罗德 vs 莫斯科斯巴达', url: 'https://www.foxsports.com/soccer/russian-premier-league-fk-nizhny-novgorod-vs-spartak-moscow-apr-26-2026-game-boxscore-628551' },
    { name: '佛罗伦萨 vs 萨索洛', url: 'https://www.foxsports.com/soccer/serie-a-fiorentina-vs-sassuolo-apr-26-2026-game-boxscore-625531' }
  ];
  
  for (const m of matches) {
    console.log(`\n=== ${m.name} ===`);
    try {
      const page = await ctx.newPage();
      await page.goto(m.url, { waitUntil: 'networkidle', timeout: 30000 });
      await page.waitForTimeout(3000);
      
      const text = await page.evaluate(() => document.body.innerText);
      
      // Look for the box score pattern: 1 2 T with team codes
      const headerMatch = text.match(/(\d+)\n+\d+\n+\d+|(\w+)\s*(\d+)\s*(\d+)/);
      const scores = text.match(/(EXL|UTR|RAN|MOT|GNT|BRU|NNO|SM|MOL|VAL|FIO|SAS)\s*\n?(\d+)\s*\n?(\d+)\s*\n?(\d*)/g);
      
      // Simpler approach: find the box score table
      const lines = text.split('\n').filter(l => l.trim());
      
      // Check for halftime score in the page
      const htPattern = text.match(/halftime[^]*?(\d)-(\d)|HT[^]*?(\d)[^]*?(\d)/i);
      
      // Look for the "1 2 T" pattern and team scores
      let foundH1 = false, foundA1 = false, foundH2 = false, foundA2 = false;
      
      for (let i = 0; i < lines.length; i++) {
        if (lines[i].includes('1') && lines[i+1] && lines[i+1].trim() === '2' && lines[i+2] && lines[i+2].trim() === 'T') {
          // This is the header "1    2    T"
          const teamCode = lines[i-1]?.trim();
          const homeScore1 = lines[i+3]?.trim();
          const homeScore2 = lines[i+4]?.trim();
          const homeScoreT = lines[i+5]?.trim();
          const awayCode = lines[i+6]?.trim();
          const awayScore1 = lines[i+7]?.trim();
          const awayScore2 = lines[i+8]?.trim();
          const awayScoreT = lines[i+9]?.trim();
          
          console.log(`  FT: ${homeScoreT}-${awayScoreT}, HT: ${homeScore1}-${awayScore1}`);
          foundH1 = true;
          break;
        }
      }
      
      if (!foundH1) {
        // Alternative: search for score patterns directly
        const scoreMatch = text.match(/(\d)\n(\d)\n\d+\n\d+\n(\w+)\n(\d)/);
        console.log(`  Trying alternative parse...`);
        
        // Just output what we find around "1 2 T"
        const idx = text.indexOf('1\n2\nT');
        if (idx >= 0) {
          const fragment = text.substring(Math.max(0, idx-50), idx+100);
          console.log(`  Fragment: ...${fragment.replace(/\n/g, ' ')}...`);
        } else {
          // Search for any score pattern
          const scoreLines = lines.filter(l => l.match(/^\d+$/) && parseInt(l) <= 10);
          console.log(`  Score numbers: ${scoreLines.join(', ')}`);
          console.log(`  Full lines around T: ${lines.filter(l => l === 'T' || l === '0' || l === '1' || l === '2' || l.match(/^[A-Z]{3}$/)).slice(0, 20).join(', ')}`);
        }
      }
      
      await page.close();
    } catch (e) {
      console.log(`  Error: ${e.message.substring(0, 100)}`);
    }
  }
  
  await browser.close();
}

main().catch(e => { console.error(e); process.exit(1); });
