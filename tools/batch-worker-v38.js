#!/usr/bin/env node
/**
 * V33 批次工作器 - 由主进程fork调用，处理一批比赛后自动退出释放内存
 * 用法: node jiebao-scraper-v33.js --worker <batchIndex> <matchCount> <jsonFile>
 */
const { chromium } = require('playwright');
const fs = require('fs');

const args = process.argv.slice(2);
if (args[0] !== '--worker') {
  console.error('此文件为工作器，请通过主入口运行');
  process.exit(1);
}

const BATCH_INDEX = parseInt(args[1]);
const TOTAL_MATCHES = parseInt(args[2]);
const DATA_FILE = args[3]; // 比赛列表JSON

const CFG = require('./v38-config.js');

const FRIENDLY_KEYWORDS = [
  '友谊赛', '友谊', '热身赛', '热身', 'Friendly',
  '俱乐部友谊', '国际友谊', '球会友谊', '球會友誼'
];

function isLeagueAllowed(league) {
  if (!league) return false;
  const clean = league.replace(/[^\u4e00-\u9fa5a-zA-Z0-9]/g, '');
  return CFG.leagues.some(allowed => clean.startsWith(allowed));
}

const RETRY_ONCE = true;

const path = require('path');
const verifyDir = path.resolve(__dirname, '../data/验证存档/v38');
const rawFile = '/tmp/jiebao-raw-v33.json';

const isFriendly = t => FRIENDLY_KEYWORDS.some(k => t.toLowerCase().includes(k.toLowerCase()));

function normalizeOdds(val) {
  if (!val || val === '-') return null;
  const s = String(val).trim();
  if (s.includes('/')) {
    const p = s.split('/');
    return (parseFloat(p[0]) + parseFloat(p[1])) / 2;
  }
  return parseFloat(s);
}

function analyzeOdds(odds) {
  const init = normalizeOdds(odds?.init);
  const cur = normalizeOdds(odds?.cur);
  if (init === null || cur === null) return { positive: false, negative: false, direction: 'unknown', detail: '无盘口数据' };
  const diff = cur - init;
  if (Math.abs(diff) < 0.01) return { positive: false, negative: false, direction: 'flat', detail: `盘口不变(${init})` };
  if (diff > 0) return { positive: true, negative: false, direction: 'up', detail: `升盘: ${init}→${cur} (+${diff.toFixed(2)})` };
  return { positive: false, negative: true, direction: 'down', detail: `降盘: ${init}→${cur} (${diff.toFixed(2)})` };
}

function buyTiming(oddsSignal, oddsCur, oddsWater) {
  const cur = normalizeOdds(oddsCur);
  const { directThreshold, highThreshold, cautionThreshold } = CFG.buyTiming;
  if (cur === null) return { timing: '无盘口', detail: '' };

  // 0.75盘口+高水陷阱：半场0.75盘且上盘水>1.90→诱盘跳过
  if (Math.abs(cur - 0.75) < 0.05 && oddsWater?.cur && oddsWater.cur > 1.90) {
    return { timing: '⚠️跳过', detail: `0.75高水陷阱(水位${oddsWater.cur})` };
  }

  if (oddsSignal.direction === 'down') {
    if (cur <= cautionThreshold) return { timing: '⚠️谨慎', detail: `降盘至${cur}，盘口过低` };
    // 区分真/假降盘：水位判断
    if (oddsWater?.init && oddsWater?.cur && oddsWater.cur < oddsWater.init) {
      return { timing: '✅直接投', detail: `降水降盘至${cur}，真信号` };
    }
    return { timing: '⚠️跳过', detail: `升水降盘至${cur}，诱盘` };
  }
  if (oddsSignal.direction === 'up') {
    if (cur <= directThreshold) return { timing: '✅尽快买入', detail: `升盘至${cur}，机构看好` };
    return { timing: '⏳尝试', detail: `升盘至${cur}，数据够硬可接受` };
  }
  if (cur <= directThreshold) return { timing: '✅直接投', detail: `盘口${cur}适中` };
  if (cur >= highThreshold) return { timing: '⏳尝试', detail: `盘口${cur}偏高，数据够硬可接受` };
  if (cur <= cautionThreshold) return { timing: '⚠️谨慎', detail: `盘口${cur}过低` };
  return { timing: '✅直接投', detail: `盘口${cur}适中` };
}

