const { chromium } = require('playwright');

const V17_MATCHES = [
  { n:1, time:"18:15", league:"荷甲",    home:"SBV精英",         away:"乌德勒支" },
  { n:2, time:"18:30", league:"意甲",    home:"佛罗伦萨",        away:"萨索洛" },
  { n:3, time:"19:00", league:"俄超",    home:"下诺夫哥罗德",    away:"莫斯科斯巴达" },
  { n:4, time:"19:30", league:"比甲冠",  home:"根特",            away:"布鲁日" },
  { n:5, time:"20:30", league:"挪超",    home:"莫尔德",          away:"瓦勒伦加" },
  { n:6, time:"22:00", league:"苏超冠",  home:"格拉斯哥流浪者",  away:"马瑟韦尔" },
  { n:7, time:"22:00", league:"俄超",    home:"莫斯科迪纳摩",    away:"索契" },
  { n:8, time:"22:00", league:"俄超",    home:"克拉斯诺达尔",    away:"马哈奇卡拉" },
  { n:9, time:"22:30", league:"瑞典超",  home:"布洛马波卡纳",    away:"瓦斯特拉斯" },
  { n:10, time:"23:00", league:"奥甲冠", home:"格拉茨风暴",      away:"奥地利维也纳" },
  { n:11, time:"23:00", league:"挪超",   home:"汉坎",            away:"斯达" },
  { n:12, time:"23:00", league:"挪超",   home:"KFUM奥斯陆",      away:"萨普斯堡" },
  { n:13, time:"23:30", league:"德甲",   home:"多特蒙德",        away:"弗赖堡" },
  { n:14, time:"01:15", league:"挪超",   home:"利勒斯特罗姆",    away:"博德闪耀" },
  { n:15, time:"03:00", league:"西甲",   home:"比利亚雷亚尔",    away:"塞尔塔" },
  { n:16, time:"05:30", league:"巴西甲", home:"巴拉纳竞技",      away:"维多利亚" },
  { n:17, time:"05:30", league:"巴西甲", home:"布拉干蒂诺RB",    away:"帕尔梅拉斯" },
  { n:18, time:"07:00", league:"美职业", home:"洛杉矶银河",      away:"皇家盐湖城" },
];

async function main() {
  console.log('Checking 捷报比分 完场比分 for April 26...\n');
  
  const browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] });
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  
  // Go to finished matches page
  await page.goto('https://live.nowscore.com/schedule.aspx?f=ft1', { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.waitForTimeout(8000);

  // Find and click "2026-04-26 (星期六)" in the date bar  
  const dateClick = await page.evaluate(() => {
    const links = Array.from(document.querySelectorAll('a'));
    const target = links.find(l => l.textContent.includes('2026-04-26'));
    if (target) { target.click(); return true; }
    return false;
  });
  console.log('Date click result:', dateClick);
  await page.waitForTimeout(5000);
  
  // Get full page content
  const lines = (await page.evaluate(() => document.body.innerText)).split('\n').filter(l => l.trim());
  
  // Create a lookup of all match lines
  const matchLines = {};
  for (let i = 0; i < lines.length; i++) {
    matchLines[i] = lines[i];
  }
  
  // Search for our specific matches
  console.log('\n=== SPECIFIC MATCH SEARCH ===');
  for (const m of V17_MATCHES) {
    for (let i = 0; i < lines.length; i++) {
      const l = lines[i];
      // Check if this line contains both home and away team names
      if (l.includes(m.home) || l.includes(m.away)) {
        // Show this line and surrounding lines for context
        const start = Math.max(0, i-1);
        const end = Math.min(lines.length, i+2);
        for (let j = start; j < end; j++) {
          console.log(`[${m.n}] ${j}: ${lines[j]}`);
        }
        console.log('---');
        break;
      }
    }
  }
  
  await browser.close();
  console.log('\nDone');
}

main().catch(e => { console.error(e); process.exit(1); });
