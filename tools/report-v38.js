#!/usr/bin/env node
/**
 * V38 标准化报告 — 完整输出格式
 * 用法: node tools/report-v38.js
 */
const fs = require('fs');

const ANALYSIS_FILE = '/tmp/jiebao-analysis-v38.json';

function loadJSON(f) { try { return JSON.parse(fs.readFileSync(f, 'utf8')); } catch { return null; } }

function main() {
  const date = new Date();
  const dateStr = date.toISOString().split('T')[0];
  const timeStr = date.toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', hour: '2-digit', minute: '2-digit' });

  const analysis = loadJSON(ANALYSIS_FILE);
  if (!analysis || !analysis.matches || analysis.matches.length === 0) {
    console.log(`⚽ V38 推荐清单 | ${dateStr} ${timeStr}\n无符合条件比赛`);
    return;
  }

  let matches = analysis.matches;
  matches.sort((a, b) => {
    const ah = parseInt(a.time || '0'), am = parseInt((a.time || '').split(':')[1] || 0);
    const bh = parseInt(b.time || '0'), bm = parseInt((b.time || '').split(':')[1] || 0);
    return (ah * 60 + am) - (bh * 60 + bm);
  });

  console.log(`⚽ V38 推荐清单 | ${dateStr} ${timeStr}\n`);

  const h100 = matches.filter(m => m.h2hRate === 100);
  const other = matches.filter(m => m.h2hRate !== 100);

  // ── 100% 推荐 ──
  if (h100.length > 0) {
    console.log('🥇 上半场推荐（历史交锋上半场进球率 ≥ 80%）');
    console.log('─'.repeat(70));
    for (const m of h100) {
      const init = m.oddsInit || '-';
      const cur = m.oddsCur || '-';
      const oddsLine = init !== cur ? `${init}→${cur}` : init;
      console.log(`  ${m.time} ${m.league}`);
      console.log(`    ${m.home} vs ${m.away}`);
      console.log(`    H2H共${m.h2hCount}场 · 上半场进球率 ${m.h2hRate}% · 场均${m.h2hAvg}球`);
      console.log(`    半场大小球: ${oddsLine} | ${m.level || ''} | ${m.buyTiming || ''}`);
      if (m.teamHomeHAvg || m.teamAwayHAvg) {
        console.log(`    团队数据: 主HT场均${m.teamHomeHAvg || '?'} · 客HT场均${m.teamAwayHAvg || '?'}`);
      }
      console.log(`    ${m.advice}`);
      console.log('');
    }
  }

  // ── 80-89% 推荐 ──
  if (other.length > 0) {
    console.log('✅ 80-89%进球率推荐');
    console.log('─'.repeat(70));
    for (const m of other) {
      const init = m.oddsInit || '-';
      const cur = m.oddsCur || '-';
      const oddsLine = init !== cur ? `${init}→${cur}` : init;
      console.log(`  ${m.time} ${m.league}`);
      console.log(`    ${m.home} vs ${m.away}`);
      console.log(`    H2H共${m.h2hCount}场 · 上半场进球率 ${m.h2hRate}% · 场均${m.h2hAvg}球`);
      console.log(`    半场大小球: ${oddsLine} | ${m.level || ''} | ${m.buyTiming || ''}`);
      if (m.teamHomeHAvg || m.teamAwayHAvg) {
        console.log(`    团队数据: 主HT场均${m.teamHomeHAvg || '?'} · 客HT场均${m.teamAwayHAvg || '?'}`);
      }
      if (m.streakNote) console.log(`    ${m.streakNote}`);
      console.log(`    ${m.advice}`);
      console.log('');
    }
  }

  const totalHt = h100.length;
  const totalNd = other.length;
  console.log(`共 ${totalHt + totalNd} 场推荐（100%: ${totalHt} · 80-89%: ${totalNd}）\n`);

  // ── 买入时机 ──
  console.log('📌 买入时机');
  for (const m of [...h100, ...other]) {
    const rate = m.h2hRate;
    console.log(`  ${m.time} ${m.league} ${m.home}vs${m.away} [${rate}%] ${m.buyTiming}`);
  }
}

main();