/** 初盘与历史匹配度分析 */
function oddsDataFit(oddsInit, h2hWeightedAvg) {
  const init = normalizeOdds(oddsInit);
  if (init === null || h2hWeightedAvg === null) return { fit: 'unknown', detail: '无足够数据' };
  const diff = h2hWeightedAvg - init;
  if (Math.abs(diff) < 0.1) return { fit: 'matched', detail: `初盘${init}匹配历史场均${h2hWeightedAvg} ✅`, score: 0 };
  if (diff > 0) {
    // 历史场均 > 初盘 → 初盘偏低，机构可能保护大球方向
    const strength = diff > 0.3 ? '明显' : '轻微';
    return { fit: 'under_value', detail: `初盘${init}<历史${h2hWeightedAvg}(${strength})，大球可能被低估`, score: diff > 0.3 ? 1 : 0.5 };
  }
  // 历史场均 < 初盘 → 初盘偏高，可能造热大球
  const strength = diff < -0.3 ? '明显' : '轻微';
  return { fit: 'over_protect', detail: `初盘${init}>历史${h2hWeightedAvg}(${strength})，大球可能造热`, score: diff < -0.3 ? -1 : -0.5 };
}

function analyzeRecentSignal(recent) {
  if (!recent || !recent.home || !recent.away) return 'unknown';
  const hr = recent.home.rate;
  const ar = recent.away.rate;
  if (hr === null || ar === null) return 'unknown';
  const avg = (hr + ar) / 2;
  if (avg >= 70) return 'positive';
  if (avg <= 50) return 'negative';
  return 'neutral';
}

function extractH2H(text) {
  const s = text.includes('對戰往績') ? text.indexOf('對戰往績') : text.indexOf('对战往绩');
  const e = text.includes('近期戰績') ? text.indexOf('近期戰績') : text.indexOf('近期战绩');
  if (s === -1 || e === -1) return null;
  const valid = [];
  for (const line of text.substring(s, e).split('\n')) {
    const m = line.match(/\((\d+)-(\d+)\)/);
    if (!m) continue;
    const ht = parseInt(m[1]) + parseInt(m[2]);
    const p = line.split('\t').filter(x => x.trim());
    const type = p[0] || '';
    const yrMatch = (p[1] || '').match(/(\d{4})/i);
    const yr = yrMatch ? parseInt(yrMatch[1]) : 0;
    if (isFriendly(type) || (yr && yr < 2020)) continue;
    valid.push({ ht, isZeroZero: ht === 0 });
  }
  if (!valid.length) return null;
  // 按时间排序：页面自上而下为最新→最旧
  const top = valid.slice(0, 10);
  let totalG = 0, hasGoal = 0, zeroCount = 0;
  // 加权计算：近3场×1.5，早于3场×0.7
  let wTotal = 0, wHas = 0, wCount = 0;
  top.forEach((m, i) => {
    const w = i < 3 ? 1.5 : 0.7;
    wTotal += m.ht * w;
    wHas += (m.ht > 0 ? 1 : 0) * w;
    wCount += w;
    // 同时计算旧的纯数值（用于部分判断）
    totalG += m.ht;
    if (m.ht > 0) hasGoal++;
    if (m.isZeroZero) zeroCount++;
  });
  // 最近2次交锋检测
  const recentTwo = valid.slice(0, Math.min(2, valid.length));
  const recentTwoZeroZero = recentTwo.length >= 2 && recentTwo.every(m => m.isZeroZero);
  const recentTwoAllGoal = recentTwo.length >= 2 && recentTwo.every(m => m.ht > 0);

  return {
    avg: +(totalG / top.length).toFixed(2),
    weightedAvg: +(wTotal / wCount).toFixed(2),
    rate: Math.round(hasGoal / top.length * 100),
    weightedRate: Math.round(wHas / wCount * 100),
    count: top.length, zeroZeroCount: zeroCount,
    recentTwoZeroZero, recentTwoAllGoal
  };
}

