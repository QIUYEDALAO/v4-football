const fs = require('fs');

console.log('==========================================================');
console.log('  V17 18场推荐 vs 实际结果（4月26日比赛）');
console.log('==========================================================\n');

// All V17 matches with confirmed results
const results14 = [
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
  { no: 11, team: '阿尔克马尔', opp: '未知', ft: 'N/A', ht: 'N/A', htGoal: null, league: '荷甲', note: '4月26日无比赛' },
  { no: 12, team: '格拉茨风暴', opp: '奥地利维也纳', ft: '1-1', ht: '0-0', htGoal: false, league: '奥甲' },
  { no: 13, team: '博洛尼亚', opp: '罗马', ft: '0-2', ht: '0-2', htGoal: true, league: '意甲' },
  { no: 14, team: '塞尔塔', opp: '比利亚雷亚尔', ft: '1-2', ht: '0-2', htGoal: true, league: '西甲' },
  { no: 15, team: '圣吉罗斯', opp: '安德莱赫特', ft: '3-1', ht: '2-1', htGoal: true, league: '比甲' },
  { no: 16, team: '特罗姆瑟', opp: '桑德菲杰', ft: '3-1', ht: '2-0', htGoal: true, league: '挪超' },
  { no: 17, team: '赫根', opp: '未知', ft: 'N/A', ht: 'N/A', htGoal: null, league: '瑞典超', note: '4月26日无比赛' },
  { no: 18, team: '帕纳辛纳科斯', opp: '未知', ft: 'N/A', ht: 'N/A', htGoal: null, league: '希腊超', note: '4月26日无比赛' }
];

// Also load the V24 recommendations to compare
// Read V24 data from analysis file
let v24Data = { predictions: [] };
try {
  v24Data = JSON.parse(fs.readFileSync('/tmp/jiebao-analysis-v21.json', 'utf-8'));
} catch(e) {
  console.log('Could not read V24 data file');
}

console.log('╔════╦══════════════════╦══════════════╦══════════════╦══════╗');
console.log('║ #  ║ 比赛            ║  全场 ║  半场 ║ 验证  ║');
console.log('╠════╬══════════════════╬══════════════╬══════════════╬══════╣');

for (const m of results14) {
  const teamDisplay = m.team.padEnd(14);
  const scoreDisplay = m.ft && m.ft !== 'N/A' ? `FT ${m.ft}  HT ${m.ht}`.padEnd(14) : `无比赛`.padEnd(14);
  const status = m.htGoal === null ? '  -  ' : (m.htGoal ? ' ✅  ' : ' ❌  ');
  console.log(`║ ${String(m.no).padEnd(2)}║ ${teamDisplay}║ ${scoreDisplay}║ ${status}║`);
}

console.log('╚════╩══════════════════╩══════════════╩══════════════╩══════╝\n');

// Stats
const validMatches = results14.filter(m => m.htGoal !== null);
const hit = validMatches.filter(m => m.htGoal === true).length;
const miss = validMatches.filter(m => m.htGoal === false).length;
const noMatch = results14.filter(m => m.htGoal === null).length;

console.log(`统计：`);
console.log(`  - 实际有比赛的场次: ${validMatches.length}`);
console.log(`  - 上半场有进球(✅): ${hit}/${validMatches.length}`);
console.log(`  - 上半场无进球(❌): ${miss}/${validMatches.length}`);
console.log(`  - V17命中率: ${(hit/validMatches.length*100).toFixed(1)}%`);
console.log(`  - 当天无比赛的场次: ${noMatch}`);

// Now compare with V24
console.log('\n\n==========================================================');
console.log('  V24 推荐列表（来自jiebao-analysis-v21.json）');
console.log('==========================================================\n');

// Extract V24's RTP >= 80% matches
const v24HighConf = v24Data.predictions.filter(p => p.rtpScore >= 80);
console.log(`V24有 ${v24HighConf.length} 场评分≥80%（总共 ${v24Data.predictions.length} 场）\n`);

// Try to match them with our result data
console.log('V24高评分比赛：');
v24HighConf.forEach(p => {
  // Find match result using team names
  const home = p.homeTeam;
  const away = p.awayTeam;
  const htRate = p.htGoalRate;
  
  // Try to match with our known results
  let found = null;
  for (const r of validMatches) {
    if ((r.team.includes(home) || home.includes(r.team) || 
         (r.team.includes('流浪者') && home.includes('Rangers')) ||
         (r.team.includes('根特') && home.includes('Gent'))) ||
        (r.opp && (r.opp.includes(away) || away.includes(r.opp)))) {
      found = r;
      break;
    }
  }
  
  if (found) {
    console.log(`  ${home} vs ${away} (RTP=${p.rtpScore}%) → ${found.htGoal ? '✅' : '❌'}`);
  } else {
    console.log(`  ${home} vs ${away} (RTP=${p.rtpScore}%) → 待确认`);
  }
});

console.log('\n\n==========================================================');
console.log('  V17 vs V24 对比总结');
console.log('==========================================================\n');

// Known V24 matches from the previous session (3 matches verified)
// Previously: SBV精英✅, 佛罗伦萨❌, 下诺夫哥罗德✅
console.log('V24已验证的3场（直接从文件确认）：');
// Let me extract the specific V24 data
const v24sbv = v24Data.predictions.find(p => 
  p.homeTeam && (p.homeTeam.includes('Excelsior') || p.homeTeam.includes('精英')));
const v24fiorentina = v24Data.predictions.find(p =>
  p.homeTeam && (p.homeTeam.includes('Fiorentina') || p.homeTeam.includes('佛罗伦萨')));
const v24nizhny = v24Data.predictions.find(p =>
  p.homeTeam && (p.homeTeam.includes('Nizhny') || p.homeTeam.includes('诺夫')));

if (v24sbv) console.log(`  SBV精英: RTP=${v24sbv.rtpScore}% → ✅ (HT 2-0)`);
if (v24fiorentina) console.log(`  佛罗伦萨: RTP=${v24fiorentina.rtpScore}% → ❌ (HT 0-0)`);
if (v24nizhny) console.log(`  下诺夫哥罗德: RTP=${v24nizhny.rtpScore}% → ✅ (HT 1-1)`);
