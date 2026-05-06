#!/usr/bin/env node
/**
 * V38.1 验证工具 — 从捷报比分完赛页面获取比赛结果
 * 用法: node tools/verify-v38.1-v2.js
 */
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const PRED_FILE = path.join(__dirname, '..', 'data', '验证存档', 'v38.1', 'predictions.json');

function loadJSON(f) { try { return JSON.parse(fs.readFileSync(f, 'utf8')); } catch { return null; } }
function saveJSON(f, d) { fs.writeFileSync(f, JSON.stringify(d, null, 2)); }

/**
 * 从捷报比分行HTML提取比赛数据
 */
function parseMatches(rows) {
  const matches = [];
  
  for (const row of rows) {
    const text = row.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
    if (!text || text.length < 10) continue;
    
    // 跳过非比赛行
    if (text.includes('首页') || text.includes('选\t联赛') || text.includes('登录')) continue;
    
    // 检查点球行 - 合并到上一场比赛
    if (text.includes('点球') || text.includes('先开球')) continue;
    
    // 检查是否有 "完" 状态
    const parts = text.split(/\s+/);
    const statusIdx = parts.findIndex(p => p === '完');
    if (statusIdx === -1) continue;
    
    const league = parts[0];
    const time = parts[1];
    
    // 找到比分 (包含"-"的)
    let scoreIdx = -1;
    for (let i = statusIdx + 1; i < parts.length; i++) {
      if (/^\d+-\d+$/.test(parts[i])) {
        scoreIdx = i;
        break;
      }
    }
    if (scoreIdx === -1) continue;
    
    // 主队累加直到比分前
    let homeTeam = '';
    for (let i = statusIdx + 1; i < scoreIdx; i++) {
      if (!parts[i].match(/^\[.*\]$/)) {
        homeTeam += (homeTeam ? ' ' : '') + parts[i];
      }
    }
    
    const score = parts[scoreIdx];
    
    // 找半场比分 (比分之后第一个"数字-数字")
    let htScore = null;
    for (let i = scoreIdx + 1; i < parts.length; i++) {
      if (/^\d+-\d+$/.test(parts[i])) {
        htScore = parts[i];
        break;
      }
    }
    
    const scoreParts = score.split('-').map(Number);
    const htParts = htScore ? htScore.split('-').map(Number) : null;
    
    matches.push({
      league,
      time,
      homeTeam,
      score,
      htScore,
      ftHome: scoreParts[0],
      ftAway: scoreParts[1],
      htHome: htParts ? htParts[0] : null,
      htAway: htParts ? htParts[1] : null,
      htHasGoal: htParts ? (htParts[0] > 0 || htParts[1] > 0) : null,
      ftHasGoal: scoreParts[0] > 0 || scoreParts[1] > 0,
    });
  }
  
  return matches;
}

// 手动修正的比赛匹配映射（自动匹配可能出错时用）
const MANUAL_MATCHES = {
  // matchId -> { htScore, ftScore, htHasGoal, ftHasGoal, lfHasGoal }
};

async function main() {
  const data = loadJSON(PRED_FILE);
  if (!data || !data.predictions) {
    console.log('❌ 无推荐数据');
    return;
  }
  
  const preds = data.predictions.filter(p => p.date === '2026-05-03');
  console.log(`🔍 V38.1 验证 - 2026-05-03  |  推荐共 ${preds.length} 条\n`);
  
  // 获取完赛数据
  console.log('📡 正在从捷报比分获取完赛数据...');
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1280, height: 2000 } });
  
  await page.goto('https://live.nowscore.com/schedule.aspx?f=ft1&d=2026-05-03', { 
    waitUntil: 'networkidle', timeout: 30000 
  }).catch(e => console.log('  ⚠️', e.message.substring(0,50)));
  await page.waitForTimeout(3000);
  
  const rows = await page.evaluate(() => {
    return Array.from(document.querySelectorAll('tr')).map(tr => tr.outerHTML);
  });
  
  const matches = parseMatches(rows);
  console.log(`  采集到 ${matches.length} 场比赛\n`);
  
  // 验证
  const htPreds = preds.filter(p => p.matchId.endsWith('_HT'));
  const ftPreds = preds.filter(p => p.matchId.endsWith('_FT'));
  
  // 修正已知的匹配问题
  const nameFixMap = {
    '门兴格拉德巴赫': undefined, // 自动匹配已工作
  };
  
  console.log('='.repeat(70));
  let verifiedCount = 0;
  
  // 上半场
  for (const p of htPreds) {
    const match = matches.find(m => 
      (m.homeTeam.includes(p.home) || p.home.includes(m.homeTeam)) &&
      (p.league.replace(/[降冠附\(\)\d]/g,'').trim().includes(m.league.replace(/[降冠附\(\)\d]/g,'').trim()) ||
       m.league.includes(p.league.replace(/[降冠附\(\)\d]/g,'').trim()))
    );
    
    if (match) {
      p.verified = true;
      p.htScore = match.htScore;
      p.htHasGoal = match.htHasGoal;
      p.ftScore = match.score;
      verifiedCount++;
      const emoji = match.htHasGoal ? '✅' : '❌';
      console.log(`  ${emoji} [HT] ${p.league} ${p.home} ${match.score} (半${match.htScore}) ${p.away}`);
    } else {
      console.log(`  ❓ [HT] ${p.league} ${p.home} vs ${p.away} — 未匹配`);
    }
  }
  
  // 下半场
  for (const p of ftPreds) {
    const match = matches.find(m => 
      (m.homeTeam.includes(p.home) || p.home.includes(m.homeTeam)) &&
      (p.league.replace(/[降冠附\(\)\d]/g,'').trim().includes(m.league.replace(/[降冠附\(\)\d]/g,'').trim()) ||
       m.league.includes(p.league.replace(/[降冠附\(\)\d]/g,'').trim()))
    );
    
    if (match) {
      // 下半场有球判断
      let lfHasGoal = false;
      if (match.htScore) {
        const ftGoals = match.ftHome + match.ftAway;
        const htGoals = match.htHome + match.htAway;
        lfHasGoal = ftGoals > htGoals;
      } else {
        lfHasGoal = match.ftHasGoal;
      }
      
      p.verified = true;
      p.ftScore = match.score;
      p.ftHasGoal = lfHasGoal;
      p.htScore = match.htScore;
      verifiedCount++;
      
      const emoji = lfHasGoal ? '✅' : '❌';
      const htInfo = match.htScore ? ` (半${match.htScore})` : '';
      console.log(`  ${emoji} [FT] ${p.league} ${p.home} ${match.score}${htInfo} ${p.away} — ${lfHasGoal ? '下半场有球' : '下半场无球'}`);
    } else {
      console.log(`  ❓ [FT] ${p.league} ${p.home} vs ${p.away} — 未匹配`);
    }
  }
  
  console.log(`\n✅ 验证 ${verifiedCount}/${preds.length} 条`);
  
  // 保存
  saveJSON(PRED_FILE, data);
  
  // 统计
  printStats(data.predictions);
  
  await browser.close();
}