function extractRecent(text) {
  const s = text.indexOf('近期戰績');
  const e = text.indexOf('數據對比');
  if (s === -1 || e === -1) return null;
  const section = text.substring(s, e).split('\n');
  // 找到两队的分界：第一队的总结行（近10场胜率...）后即为第二队
  let splitIdx = -1;
  for (let i = 1; i < section.length; i++) {
    if (section[i].includes('近10场') && section[i].includes('胜率')) {
      splitIdx = i + 1;
      break;
    }
  }
  function parseTeam(lines) {
    const valid = [];
    for (const line of lines) {
      const m = line.match(/\((\d+)-(\d+)\)/);
      if (!m) continue;
      const type = (line.split('\t').filter(x => x.trim())[0] || '');
      if (isFriendly(type)) continue;
      valid.push({ ht: parseInt(m[1]) + parseInt(m[2]) });
    }
    return valid;
  }
  const teamA = parseTeam(splitIdx > 0 ? section.slice(0, splitIdx) : []);
  const teamB = parseTeam(splitIdx > 0 ? section.slice(splitIdx) : []);
  if (teamA.length < 2 && teamB.length < 2) return null;
  // 如果某队没分到数据，用原逻辑（各一半）
  if (teamA.length < 2 && teamB.length >= 2) {
    const all = [...teamA, ...teamB];
    const half = Math.ceil(all.length / 2);
    return { home: calc(all.slice(0, half)), away: calc(all.slice(half)) };
  }
  function calc(a) {
    if (!a.length) return { avg: null, rate: null, streak: null, streak3: null };
    let g = 0, hg = 0;
    a.forEach(x => { g += x.ht; if (x.ht > 0) hg++; });
    function hasConsecutive(matches, num) {
      if (matches.length < num) return null;
      const recent = matches.slice(0, num);
      const allGood = recent.every(m => m.ht > 0);
      const rate = recent.filter(m => m.ht > 0).length / recent.length;
      if (allGood) return '🔥连胜';
      if (rate >= 0.8) return '✅高率';
      if (rate <= 0.3) return '⚠️低率';
      return 'normal';
    }
    return {
      avg: +(g / a.length).toFixed(2),
      rate: Math.round(hg / a.length * 100),
      streak: hasConsecutive(a, 3),
      streak3: hasConsecutive(a, 5)
    };
  }
  return { home: calc(teamA), away: calc(teamB) };
}

/** 提取裁判名（从analysis页面顶部信息区），找不到返回null */
function extractReferee(text) {
  // 捷报裁判信息通常在页面顶部信息行，格式如："裁判: 张三" 或 "裁判：张三"
  const m = text.match(/裁判[：:]\s*([\u4e00-\u9fa5a-zA-Z]+)/);
  return m ? m[1] : null;
}

// 从 Crown全指数 区解析半场大小球盘口（无需点击按钮）
// 从Crown全指数区一次提取：半场大小球、全场让球盘、胜平负赔率、水位
// 格式：半场|主胜|和|客胜|让球上盘|让球盘口|让球下盘|大小大球水|大小球盘口|大小小球水
// 格式：全场|主胜|和|客胜|让球上盘|让球盘口|让球下盘|大小大球水|大小球盘口|大小小球水
function extractCrownOdds(text) {
  const lines = text.split('\n');
  let htLine = null, ftLine = null;
  let inCrown = false;
  for (const line of lines) {
    const t = line.trim();
    if (t.includes('全指数')) { inCrown = true; continue; }
    if (!inCrown) continue;
    if (t.startsWith('半场\t') || t.startsWith('半　场\t')) { htLine = line; }
    if (t.startsWith('全场\t') || t.startsWith('全　场\t')) { ftLine = line; }
    if (htLine && ftLine) break;
  }

  // 解析一行数据：parts索引 0=标签,1=主胜,2=和,3=客胜,4=让球上盘水位,5=让球盘口,6=让球下盘水位,7=大小大球水,8=大小球盘口,9=大小小球水
  function parseLine(line) {
    if (!line) return null;
    const parts = line.split('\t').filter(x => x.trim());
    if (parts.length < 9) return null;
    const goalLine = parts[8];
    const hcpLine = parts[5];
    let goalVal = null, hcpVal = null;
    if (goalLine && goalLine !== '-') {
      if (goalLine.includes('/')) { const p = goalLine.split('/'); goalVal = (parseFloat(p[0]) + parseFloat(p[1])) / 2; }
      else { goalVal = parseFloat(goalLine); }
    }
    if (hcpLine && hcpLine !== '-') {
      if (hcpLine.includes('/')) { const p = hcpLine.split('/'); hcpVal = (parseFloat(p[0]) + parseFloat(p[1])) / 2; }
      else { hcpVal = parseFloat(hcpLine); }
    }
    return {
      goal: (goalVal !== null && !isNaN(goalVal)) ? { init: goalVal, cur: goalVal } : null,
      handicap: (hcpVal !== null && !isNaN(hcpVal)) ? { init: hcpVal, cur: hcpVal } : null,
      hcpWater: { init: parseFloat(parts[4]) || null, cur: parseFloat(parts[6]) || null },
      goalWater: { init: parseFloat(parts[7]) || null, cur: parseFloat(parts[9]) || null }
    };
  }

  const ht = parseLine(htLine);
  const ft = parseLine(ftLine);
  return {
    htGoal: ht?.goal || null,            // 半场大小球盘口
    htHandicap: ht?.handicap || null,     // 半场让球盘口
    htWater: ht?.hcpWater || null,        // 半场水位
    ftGoal: ft?.goal || null,             // 全场大小球盘口
    ftHandicap: ft?.handicap || null,     // 全场让球盘口（AH核心数据）
    ftWater: ft?.hcpWater || null         // 全场水位
  };
}

