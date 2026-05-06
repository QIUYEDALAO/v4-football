const { chromium } = require('playwright');

async function main() {
  const browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] });
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  
  await page.goto('https://live.nowscore.com/schedule.aspx?f=ft2', { waitUntil: 'networkidle', timeout: 60000 });
  await page.waitForTimeout(8000);
  
  const text = await page.evaluate(() => document.body.innerText);
  const lines = text.split('\n').filter(l => l.trim());
  
  console.log('=== f=ft2 MATCHES FROM RELEVANT LEAGUES ===');
  const v17Leagues = ['荷甲','意甲','俄超','比甲','挪超','苏超','瑞典超','奥甲冠',
    '德甲','西甲','巴西甲','美职业'];
  
  lines.forEach(l => {
    for (const league of v17Leagues) {
      if ((l.includes(league) || l.includes('瑞典超') || l.includes('奥甲冠')) && l.includes('完')) {
        console.log(l.replace(/\t/g, ' | '));
        break;
      }
    }
  });
  
  console.log('\n=== SPECIFIC SEARCH ===');
  const keywords = ['SBV精英','佛罗伦萨','诺夫哥罗德','根特','莫尔德','流浪者',
    '迪纳摩','克拉斯诺达尔','布洛马','格拉茨','汉坎','KFUM',
    '多特蒙德','利勒斯特','比利亚雷','巴拉纳','布拉干蒂诺','银河'];
  
  for (const kw of keywords) {
    const found = lines.filter(l => l.includes(kw));
    if (found.length > 0) {
      console.log(kw + ': ' + found[0].replace(/\t/g, ' | '));
    } else {
      console.log(kw + ': NOT FOUND');
    }
  }
  
  await browser.close();
}

main().catch(e => { console.error(e); process.exit(1); });