function printStats(preds) {
  const htPreds = preds.filter(p => p.matchId.endsWith('_HT') && p.verified);
  const ftPreds = preds.filter(p => p.matchId.endsWith('_FT') && p.verified);
  
  console.log('\n📊 统计报告');
  console.log('='.repeat(60));
  
  if (htPreds.length > 0) {
    console.log('\n⚡ 上半场:');
    const groups = { '100%': { t: 0, h: 0 }, '90%': { t: 0, h: 0 }, '80-89%': { t: 0, h: 0 } };
    htPreds.forEach(p => {
      const k = p.h2hRate >= 100 ? '100%' : p.h2hRate >= 90 ? '90%' : '80-89%';
      groups[k].t++;
      if (p.htHasGoal) groups[k].h++;
    });
    let totH = 0, totT = 0;
    for (const [k, g] of Object.entries(groups)) {
      if (g.t === 0) continue;
      const rate = (g.h / g.t * 100).toFixed(1) + '%';
      const y = ((g.h * 1.85 - g.t) / g.t * 100).toFixed(1);
      console.log(`  ${k.padEnd(8)} ${g.h}/${g.t}  命中率${rate}  收益${y}%`);
      totH += g.h; totT += g.t;
    }
    if (totT > 0) {
      const tr = (totH / totT * 100).toFixed(1) + '%';
      const ty = ((totH * 1.85 - totT) / totT * 100).toFixed(1);
      console.log(`  ────────────────────────────`);
      console.log(`  总计    ${totH}/${totT}  命中率${tr}  收益${ty}%`);
    }
  }
  
  if (ftPreds.length > 0) {
    console.log('\n⚽ 下半场:');
    const groups = { '100%': { t: 0, h: 0 }, '90%': { t: 0, h: 0 }, '80-89%': { t: 0, h: 0 } };
    ftPreds.forEach(p => {
      const k = p.h2hRate >= 100 ? '100%' : p.h2hRate >= 90 ? '90%' : '80-89%';
      groups[k].t++;
      if (p.ftHasGoal) groups[k].h++;
    });
    let totH = 0, totT = 0;
    for (const [k, g] of Object.entries(groups)) {
      if (g.t === 0) continue;
      const rate = (g.h / g.t * 100).toFixed(1) + '%';
      const y = ((g.h * 1.85 - g.t) / g.t * 100).toFixed(1);
      console.log(`  ${k.padEnd(8)} ${g.h}/${g.t}  命中率${rate}  收益${y}%`);
      totH += g.h; totT += g.t;
    }
    if (totT > 0) {
      const tr = (totH / totT * 100).toFixed(1) + '%';
      const ty = ((totH * 1.85 - totT) / totT * 100).toFixed(1);
      console.log(`  ────────────────────────────`);
      console.log(`  总计    ${totH}/${totT}  命中率${tr}  收益${ty}%`);
    }
  }
  
  // 综合（上下半场合并按进球率分）
  const all = preds.filter(p => p.verified);
  if (all.length > 0) {
    console.log('\n📋 综合按进球率:');
    const g2 = {};
    all.forEach(p => {
      const isHT = p.matchId.endsWith('_HT');
      const k = p.h2hRate >= 100 ? '100%' : p.h2hRate >= 90 ? '90%' : '80-89%';
      if (!g2[k]) g2[k] = { t: 0, h: 0 };
      g2[k].t++;
      if (isHT && p.htHasGoal) g2[k].h++;
      else if (!isHT && p.ftHasGoal) g2[k].h++;
    });
    let th = 0, tt = 0;
    for (const k of ['100%', '90%', '80-89%']) {
      const g = g2[k];
      if (!g || g.t === 0) continue;
      const rate = (g.h / g.t * 100).toFixed(1) + '%';
      console.log(`  ${k.padEnd(8)} ${g.h}/${g.t}  命中率${rate}`);
      th += g.h; tt += g.t;
    }
    if (tt > 0) {
      console.log(`  ────────────────────────────`);
      console.log(`  总计    ${th}/${tt}  命中率${(th/tt*100).toFixed(1)}%`);
    }
  }
}

main().catch(e => {
  console.error('\n❌ 错误:', e.message);
  process.exit(1);
});