function smartRecommend(h2h, recent, odds, teamStats) {
  if (!h2h || h2h.count < CFG.filters.h2hMinCount) return { pass: false, reason: `H2H仅${h2h?.count || 0}场 (需≥${CFG.filters.h2hMinCount})` };
  if (h2h.rate < CFG.filters.h2hMinRate) return { pass: false, reason: `进球率${h2h.rate}% < ${CFG.filters.h2hMinRate}%` };
  if (h2h.zeroZeroCount > CFG.filters.h2hMaxZeroZero) return { pass: false, reason: `${h2h.zeroZeroCount}场0-0 > ${CFG.filters.h2hMaxZeroZero}场` };
  if (!odds) return { pass: false, reason: '无半场盘口数据' };

  // 近2次H2H验证：最近2次交锋都0-0→直接跳过
  if (h2h.recentTwoZeroZero) {
    return { pass: false, reason: '近2次交锋均0-0，近期战术转保守' };
  }

  const oddsSig = analyzeOdds(odds?.htGoal);
  const recentSig = analyzeRecentSignal(recent);
  const timing = buyTiming(oddsSig, odds?.htGoal?.cur, odds?.htWater);

  // ===== 团队数据（提取到前面，供TDZ安全使用） =====
  const homeHAvg = teamStats?.dist?.home?.avg || 0;
  const awayHAvg = teamStats?.dist?.away?.avg || 0;
  const teamAvgMax = Math.max(homeHAvg, awayHAvg);
  const homeConc = teamStats?.time?.home?.conc || 0;
  const awayConc = teamStats?.time?.away?.conc || 0;
  const teamAvgNote = (homeHAvg || awayHAvg) ? `团队HT场均${homeHAvg}/${awayHAvg}` : '';
  const teamBonus = teamAvgMax >= 0.8 ? 0.5 : (homeHAvg || awayHAvg) ? -0.3 : 0;
  const lateBias = homeConc >= 50 || awayConc >= 50 ? 0.3 : 0;

  // 盘口≥1.5 → 用团队数据判断
  if (timing.timing === '⏳尝试') {
    const oddsVal = normalizeOdds(odds?.htGoal?.cur);
    const h2hStrong = h2h.rate === 100 && h2h.count >= 6;
    const h2hAvgOk = (h2h.weightedAvg || h2h.avg) >= 1.5;
    const accept = h2hStrong || (h2hAvgOk && (teamAvgMax >= 0.8 || lateBias >= 0.3));
    if (!accept) {
      return { pass: false, reason: `盘口${oddsVal}偏高(H2H${h2h.rate}%/${h2h.weightedAvg} 团队${homeHAvg}/${awayHAvg})，跳过` };
    }
    timing.timing = '✅直接投';
    timing.detail = `盘口${oddsVal}偏高但数据够硬(H2H${h2h.rate}%/${h2h.weightedAvg} 团队${homeHAvg}/${awayHAvg})，接受`;
  }

  const is100 = h2h.rate === 100;
  const avgG = h2h.weightedAvg || h2h.avg;
  const hc = h2h.count;

  // ===== 初盘匹配度 =====
  const fit = oddsDataFit(odds?.htGoal?.init, h2h.weightedAvg);

  // ===== 近期连续趋势 =====
  const homeStreak = recent?.home?.streak || 'normal';
  const awayStreak = recent?.away?.streak || 'normal';
  const hasHotStreak = homeStreak === '🔥连胜' || awayStreak === '🔥连胜';
  const hasColdStreak = homeStreak === '❌连冷' && awayStreak === '❌连冷';
  const streakNote = hasHotStreak ? '🔥近期连续进球' : hasColdStreak ? '❌近期连场闷平' : '';

  const zzWarn = h2h.zeroZeroCount === 0 ? '🟢' : h2h.zeroZeroCount === 1 ? '🟡' : '🔴';
  const conf = hc >= 8 ? '📊高信度' : hc >= 6 ? '📊中信度' : '📊样本偏少';
  const recentNote = recentSig === 'positive' ? '近期两队进球活跃 ✅' : recentSig === 'negative' ? '近期两队状态偏闷 ⚠️' : '';

  // ===== 综合加分 =====
  const streakBonus = hasHotStreak ? 1 : hasColdStreak ? -1 : 0;
  const fitBonus = fit.score || 0;
  let totalBonus = streakBonus + fitBonus + teamBonus + lateBias;

  // 近2次H2H反向利用：最近2场半场都有进球→加分
  if (h2h.recentTwoAllGoal) totalBonus += 0.5;

  // 共振系数：80-89%档评估近期vs历史的一致性
  if (!is100) {
    const homeRt = recent?.home?.rate;
    const awayRt = recent?.away?.rate;
    if (homeRt !== null && homeRt !== undefined && awayRt !== null && awayRt !== undefined && h2h.rate > 0) {
      const avgRecentRate = (homeRt + awayRt) / 2;
      const ratio = avgRecentRate / h2h.rate;
      if (ratio >= 1.0) totalBonus += 1;
      else if (ratio < 0.6) {
        return { pass: false, reason: `共振系数${ratio.toFixed(2)}过低(近期${avgRecentRate.toFixed(0)}%/历史${h2h.rate}%)` };
      }
    }
  }

  // 全场让球绝对值：全场让球≥1.5→实力悬殊→利好半场大球
  if (odds?.ftHandicap) {
    const ftHcpAbs = Math.abs(odds.ftHandicap.cur);
    if (ftHcpAbs >= 1.5) totalBonus += 0.5;
    else if (ftHcpAbs <= 0.25 && !is100) {
      // 势均力敌→上半场试探→不利半场大球，但100%档给机会
      if (h2h.rate < 90) {
        return { pass: false, reason: `全场让球${odds.ftHandicap.cur}，势均力敌不利半场大球` };
      }
    }
  }

  // ===== 等待建议：1-10'安全→可等降盘 =====
  if (timing.timing === '✅直接投' || timing.timing === '✅尽快买入') {
    const hRaw = teamStats?.time?.home?.raw;
    const aRaw = teamStats?.time?.away?.raw;
    if (hRaw && aRaw && hRaw.length >= 5 && aRaw.length >= 5) {
      const hTotal = hRaw.reduce((a,b) => a+b, 0);
      const aTotal = aRaw.reduce((a,b) => a+b, 0);
      if (hTotal > 0 && aTotal > 0) {
        const hPct1 = hRaw[0] / hTotal * 100;
        const aPct1 = aRaw[0] / aTotal * 100;
        if (hPct1 < 10 && aPct1 < 10) {
          timing.timing = '⏳等10分钟';
          timing.detail = timing.detail + ' | 1-10分无球可等降盘';
        }
      }
    }
  }

  if (is100) {
    if (hc >= 6) {
      if (avgG >= 1.2) {
        let level = '🔥推荐';
        let action = '推荐';
        if (totalBonus >= 1 && recentSig === 'positive') {
          level = '🔥🔥强烈推荐';
          action = '强烈推荐';
        }
        let adviceParts = [`100%进球率(H2H=${hc})`];
        if (avgG > 1) adviceParts.push(`场均${avgG}球`);
        if (recentSig === 'positive') adviceParts.push('近期状态好');
        if (hasHotStreak) adviceParts.push(streakNote);
        if (fit.fit !== 'matched' && fit.fit !== 'unknown') adviceParts.push(fit.detail);
        return { pass: true, level, action, advice: adviceParts.join(' + '), oddsSig, timing, recentSig, zzWarn, conf, is100, recentNote, streakNote, fit };
      }
      return { pass: true, level: recentSig === 'negative' ? '⚠️谨慎' : '✅推荐', action: '推荐', advice: `100%进球率但场均仅${avgG}球${recentSig === 'negative' ? '+近期状态差→谨慎' : ''}`, oddsSig, timing, recentSig, zzWarn, conf, is100, recentNote, streakNote, fit };
    }
    return { pass: true, level: '⚡推荐(样本小)', action: '推荐', advice: `100%进球率但H2H仅${hc}场，建议减注`, oddsSig, timing, recentSig, zzWarn, conf, is100, recentNote, streakNote, fit };
  }

  const h2hStrong = hc >= 8;
  const avgOk = avgG >= CFG.grading.rate80_89.avgLine;
  const avgWeakOk = avgG >= 1.5 && h2hStrong;

  if (avgOk || avgWeakOk) {
    let level = '✅推荐';
    let action = '推荐';
    let adviceParts = [`进球率${h2h.rate}%`];
    if (avgG > 0) adviceParts.push(`场均${avgG}球`);
    if (recentSig === 'positive') {
      adviceParts.push('近期状态好');
    }
    if (hasHotStreak) {
      adviceParts.push(streakNote);
      level = '🔥推荐';
    }
    if (fit.fit !== 'matched' && fit.fit !== 'unknown') adviceParts.push(fit.detail);
    if (recentSig === 'negative') {
      level = '⚠️谨慎';
      action = '谨慎';
      adviceParts.push('近期状态差');
    }
    // 趋势加分提升等级
    if (totalBonus >= 1 && level === '✅推荐') level = '🔥推荐';
    if (totalBonus <= -1 && level !== '⚠️谨慎') { level = '⚠️谨慎'; action = '谨慎'; }
    return { pass: true, level, action, advice: adviceParts.join(' + '), oddsSig, timing, recentSig, zzWarn, conf, is100: false, recentNote, streakNote, fit };
  }

  return { pass: false, reason: `进球率${h2h.rate}%但场均仅${avgG}球 (V33:需≥1.8或H2H≥8且≥1.5)` };
}

