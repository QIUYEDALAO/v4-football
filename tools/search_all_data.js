const { chromium } = require('playwright');

async function main() {
  const browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] });
  const ctx = await browser.newContext();
  
  // ft1.js has 04-25 and 04-26 matches
  // ft2.js has 04-24 matches
  // But for the V17 Apr 26 matches, they might be in:
  // - ft1.js with date 04-26 (late Apr 26 matches that just finished)
  // - Or the default page loads ft1.js but the match is dated 04-26
  // - Let's search across ALL ft files
  
  const allFiles = [];
  for (let i = 1; i <= 7; i++) {
    allFiles.push(`ft${i}`);
  }
  // Also check sc1 (today's future matches)
  allFiles.push('sc1');
  
  for (const file of allFiles) {
    const page = await ctx.newPage();
    const url = `https://live.nowscore.com/data/${file}.js?1777255917000`;
    await page.goto(url, { waitUntil: 'networkidle', timeout: 30000 });
    const text = await page.evaluate(() => document.body.innerText);
    await page.close();
    
    // Check for V17 team names
    const teams = ['根特','Gent','莫尔德','Molde','Excelsior','SBV精英','乌德勒支','Utrecht',
      '诺夫哥罗德','Nizhny','佛罗伦萨','Fiorentina','萨索洛','流浪者','Rangers',
      '马瑟韦尔','Motherwell','莫斯科迪纳摩','Dynamo Moscow','索契','克拉斯诺达尔','Krasnodar',
      '马哈奇卡拉','布洛马','Brommapojkarna','瓦斯特拉斯','Vasteras',
      '格拉茨','Sturm','Graz','奥地利维也纳','Austria Wien','汉坎','HamKam',
      'KFUM','萨普斯堡','Sarpsborg','多特蒙德','Dortmund','弗赖堡','Freiburg',
      '利勒斯特','Lillestrom','博德','Bodo','Glimt','比利亚雷亚尔','Villarreal',
      '塞尔塔','Celta','巴拉纳','Athletico','Paranaense','维多利亚','Vitoria',
      '布拉干蒂诺','Bragantino','帕尔梅拉斯','Palmeiras','洛杉矶','Galaxy','盐湖城','Salt Lake'];
    
    const matches = text.split('\n').filter(l => l.trim().startsWith('A['));
    const foundMatches = [];
    
    for (const line of matches) {
      const quoted = line.match(/'([^']*)'/g);
      if (!quoted) continue;
      
      const homeCN = quoted[0]?.replace(/'/g,'') || '';
      const awayCN = quoted[3]?.replace(/'/g,'') || '';
      
      // Check if this line contains any V17 teams
      for (const team of teams) {
        if ((homeCN.includes(team) || awayCN.includes(team)) && !line.includes('青年') && !line.includes('后备') && !line.includes('B队') && !line.includes('女足') && !line.includes('U2')) {
          const time = quoted[6]?.replace(/'/g,'') || '';
          const date = quoted[7]?.replace(/'/g,'') || '';
          
          // Try to get scores - these are numeric values after the 12th element
          const arrContent = line.match(/A\[\d+\]=\[([^\]]+)\]/);
          if (arrContent) {
            try {
              const arr = JSON.parse('[' + arrContent[1] + ']');
              const homeTotal = arr[13];
              const awayTotal = arr[14];
              const halfHome = arr[15];
              const halfAway = arr[16];
              
              foundMatches.push({
                file,
                line: `${homeCN} vs ${awayCN} (${time} ${date}) FT ${homeTotal}-${awayTotal} HT ${halfHome}-${halfAway}`,
                homeCN, awayCN, time, date,
                ft: `${homeTotal}-${awayTotal}`,
                ht: `${halfHome}-${halfAway}`,
                hasHT: halfHome + halfAway > 0
              });
            } catch(e) {}
          }
          break;
        }
      }
    }
    
    if (foundMatches.length > 0) {
      console.log(`\n=== ${file}.js ===`);
      for (const m of foundMatches) {
        console.log(m.line);
      }
    }
  }
  
  await browser.close();
}

main().catch(e => { console.error(e); process.exit(1); });
