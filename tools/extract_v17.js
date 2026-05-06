// Now we have the 2in1 page loaded. Let's intercept the ft1.js data
// and search for ALL matches. But actually we already have the complete ft1.txt
// Let me search for all V17 matches in the existing ft1 data

const fs = require('fs');
const text = fs.readFileSync('/tmp/ft1_full.txt', 'utf-8');

// OK from the page output I can see MANY Apr 26 matches including V17 ones:
// 英冠: 考文垂 vs 雷克瑟姆  角球5-4 (全)  1-1(半)
// 下诺夫哥罗德 vs 莫斯科斯巴达  角球3-7(全) 1-1(半)
// 德乙: 波鸿 vs 菲尔特  角球5-5(全) 1-0(半)
// 德乙: 纽伦堡 vs 马格德堡  角球3-5(全) 1-0(半)
// 德乙: 帕德博恩 vs 沙尔克04  角球7-2(全) 2-2(半)
// 根特 vs 布鲁日  角球7-9(全) 0-1(半)
// 挪超: 莫尔德 vs 瓦勒伦加  角球2-5(全) 1-1(半)
// 荷甲: SBV精英 vs 乌德勒支  角球3-2(全) 2-0(半)
// 意甲: 佛罗伦萨 vs 萨索洛  角球7-4(全) 0-0(半)
// 意甲: 热那亚 vs 科莫  角球2-3(全) 0-1(半)
// 法甲: 洛里昂 vs 斯特拉斯堡  角球9-7(全) 1-0(半)

// But wait, these are corner stats, not goals!
// In the 2in1 page, the numbers before the hyphen are home team corner kicks
// The numbers after the hyphen are away team corner kicks
// The score like "0-0" next to it could be the half time score OR more corners

// Let me look at the raw ft1.js data more carefully for the V17 matches
// The V17 matches I need:
const v17Teams = [
  '根特', '莫尔德', 'SBV精英', '下诺夫哥罗德',
  '佛罗伦萨', '流浪者', '莫斯科迪纳摩', '克拉斯诺达尔',
  '塞维利亚', '多特蒙德', '阿尔克马尔', '格拉茨',
  '博洛尼亚', '塞尔塔', '圣吉罗斯', '特罗姆瑟',
  '赫根', '帕纳辛纳科斯'
];

// Let me parse the ft1.js properly
// Scan each line for these teams
const lines = text.split('\n');