/**
 * 从页面底部提取：入球分布（上半场场均）
 * 格式: 总  2 9 12 6 2  35 24 (末两位=上半场/下半场球数)
 */
function parseGoalDist(text) {
  const s = text.indexOf('入球分布');
  if (s < 0) return null;
  const block = text.substring(s, s + 600);
  const res = [], tmp = [];
  for (const line of block.split('\n')) {
    const l = line.trim();
    if (!l.startsWith('總') && !l.startsWith('总')) continue;
    const nums = l.split(/\s+/).filter(x => /^\d+$/.test(x));
    if (nums.length < 7) continue;
    const mc = nums.slice(0,5).reduce((a,b)=>a+parseInt(b), 0);
    const ht = parseInt(nums[nums.length-2]);
    tmp.push({ matches: mc, htGoals: ht, avg: mc>0 ? +(ht/mc).toFixed(2) : 0 });
    if (tmp.length >= 2) { res.push(tmp[0], tmp[1]); tmp.length = 0; }
  }
  return res.length >= 2 ? { home: res[0], away: res[1] } : null;
}

/**
 * 从页面底部提取：入球时间（上半场集中度）
 * 格式: 总  3 12 5 10 5（前5=上半场时间段）
 * 返回含原始分段数据用于等待建议
 */
