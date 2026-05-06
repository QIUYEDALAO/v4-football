const { chromium } = require('playwright');

const V17_MATCHES = [
  { n:1, time:"18:15", league:"荷甲",    home:"SBV精英",         away:"乌德勒支", short_h:"精英", short_a:"乌德勒支" },
  { n:2, time:"18:30", league:"意甲",    home:"佛罗伦萨",        away:"萨索洛", short_h:"佛罗伦萨", short_a:"萨索洛" },
  { n:3, time:"19:00", league:"俄超",    home:"下诺夫哥罗德",    away:"莫斯科斯巴达", short_h:"诺夫哥罗德", short_a:"莫斯科斯巴达" },
  { n:4, time:"19:30", league:"比甲冠",  home:"根特",            away:"布鲁日", short_h:"根特", short_a:"布鲁日" },
  { n:5, time:"20:30", league:"挪超",    home:"莫尔德",          away:"瓦勒伦加", short_h:"莫尔德", short_a:"瓦勒伦加" },
  { n:6, time:"22:00", league:"苏超冠",  home:"格拉斯哥流浪者",  away:"马瑟韦尔", short_h:"流浪者", short_a:"马瑟韦尔" },
  { n:7, time:"22:00", league:"俄超",    home:"莫斯科迪纳摩",    away:"索契", short_h:"迪纳摩", short_a:"索契" },
  { n:8, time:"22:00", league:"俄超",    home:"克拉斯诺达尔",    away:"马哈奇卡拉", short_h:"克拉斯诺达尔", short_a:"马哈奇卡拉" },
  { n:9, time:"22:30", league:"瑞典超",  home:"布洛马波卡纳",    away:"瓦斯特拉斯", short_h:"布洛马", short_a:"瓦斯特拉" },
  { n:10, time:"23:00", league:"奥甲冠", home:"格拉茨风暴",      away:"奥地利维也纳", short_h:"格拉茨", short_a:"奥地利" },
  { n:11, time:"23:00", league:"挪超",   home:"汉坎",            away:"斯达", short_h:"汉坎", short_a:"斯达" },
  { n:12, time:"23:00", league:"挪超",   home:"KFUM奥斯陆",      away:"萨普斯堡", short_h:"KFUM", short_a:"萨普斯堡" },
  { n:13, time:"23:30", league:"德甲",   home:"多特蒙德",        away:"弗赖堡", short_h:"多特蒙德", short_a:"弗赖堡" },
  { n:14, time:"01:15", league:"挪超",   home:"利勒斯特罗姆",    away:"博德闪耀", short_h:"利勒斯特", short_a:"博德" },
  { n:15, time:"03:00", league:"西甲",   home:"比利亚雷亚尔",    away:"塞尔塔", short_h:"比利亚雷", short_a:"塞尔塔" },
  { n:16, time:"05:30", league:"巴西甲", home:"巴拉纳竞技",      away:"维多利亚", short_h:"巴拉纳", short_a:"维多利亚" },
  { n:17, time:"05:30", league:"巴西甲", home:"布拉干蒂诺RB",    away:"帕尔梅拉斯", short_h:"布拉干蒂诺", short_a:"帕尔梅拉斯" },
  { n:18, time:"07:00", league:"美职业", home:"洛杉矶银河",      away:"皇家盐湖城", short_h:"银河", short_a:"盐湖城" },
];

async function main() {
  const browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] });
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  
  await page.goto('https://live.nowscore.com/schedule.aspx?f=ft1', { waitUntil: 'networkidle', timeout: 60000 });
  await page.waitForTimeout(10000);
  
  // Get all text
  const text = await page.evaluate(() => document.body.innerText);
  const lines = text.split('\n').filter(l => l.trim());
  
  console.log('=== FULL SEARCH FOR RELEVANT MATCHES ===');
  // Search for each match
  for (const m of V17_MATCHES) {
    let found = false;
    for (let i = 0; i < lines.length; i++) {
      const l = lines[i];
      // Exact line format: \tleague\ttime\t完\thome[rank]\tscore\taway[rank]\tHTscore
      if (l.includes(m.short_h) && l.includes(m.short_a)) {
        console.log(`[${m.n}] ${m.league}: ${m.home} vs ${m.away} | ${l.replace(/\t/g, ' | ')}`);
        found = true;
        break;
      }
    }
    if (!found) {
      // Try broader search
      for (let i = 0; i < lines.length; i++) {
        const l = lines[i];
        if ((l.includes(m.short_h.substring(0, Math.max(2, m.short_h.length-1))) || 
             l.includes(m.short_a.substring(0, Math.max(2, m.short_a.length-1)))) &&
            l.includes('完')) {
          console.log(`[${m.n}] POSSIBLE: ${m.home} vs ${m.away} ≈ ${l.replace(/\t/g, ' | ')}`);
          found = true;
          break;
        }
      }
    }
    if (!found) {
      console.log(`[${m.n}] ${m.league}: ${m.home} vs ${m.away} -> NOT FOUND`);
    }
  }
  
  // Also show all lines with known matches from the previous run that we found
  console.log('\n=== ALL LINES CONTAINING 完 (finished) with HT scores ===');
  lines.filter(l => l.includes('完') && l.split('\t').length >= 6).slice(0, 350).forEach(l => {
    const parts = l.split('\t');
    if (parts.length >= 8) {
      // Format: league, time, "完", home[rank], score, away[rank], HTscore
      console.log(`${parts[0].trim()}\t${parts[1].trim()}\t${parts[3].trim()}\t${parts[4].trim()}\t${parts[5].trim()}\tHT:${parts[6].trim()}`);
    }
  });
  
  await browser.close();
}

main().catch(e => { console.error(e); process.exit(1); });
