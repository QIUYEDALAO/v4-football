const fs = require('fs');

console.log('==========================================================');
console.log('  V17 18场推荐 vs 实际结果（4月26日比赛）');
console.log('==========================================================\n');

const results = [
  { no: 1,  team: '根特', opp: '布鲁日', ft: '0-2', ht: '0-1', htGoal: true, league: '比甲' },
  { no: 2,  team: '莫尔德', opp: '瓦勒伦加', ft: '5-1', ht: '1-1', htGoal: true, league: '挪超' },
  { no: 3,  team: 'SBV精英', opp: '乌德勒支', ft: '5-0', ht: '2-0', htGoal: true, league: '荷甲' },
  { no: 4,  team: '下诺夫哥罗德', opp: '莫斯科斯巴达', ft: '1-2', ht: '1-1', htGoal: true, league: '俄超' },
  { no: 5,  team: '佛罗伦萨', opp: '萨索洛', ft: '0-0', ht: '0-0', htGoal: false, league: '意甲' },
  { no: 6,  team: '格拉斯哥流浪者', opp: '马瑟韦尔', ft: '2-3', ht: '0-2', htGoal: true, league: '苏超' },
  { no: 7,  team: '莫斯科迪纳摩', opp: '索契', ft: '2-0', ht: '1-0', htGoal: true, league: '俄超' },
  { no: 8,  team: '克拉斯诺达尔', opp: '马哈奇卡拉', ft: '2-1', ht: '1-1', htGoal: true, league: '俄超' },
  { no: 9,  team: '塞维利亚', opp: '奥萨苏纳', ft: '1-2', ht: '0-0', htGoal: false, league: '西甲' },
  { no: 10, team: '多特蒙德', opp: '弗赖堡', ft: '4-0', ht: '3-0', htGoal: true, league: '德甲' },
  { no: 11, team: '阿尔克马尔', opp: '-', ft: 'N/A', ht: 'N/A', htGoal: null, league: '荷甲', note: '当日无比赛' },
  { no: 12, team: '格拉茨风暴', opp: '奥地利维也纳', ft: '1-1', ht: '0-0', htGoal: false, league: '奥甲' },
  { no: 13, team: '博洛尼亚', opp: '罗马', ft: '0-2', ht: '0-2', htGoal: true, league: '意甲' },
  { no: 14, team: '塞尔塔', opp: '比利亚雷亚尔', ft: '1-2', ht: '0-2', htGoal: true, league: '西甲' },
  { no: 15, team: '圣吉罗斯', opp: '安德莱赫特', ft: '3-1', ht: '2-1', htGoal: true, league: '比甲' },
  { no: 16, team: '特罗姆瑟', opp: '桑德菲杰', ft: '3-1', ht: '2-0', htGoal: true, league: '挪超' },
  { no: 17, team: '赫根', opp: '-', ft: 'N/A', ht: 'N/A', htGoal: null, league: '瑞典超', note: '当日无比赛' },
  { no: 18, team: '帕纳辛纳科斯', opp: '-', ft: 'N/A', ht: 'N/A', htGoal: null, league: '希腊超', note: '当日无比赛' }
];

console.log('╔════╦══════════════════╦═══════════════════╦══════╗');
console.log('║ #  ║ 比赛            ║ 全场 FT 半场 HT   ║ 验证 ║');
console.log('╠════╬══════════════════╬═══════════════════╬══════╣');
for (const m of results) {
  const name = m.team.padEnd(14);
  const score = m.htGoal === null ? `无比赛            ` : `FT ${m.ft}  HT ${m.ht}`.padEnd(17);
  const status = m.htGoal === null ? '  -  ' : (m.htGoal ? ' ✅  ' : ' ❌  ');
  console.log(`║ ${String(m.no).padEnd(2)}║ ${name}║ ${score}║ ${status}║`);
}
console.log('╚════╩══════════════════╩═══════════════════╩══════╝\n');

const valid = results.filter(m => m.htGoal !== null);
const hit = valid.filter(m => m.htGoal === true).length;
const miss = valid.filter(m => m.htGoal === false).length;
const none = results.filter(m => m.htGoal === null).length;

console.log(`📊 V17 统计：`);
console.log(`  实际有比赛: ${valid.length}场`);
console.log(`  上半场有进球(✅): ${hit}/${valid.length}`);
console.log(`  上半场无进球(❌): ${miss}/${valid.length}`);
console.log(`  命中率: ${(hit/valid.length*100).toFixed(1)}%`);
console.log(`  当日无比赛: ${none}场\n`);

console.log('==========================================================');
console.log('  V24 对比分析');
console.log('==========================================================\n');

let v24Data;
try {
  v24Data = JSON.parse(fs.readFileSync('/tmp/jiebao-analysis-v21.json', 'utf-8'));
} catch (e) {
  console.log('Error reading V24:', e.message);
  process.exit(1);
}

const v24Matches = v24Data.matches || [];
console.log(`V24共分析 ${v24Matches.length} 场\n`);

// Find V24's >=80% matches
const v24High = v24Matches.filter(m => m.score >= 80);
// Find V24's >=90% matches
const v24VeryHigh = v24Matches.filter(m => m.score >= 90);

// Show V24 scores for the V17 matches
console.log('--- V24对V17 18场的评分 ---');
for (const m of results) {
  if (m.htGoal === null) {
    console.log(`${m.team}: 当日无比赛`);
    continue;
  }
  
  // Try to find V24's match for this team
  let v24Match = null;
  for (const vm of v24Matches) {
    const h = vm.home || '';
    const a = vm.away || '';
    if (h.includes(m.team) || h.includes(m.opp) || a.includes(m.team) || a.includes(m.opp) ||
        (m.team === '格拉斯哥流浪者' && (h.includes('Rangers') || h.includes('流浪者'))) ||
        (m.team === 'SBV精英' && (h.includes('Excelsior') || h.includes('精英')))) {
      v24Match = vm;
      break;
    }
  }
  
  const v24Score = v24Match ? v24Match.score : 'N/A';
  const v24Rec = v24Match ? (v24Match.recommend || '') : '';
  const v24Action = v24Match ? (v24Match.bettingAction || '') : '';
  console.log(`${m.team}: V17推荐=≥80%, V24评分=${v24Score} ${v24Rec} → 实际HT=${m.ht} ${m.htGoal ? '✅' : '❌'}`);
}

// List all V24 >= 80%
console.log('\n\n--- V24 评分≥80%比赛列表 ---');
for (const vm of v24High) {
  console.log(`${vm.league} ${vm.time} ${vm.home} vs ${vm.away}: score=${vm.score} rec=${vm.recommend} action=${vm.bettingAction}`);
}

// Summary comparison
console.log('\n\n==========================================================');
console.log('  V17 vs V24 总结');
console.log('==========================================================\n');

console.log(`V17: 推荐≥80%比赛 ${valid.length}场 → 命中 ${hit}/${valid.length} (${(hit/valid.length*100).toFixed(1)}%)`);
console.log(`V24: 评分≥80%比赛 ${v24High.length}场, 评分≥90%比赛 ${v24VeryHigh.length}场`);
console.log(`V24: 平均预测分数 ${(v24Matches.reduce((s,m) => s + m.score, 0) / v24Matches.length).toFixed(1)}`);