function parseGoalTimes(text) {
  const s = text.indexOf('入球\u6642\u9593');
  if (s < 0) return null;
  const block = text.substring(s, s + 600);
  const res = [], tmp = [];
  for (const line of block.split('\n')) {
    const l = line.trim();
    if (!l.startsWith('總') && !l.startsWith('总')) continue;
    const nums = l.split(/\s+/).filter(x => /^\d+$/.test(x));
    if (nums.length < 10) continue;
    const raw = nums.slice(0,5).map(x => parseInt(x)); // [1-10, 11-20, 21-30, 31-40, 41-45]
    const total = raw.reduce((a,b) => a+b, 0);
    const pct = raw.map(x => total > 0 ? +(x/total*100).toFixed(0) : 0);
    const early = raw[0]+raw[1]+raw[2], late = raw[3]+raw[4];
    tmp.push({ raw, pct, early, late, total, conc: total>0 ? +(late/total*100).toFixed(0) : 0 });
    if (tmp.length >= 2) { res.push(tmp[0], tmp[1]); tmp.length = 0; }
  }
  return res.length >= 2 ? { home: res[0], away: res[1] } : null;
}

/**
 * 从页面底部提取：大小球率
 * 格式: 總	13(41.9%)	15(48.4%)...
 */
function parseOddsStats(text) {
  const s = text.indexOf('大小/單雙');
  if (s < 0) return null;
  const rates = [];
  for (const line of text.substring(s, s+400).split('\n').filter(l => l.includes('%'))) {
    const m = line.match(/大(\d+)\(([\d.]+)%\)/);
    if (m) rates.push({ over: parseInt(m[1]), overRate: parseFloat(m[2]) });
  }
  return rates.length >= 2 ? { home: rates[0], away: rates[1] } : null;
}

