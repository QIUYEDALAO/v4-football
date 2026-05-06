const { chromium } = require('playwright');

async function main() {
  const browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] });
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  
  // The default page (schedule.aspx) shows today's finished matches
  // Today is April 27, but some of the V17 matches kicked off on April 26 
  // The ones that played earlier (evening Apr 26) finished today
  // Let me load the default and look for matches starting Apr 26
  
  await page.goto('https://live.nowscore.com/schedule.aspx', { waitUntil: 'networkidle', timeout: 60000 });
  await page.waitForTimeout(8000);
  
  const text = await page.evaluate(() => document.body.innerText);
  const lines = text.split('\n').filter(l => l.trim());
  
  // The default shows today's finished matches
  // Let me check specific matches by looking at ALL lines
  console.log('=== TOTAL LINES ===', lines.length);
  
  // Look for all match lines from 18:00 onwards (these would be Apr 26 evening matches)  
  console.log('\n=== LINES FROM 18:00 onwards ===');
  lines.filter(l => l.match(/\d{2}:\d{2}/)).slice(0, 30).forEach(l => console.log(l));
  
  // Need to search through the page more carefully
  // The 完场比分 page shows FINISHED matches for the current date
  // April 26 matches finished on April 26 (those played in European evening)
  // But some late matches (01:15, 03:00, 05:30, 07:00) finished on April 27
  
  // All V17 matches:
  const v17 = [
    { n:1, time:"18:15", home:"SBV精英" },
    { n:2, time:"18:30", home:"佛罗伦萨" },
    { n:3, time:"19:00", home:"下诺夫哥罗德" },
    { n:4, time:"19:30", home:"根特" },
    { n:5, time:"20:30", home:"莫尔德" },
    { n:6, time:"22:00", home:"格拉斯哥流浪者" },
    { n:7, time:"22:00", home:"莫斯科迪纳摩" },
    { n:8, time:"22:00", home:"克拉斯诺达尔" },
    { n:9, time:"22:30", home:"布洛马波卡纳" },
    { n:10, time:"23:00", home:"格拉茨风暴" },
    { n:11, time:"23:00", home:"汉坎" },
    { n:12, time:"23:00", home:"KFUM奥斯陆" },
    { n:13, time:"23:30", home:"多特蒙德" },
    { n:14, time:"01:15", home:"利勒斯特罗姆" },
    { n:15, time:"03:00", home:"比利亚雷亚尔" },
    { n:16, time:"05:30", home:"巴拉纳竞技" },
    { n:17, time:"05:30", home:"布拉干蒂诺RB" },
    { n:18, time:"07:00", home:"洛杉矶银河" },
  ];
  
  console.log('\n=== SEARCHING FOR V17 MATCHES ===');
  for (const m of v17) {
    let found = false;
    for (let i = 0; i < lines.length; i++) {
      const l = lines[i];
      if (l.includes(m.home)) {
        const parts = l.split('\t').filter(p => p.trim());
        // Try to extract HT score
        // format is usually: league\ttime\tstatus\thome\tfullscore\taway\thalfscore
        console.log(`[${m.n}] ${m.home}: ${parts.join(' | ')}`);
        found = true;
        break;
      }
    }
    if (!found) console.log(`[${m.n}] ${m.home}: NOT FOUND`);
  }
  
  await browser.close();
}

main().catch(e => { console.error(e); process.exit(1); });