console.log('=== Searching V17 matches in ft1.js ===');
for (const line of lines) {
  const trimmed = line.trim();
  if (!trimmed.startsWith('A[')) continue;
  
  const quoted = trimmed.match(/'([^']*)'/g);
  if (!quoted || quoted.length < 8) continue;
  
  const homeCN = quoted[0].replace(/'/g,'');
  const awayCN = quoted[3].replace(/'/g,'');
  const homeEN = quoted[2].replace(/'/g,'');
  const awayEN = quoted[5].replace(/'/g,'');
  const time = quoted[6].replace(/'/g,'');
  const date = quoted[7].replace(/'/g,'');
  
  // Check if this matches any V17 team
  let matched = false;
  let matchName = '';
  
  // Match by both CN and EN names, excluding youth/women/B
  const isMatch = (name, target) => {
    if (name.includes('女') || name.includes('U2') || name.includes('U1') || name.includes('青年') || name.includes('后备') || name.includes('B队') || name.includes('Reserve')) return false;
    const lowerName = name.toLowerCase();
    const lowerTarget = target.toLowerCase();
    return lowerName.includes(lowerTarget) || lowerTarget.includes(lowerName);
  };
  
  const searchTerms = [
    // 1. 根特 / Gent
    {cn: '根特', en: 'Gent', name: '根特'},
    // 2. 莫尔德 / Molde
    {cn: '莫尔德', en: 'Molde', name: '莫尔德'},
    // 3. SBV精英 / Excelsior  
    {cn: '精英', en: 'Excelsior', name: 'SBV精英'},
    // 4. 下诺夫哥罗德 / Nizhny Novgorod
    {cn: '诺夫哥罗德', en: 'Nizhny', name: '下诺夫哥罗德'},
    // 5. 佛罗伦萨 / Fiorentina
    {cn: '佛罗伦萨', en: 'Fiorentina', name: '佛罗伦萨'},
    // 6. 流浪者 / Rangers
    {cn: '流浪者', en: 'Rangers', name: '流浪者'},
    // 7. 莫斯科迪纳摩 / Dynamo Moscow
    {cn: '莫斯科迪纳摩', en: 'Dynamo Moscow', name: '莫斯科迪纳摩'},
    // 8. 克拉斯诺达尔 / Krasnodar
    {cn: '克拉斯诺达尔', en: 'Krasnodar', name: '克拉斯诺达尔'},
    // 9. 塞维利亚 / Sevilla
    {cn: '塞维利亚', en: 'Sevilla', name: '塞维利亚'},
    // 10. 多特蒙德 / Dortmund
    {cn: '多特', en: 'Dortmund', name: '多特蒙德'},
    // 11. 阿尔克马尔 / AZ Alkmaar
    {cn: '阿尔克马尔', en: 'Alkmaar', name: '阿尔克马尔'},
    // 12. 格拉茨 / Sturm Graz
    {cn: '格拉茨', en: 'Sturm Graz', name: '格拉茨'},
    // 13. 博洛尼亚 / Bologna 
    {cn: '博洛尼亚', en: 'Bologna', name: '博洛尼亚'},
    // 14. 塞尔塔 / Celta Vigo
    {cn: '塞尔塔', en: 'Celta', name: '塞尔塔'},
    // 15. 圣吉罗斯 / Union Saint-Gilloise
    {cn: '圣吉罗斯', en: 'Union SG', name: '圣吉罗斯'},
    // 16. 特罗姆瑟 / Tromso
    {cn: '特罗姆瑟', en: 'Tromso', name: '特罗姆瑟'},
    // 17. 赫根 / Hacken
    {cn: '赫根', en: 'Hacken', name: '赫根'},
    // 18. 帕纳辛纳科斯 / Panathinaikos
    {cn: '帕纳辛纳', en: 'Panathinaikos', name: '帕纳辛纳科斯'}
  ];
  
  for (const s of searchTerms) {
    const inHomeCN = homeCN.includes(s.cn);
    const inAwayCN = awayCN.includes(s.cn);
    const inHomeEN = homeEN.toLowerCase().includes(s.en.toLowerCase());
    const inAwayEN = awayEN.toLowerCase().includes(s.en.toLowerCase());
    
    if ((inHomeCN || inAwayCN || inHomeEN || inAwayEN) && 
        !homeCN.includes('女') && !awayCN.includes('女') &&
        !homeCN.includes('U') && !awayCN.includes('U') &&
        !homeCN.includes('青年') && !awayCN.includes('青年') &&
        !homeCN.includes('后备') && !awayCN.includes('后备') &&
        !homeEN.includes('(W)') && !awayEN.includes('(W)') &&
        !homeEN.includes('U23') && !awayEN.includes('U23') &&
        !homeCN.includes('B队') && !awayCN.includes('B队')) {
      
      if (s.name === 'SBV精英' && (!homeCN.includes('SBV') && !awayCN.includes('SBV') && !homeEN.includes('Excelsior ') && !awayEN.includes('Excelsior '))) continue;
      if (s.name === '流浪者' && !homeCN.includes('流浪者') && !awayCN.includes('流浪者')) continue;
      if (s.name === '格拉茨' && (homeCN.includes('女') || awayCN.includes('女') || homeEN.includes('W)') || awayEN.includes('W)') || homeCN.includes('U') || awayCN.includes('U'))) continue;
      
      matched = true;
      matchName = s.name;
      break;
    }
  }
  
  if (!matched) {
    // Also check specific team IDs 
    continue;
  }
  
  // Extract scores - simpler approach
  // Find the position after the 8th quoted string (date)
  let idx = -1;
  for (let q = 0; q < 8; q++) {
    idx = trimmed.indexOf("'", idx + 1);
    idx = trimmed.indexOf("'", idx + 1);
  }
  
  const afterQuotes = trimmed.substring(idx + 1).replace(/^,/, '').replace(/\];?\s*$/, '');
  const nums = afterQuotes.split(',').map(s => parseInt(s.trim())).filter(n => !isNaN(n));
  
  if (nums.length >= 5) {
    const status = nums[0];
    const homeTotal = nums[1];
    const awayTotal = nums[2];
    const halfHome = nums[3];
    const halfAway = nums[4];
    
    const hasHTGoal = (halfHome + halfAway) > 0;
    
    if (time && homeCN && awayCN) {
      console.log(`${matchName}: ${date} ${time} ${homeCN} vs ${awayCN} → FT ${homeTotal}-${awayTotal} HT ${halfHome}-${halfAway} ${hasHTGoal ? '✅' : '❌'}`);
    }
  }
}