function addPrediction(match, h2h, recent, odds, result) {
  try {
    if (!fs.existsSync(verifyDir)) fs.mkdirSync(verifyDir, { recursive: true });
    const dbFile = verifyDir + '/predictions.json';
    let db = { version: 'v38', predictions: [] };
    try { db = JSON.parse(fs.readFileSync(dbFile, 'utf8')); } catch (e) {}
    const today = new Date().toISOString().split('T')[0];
    const matchId = match.league + '__' + match.home + '_vs_' + match.away + '__' + match.time;
    if (db.predictions.some(p => p.matchId === matchId && !p.verified)) return;
    db.predictions.push({
      date: today, matchId: matchId,
      league: match.league, time: match.time, home: match.home, away: match.away,
      h2hRate: h2h.rate, h2hAvg: h2h.avg, h2hWeightedAvg: h2h.weightedAvg,
      h2hCount: h2h.count, h2hZeroCount: h2h.zeroZeroCount,
      oddsInit: odds?.init || null, oddsCur: odds?.cur || null,
      oddsSignal: result.oddsSig?.direction || 'unknown',
      homeRecentRate: recent?.home?.rate || null, awayRecentRate: recent?.away?.rate || null,
      homeStreak: recent?.home?.streak || null, awayStreak: recent?.away?.streak || null,
      oddsFit: result.fit?.fit || null, oddsFitDetail: result.fit?.detail || null,
      level: result.level, advice: result.advice,
      buyTiming: result.timing?.timing || '', buyDetail: result.timing?.detail || '',
      verified: false, htScore: null, htHasGoal: null
    });
    fs.writeFileSync(dbFile, JSON.stringify(db, null, 2));
  } catch (e) { process.stderr.write("ERR save: " + (e.message||"").substring(0,80) + "\n"); }
}

/** 动态等待：页面中出现匹配文本，最多等maxMs毫秒 */
async function waitForVisible(page, check, maxMs = 4000, checkMs = 150) {
  const start = Date.now();
  while (Date.now() - start < maxMs) {
    try {
      const ok = typeof check === 'function'
        ? await page.evaluate(check)
        : await page.evaluate((t) => document.body.innerText.includes(t), check);
      if (ok) return true;
    } catch (e) {}
    await new Promise(r => setTimeout(r, checkMs));
  }
  return false;
}

