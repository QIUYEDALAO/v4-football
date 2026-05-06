const fs = require('fs');
const v24Data = JSON.parse(fs.readFileSync('/tmp/jiebao-analysis-v21.json', 'utf-8'));
const v24Matches = v24Data.matches;

// Results from jiebao for V17 matches (15 actual matches)
const v17Results = {
  '根特': { ht: '0-1', htGoal: true, v17Rec: true },
  '莫尔德': { ht: '1-1', htGoal: true, v17Rec: true },
  'SBV精英': { ht: '2-0', htGoal: true, v17Rec: true },
  '下诺夫哥罗德': { ht: '1-1', htGoal: true, v17Rec: true },
  '佛罗伦萨': { ht: '0-0', htGoal: false, v17Rec: true },
  '格拉斯哥流浪者': { ht: '0-2', htGoal: true, v17Rec: true },
  '莫斯科迪纳摩': { ht: '1-0', htGoal: true, v17Rec: true },
  '克拉斯诺达尔': { ht: '1-1', htGoal: true, v17Rec: true },
  '塞维利亚': { ht: '0-0', htGoal: false, v17Rec: true },
  '多特蒙德': { ht: '3-0', htGoal: true, v17Rec: true },
  '格拉茨风暴': { ht: '0-0', htGoal: false, v17Rec: true },
  '博洛尼亚': { ht: '0-2', htGoal: true, v17Rec: true },
  '塞尔塔': { ht: '0-2', htGoal: true, v17Rec: true },
  '圣吉罗斯': { ht: '2-1', htGoal: true, v17Rec: true },
  '特罗姆瑟': { ht: '2-0', htGoal: true, v17Rec: true }
};

// Map V24 matches to corresponding V17 teams
// V24 uses different team name formats
const v24ToV17 = {};
for (const vm of v24Matches) {
  const h = vm.home || '';
  const a = vm.away || '';
  
  if (h.includes('格拉茨') || h.includes('Sturm')) v24ToV17['格拉茨风暴'] = vm;
  else if (h.includes('多特') || h.includes('Dortmund')) v24ToV17['多特蒙德'] = vm;
  else if (h.includes('塞尔塔') || h.includes('Celta') || a.includes('塞尔塔')) v24ToV17['塞尔塔'] = vm;
  else if (a === '塞维利亚' || a.includes('Sevilla') || (a.includes('塞维利亚') && vm.league === '西甲')) v24ToV17['塞维利亚'] = vm;
  else if (h === '圣吉罗斯' || h.includes('Union S') || (h === '圣吉罗斯联合' ) || (h.includes('圣吉罗斯') && vm.league === '比甲')) v24ToV17['圣吉罗斯'] = vm;
  else if (h.includes('特罗姆瑟') || h.includes('Tromso') || (h.includes('特罗姆瑟') && vm.league === '挪超')) v24ToV17['特罗姆瑟'] = vm;
  else if (h === '根特' || h.includes('Gent')) v24ToV17['根特'] = vm;
  else if (h === '莫尔德' || h.includes('Molde')) v24ToV17['莫尔德'] = vm;
  else if (h.includes('精英') || h.includes('Excelsior')) v24ToV17['SBV精英'] = vm;
  else if (h.includes('诺夫哥罗德') || h.includes('Nizhny')) v24ToV17['下诺夫哥罗德'] = vm;
  else if (h.includes('佛罗伦萨') || h.includes('Fiorentina')) v24ToV17['佛罗伦萨'] = vm;
  else if (h.includes('流浪者') || h.includes('Rangers')) v24ToV17['格拉斯哥流浪者'] = vm;
  else if (h.includes('莫斯科迪纳摩') || h.includes('Dynamo Moscow')) v24ToV17['莫斯科迪纳摩'] = vm;
  else if (h.includes('克拉斯诺达尔') || h.includes('Krasnodar')) v24ToV17['克拉斯诺达尔'] = vm;
  else if (h.includes('博洛尼亚') || h.includes('Bologna')) v24ToV17['博洛尼亚'] = vm;
}

console.log('=============================================================');
console.log('  V17 vs V24 评分模型对比 — 4月26日验证');
console.log('=============================================================\n');

console.log('┌────┬──────────────────────┬────┬────┬────┬──────┬──────┬──────┐');
console.log('│ #  │ 比赛                 │V17 │V24 │V24 │ 半场 │ 验证 │ 命中 │');
console.log('│    │                      │推荐│评分│推荐│      │      │      │');
console.log('├────┼──────────────────────┼────┼────┼────┼──────┼──────┼──────┤');

const comparisonTable = [];
let v17Hit = 0, v17Total = 0;
let v24Hit = 0, v24Total80 = 0;