async function processMatch(page, m) {
  try {
    // 直接打开 analysis 页面（不是 panlu，panlu没有全指数区）
    const ctx = page.context();
    const np = await ctx.newPage();
    await np.goto('https://live.nowscore.com/analysis/' + (m.id || '') + '.html', { waitUntil: 'domcontentloaded', timeout: 15000 }).catch(()=>{});
    await waitForVisible(np, '對戰往績', 10000);
    await new Promise(r => setTimeout(r, 800));

    // 从 analysis 页面提取所有数据
    // 注意：「指数三合一」按钮现在会404，所以不能点
    // 数据来源：页面初始加载已包含全部内容
    const dt = await np.evaluate(() => document.body.innerText);
    const odds = extractCrownOdds(dt);
    const h2h = extractH2H(dt);
    const recent = extractRecent(dt);
    const teamDist = parseGoalDist(dt);
    const teamTime = parseGoalTimes(dt);
    const teamOdds = parseOddsStats(dt);
    const teamStats = { dist: teamDist, time: teamTime, odds: teamOdds };
    const referee = extractReferee(dt);
    const result = smartRecommend(h2h, recent, odds, teamStats);
    try { await np.close(); } catch (e) {}

    if (!result.pass) { process.stdout.write(`${result.reason}\n`); return null; }
    const ha = teamStats?.dist?.home?.avg, aa = teamStats?.dist?.away?.avg;
    const hc = teamStats?.time?.home?.conc, ac = teamStats?.time?.away?.conc;
    const hd = teamStats?.odds?.home?.overRate, ad = teamStats?.odds?.away?.overRate;
    const distInfo = (ha||aa) ? ` 团队${ha||'?'}/${aa||'?'}` : '';
    addPrediction(m, h2h, recent, odds, result);
    process.stdout.write(`✅ ${h2h.rate}% 场均${h2h.avg} ${h2h.count}场${distInfo}\n`);

    return {
      league: m.league, time: m.time, home: m.home, away: m.away,
      h2hRate: h2h.rate, h2hAvg: h2h.avg, h2hCount: h2h.count,
      h2hWeightedAvg: h2h.weightedAvg, h2hZeroCount: h2h.zeroZeroCount,
      oddsInit: odds?.htGoal?.init || null, oddsCur: odds?.htGoal?.cur || null,
      oddsSignal: result.oddsSig?.direction || null,
      oddsSignalDetail: result.oddsSig?.detail || '',
      homeRate: recent?.home?.rate || null, homeAvg: recent?.home?.avg || null,
      awayRate: recent?.away?.rate || null, awayAvg: recent?.away?.avg || null,
      recentSignal: result.recentSig || null,
      predGoals: h2h.weightedAvg || h2h.avg,
      homeStreak: recent?.home?.streak || null, awayStreak: recent?.away?.streak || null,
      streakNote: result?.streakNote || '',
      advice: result.advice, level: result.level,
      action: result.action || '推荐',
      zzWarn: result.zzWarn,
      confidence: result.conf,
      buyTiming: result.timing?.timing || '',
      buyDetail: result.timing?.detail || '',
      teamHomeHAvg: ha, teamAwayHAvg: aa,
      teamHomeConc: hc, teamAwayConc: ac,
      teamHomeTimeRaw: teamStats?.time?.home?.raw || null, teamAwayTimeRaw: teamStats?.time?.away?.raw || null,
      teamHomeOverRate: hd, teamAwayOverRate: ad,
      // AH记录（不用于实盘决策，只积累数据）
      ftHandicapInit: odds?.ftHandicap?.init || null,
      ftHandicapCur: odds?.ftHandicap?.cur || null,
      ftHandicapResult: null,  // 验证时回填
      referee: referee
    };
  } catch (e) {
    process.stderr.write("ERR return: " + (e.message||"").substring(0,80) + "\n");
  }
}

async function main() {
  const matches = JSON.parse(fs.readFileSync(DATA_FILE, 'utf8'));
  console.log(`\n${'='.repeat(50)}`);
  console.log(`  工作器 #${BATCH_INDEX} (${matches.length}场)`);
  console.log(`${'='.repeat(50)}`);

  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await ctx.newPage();
  await page.goto('https://live.nowscore.com/2in1.aspx', { waitUntil: 'domcontentloaded', timeout: 25000 });
  // 页面加载等待（等 table_live 出现）
  try {
    const loadStart = Date.now();
    while (Date.now() - loadStart < 5000) {
      const ok = await page.evaluate(() => { const t = document.getElementById('table_live'); return t && t.rows.length > 3; });
      if (ok) break;
      await new Promise(r => setTimeout(r, 200));
    }
  } catch (e) {}

  const results = [];
  for (let i = 0; i < matches.length; i++) {
    const m = matches[i];
    const globalIdx = BATCH_INDEX * matches.length + i + 1;
    process.stdout.write(`[${globalIdx}/${TOTAL_MATCHES}] ${m.league} ${m.home} vs ${m.away}... `);
    if (!m.id) { process.stdout.write(`无matchId\n`); continue; }
    const r = await processMatch(page, m);
    if (r) results.push(r);
    if ((i + 1) % 10 === 0) process.stdout.write(`[进度 ${globalIdx}/${TOTAL_MATCHES}]\n`);
  }

  await browser.close();
  console.log(`\n工作器 #${BATCH_INDEX} 完成 → ${results.length}场推荐\n`);

  // 输出结果到stdout JSON格式
  console.log(JSON.stringify({ batchIndex: BATCH_INDEX, results }));
}

main().catch(e => { console.error('Worker fatal:', e.message); process.exit(1); });