for (const [team, r] of Object.entries(v17Results)) {
  const vm = v24ToV17[team];
  const v24Score = vm ? vm.score : 'N/A';
  const v24Rec = vm ? (vm.recommend || (vm.score >= 80 ? '推荐' : '不推荐')) : '-';
  const v24Qualified = vm && vm.score >= 80;
  
  const resultIcon = r.htGoal ? '✅' : '❌';
  
  console.log(`│ ${String(Object.keys(v17Results).indexOf(team)+1).padEnd(2)}│ ${team.padEnd(20)}│ 是  │ ${String(v24Score).padEnd(3)}│ ${v24Rec.padEnd(4)}│ ${r.ht.padEnd(4)}│ ${resultIcon}    │` +
    (v24Qualified !== undefined ? '' : ''));
  
  // V17 tracking
  v17Total++;
  if (r.htGoal) v17Hit++;
  
  comparisonTable.push({ team, v17Hit: r.htGoal, v24Qualified, v24Score });
}

// Now let's get V24's own >=80% matches data
// We need to find actual results for V24's >80% matches
console.log('├────┼──────────────────────┼────┼────┼────┼──────┼──────┼──────┤');
console.log('│    │                      │    │    │    │      │      │      │');

// Check V24's >=80% matches on the page
const v24High = v24Matches.filter(m => m.score >= 80);
console.log(`\n\nV24共 ${v24High.length} 场评分≥80%比赛:`);
console.log('（需从页面获取这些比赛的实际HT结果...）\n');

// The V24 80%+ matches include:
// 格拉茨风暴 80 - 我们已有: ❌
// 汉坎 86, KFUM奥斯陆 90, 多特蒙德 83 - 已有: ✅
// 比利亚雷亚尔vs塞尔塔 87 - 塞尔塔是客队, V17反方向
// 布拉干蒂诺RB 84, 洛杉矶银河 84, 坎昆 90

// For the proper comparison, we need V24 >=80% matches that overlap with V17
// Then we compare: V17 metric (all 15 matches) vs V24 metric (only >=80% subset)

console.log('\n=============================================================');
console.log('  总结对比');
console.log('=============================================================\n');

// V17: 推荐≥80%, 15场, 12/15 = 80%
// V24: among the 15 V17 matches, how many would V24 filter?
const v17Total15 = 15;
const v17Hits = 12;
console.log(`V17（基础模型）:`);
console.log(`  筛选条件: H2H(30%) + 主队近期(35%) + 客队近期(35%)`);
console.log(`  推荐策略: 半场进球率≥80%`);
console.log(`  推荐场次: ${v17Total15}场`);
console.log(`  实际命中: ${v17Hits}/${v17Total15} = ${(v17Hits/v17Total15*100).toFixed(1)}%`);
console.log(`  未命中: 佛罗伦萨(0-0)、塞维利亚(0-0)、格拉茨风暴(0-0)\n`);

console.log(`V24（加权优化模型）:`);
console.log(`  筛选条件: H2H(40%) + 主客近期(各30%) + 盘口信号 + 联赛因子`);
console.log(`  针对V17的15场比赛: V24评分≥80的占 ${v24ToV17['多特蒙德'] ? 1 : 0}场 （多特蒙德83分）`);
console.log('');
console.log(`V24自身分析(${v24Matches.length}场):`);
console.log(`  评分≥80分: ${v24High.length}场`);

// Check which V24 >=80% matches we can verify from the page
// We have data for: 格拉茨风暴(80, ❌), 多特蒙德(83, ✅), 塞尔塔(87, ✅)
let v24FromPage = 0;
let v24PageHit = 0;

console.log(`  其中可验证:`);
for (const vm of v24High) {
  const h = vm.home || '';
  const a = vm.away || '';
  
  if (h.includes('格拉茨')) {
    console.log(`    - ${h} vs ${a}: 评分${vm.score} → 实际HT 0-0 ❌`);
    v24FromPage++; 
  } else if (h.includes('多特')) {
    console.log(`    - ${h} vs ${a}: 评分${vm.score} → 实际HT 3-0 ✅`);
    v24FromPage++;
    v24PageHit++;
  } else if (h.includes('比利亚雷亚尔') && a.includes('塞尔塔')) {
    console.log(`    - ${h} vs ${a}: 评分${vm.score} → 实际HT 2-0 ✅ (塞尔塔视角)`);
    v24FromPage++;
    v24PageHit++;
  } else if (h.includes('汉坎')) {
    // Need to check - not a V17 team but V24 recommends it
    console.log(`    - ${h} vs ${a}: 评分${vm.score} → 需要在页面上查找实际结果`);
  } else if (h.includes('KFUM')) {
    console.log(`    - ${h} vs ${a}: 评分${vm.score} → 需要在页面上查找实际结果`);
  } else {
    console.log(`    - ${h} vs ${a}: 评分${vm.score}`);
  }
}

if (v24FromPage > 0) {
  console.log(`\n  V24≥80%可验证: ${v24PageHit}/${v24FromPage} = ${(v24PageHit/v24FromPage*100).toFixed(1)}%`);
}

// Final verdict
console.log(`\n=============================================================`);
console.log(`  V17可以直接对比: 15场中12场命中 = 80.0%`);
console.log(`  V24需要更多数据对比，但交叉分析已可看出差异`);
console.log(`=============================================================`);
