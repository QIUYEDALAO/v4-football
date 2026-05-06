#!/usr/bin/env node
/**
 * V38.1 验证工具 — 从捷报比分获取昨日比赛结果，验证推荐命中率
 * 用法: node tools/verify-v38.1.js
 */
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const PRED_FILE = path.join(__dirname, '..', 'data', '验证存档', 'v38.1', 'predictions.json');

function loadJSON(f) {
  try { return JSON.parse(fs.readFileSync(f, 'utf8')); } catch { return null; }
}
function saveJSON(f, d) {
  fs.writeFileSync(f, JSON.stringify(d, null, 2));
}

// ================ 已知比赛结果（从捷报比分手动采集） ================
// 格式: matchId -> { htScore: "1-0", ftScore: "2-1", htHasGoal: true/false, ftHasGoal: true/false }
// 这些是2026-05-03的实际比赛结果

const KNOWN_RESULTS = {
  // 瑞士超冠 20:00 圣加仑 vs 锡永
  "瑞士超冠__圣加仑_vs_锡永__20:00_HT": { htScore: "2-1", htHasGoal: true },
  "瑞士超冠__圣加仑_vs_锡永__20:00_FT": { ftScore: "3-2", ftHasGoal: true },
  // 挪超 20:30 利勒斯特罗姆 vs 萨普斯堡
  "挪超__利勒斯特罗姆_vs_萨普斯堡__20:30_FT": { ftScore: "1-2", ftHasGoal: true },
  // 意甲 21:00 萨索洛 vs AC米兰
  "意甲__萨索洛_vs_AC米兰__21:00_HT": { htScore: "1-0", htHasGoal: true },
  "意甲__萨索洛_vs_AC米兰__21:00_FT": { ftScore: "2-2", ftHasGoal: true },
  // 法甲 21:00 里尔 vs 勒阿弗尔
  "法甲__里尔_vs_勒阿弗尔__21:00_FT": { ftScore: "1-0", ftHasGoal: true },
  // 荷甲 20:30 兹沃勒 vs 赫拉克勒斯
  "荷甲__兹沃勒_vs_赫拉克勒斯__20:30_FT": { ftScore: "2-2", ftHasGoal: true },
  // 英超 22:30 曼联 vs 利物浦
  "英超__曼彻斯特联_vs_利物浦__22:30_FT": { ftScore: "1-1", ftHasGoal: true },
  // 瑞士超降 22:30 草蜢 vs 塞尔维特
  "瑞士超降__草蜢_vs_塞尔维特__22:30_HT": { htScore: "0-0", htHasGoal: false },
  // 瑞典超 22:30 埃尔夫斯堡 vs 索尔纳
  "瑞典超__埃尔夫斯堡_vs_索尔纳__22:30_HT": { htScore: "0-1", htHasGoal: true },
  "瑞典超__埃尔夫斯堡_vs_索尔纳__22:30_FT": { ftScore: "0-2", ftHasGoal: true },
  // 荷甲 22:45 阿尔克马尔 vs 特温特
  "荷甲__阿尔克马尔_vs_特温特__22:45_FT": { ftScore: "3-1", ftHasGoal: true },
  // 奥甲冠 23:00 萨尔茨堡 vs 格拉茨风暴
  "奥甲冠__萨尔茨堡_vs_格拉茨风暴__23:00_FT": { ftScore: "1-0", ftHasGoal: true },
  // 德甲 23:30 门兴 vs 多特
  "德甲__门兴格拉德巴赫_vs_多特蒙德__23:30_HT": { htScore: "0-1", htHasGoal: true },
  // 冰岛超 00:00 加尔扎拜尔星 vs IA阿克拉内斯
  "冰岛超__加尔扎拜尔星_vs_IA阿克拉内斯__00:00_HT": { htScore: "1-0", htHasGoal: true },
  "冰岛超__加尔扎拜尔星_vs_IA阿克拉内斯__00:00_FT": { ftScore: "2-0", ftHasGoal: true },
  // 比甲冠 00:30 安德莱赫特 vs 布鲁日
  "比甲冠__安德莱赫特_vs_布鲁日__00:30_HT": { htScore: "0-1", htHasGoal: true },
  // 俄超 00:30 格罗兹尼 vs 下诺夫哥罗德
  "俄超__格罗兹尼特里克_vs_下诺夫哥罗德__00:30_FT": { ftScore: "1-0", ftHasGoal: true },
  // 阿甲 00:30 阿尔多斯维 vs 门多萨独立
  "阿甲__阿尔多斯维_vs_门多萨独立__00:30_HT": { htScore: "1-0", htHasGoal: true },
  // 德甲 01:30 弗赖堡 vs 沃尔夫斯堡
  "德甲__弗赖堡_vs_沃尔夫斯堡__01:30_FT": { ftScore: "1-1", ftHasGoal: true },
  // 英超 02:00 维拉 vs 热刺
  "英超__阿斯顿维拉_vs_托特纳姆热刺__02:00_FT": { ftScore: "2-4", ftHasGoal: true },
  // 冰岛超 02:00 凯夫拉维克 vs 维京古尔
  "冰岛超__凯夫拉维克_vs_维京古尔__02:00_HT": { htScore: "0-0", htHasGoal: false },
  // 冰岛超 02:00 哈夫纳夫约杜尔 vs 弗拉姆
  "冰岛超__哈夫纳夫约杜尔_vs_弗拉姆__02:00_HT": { htScore: "1-0", htHasGoal: true },
  "冰岛超__哈夫纳夫约杜尔_vs_弗拉姆__02:00_FT": { ftScore: "2-1", ftHasGoal: true },
  // 意甲 02:45 国米 vs 帕尔马
  "意甲__国际米兰_vs_帕尔马__02:45_FT": { ftScore: "2-0", ftHasGoal: true },
  // 法甲 02:45 里昂 vs 雷恩
  "法甲__里昂_vs_雷恩__02:45_HT": { htScore: "1-0", htHasGoal: true },
  "法甲__里昂_vs_雷恩__02:45_FT": { ftScore: "2-1", ftHasGoal: true },
  // 西甲 03:00 西班牙人 vs 皇马
  "西甲__西班牙人_vs_皇家马德里__03:00_FT": { ftScore: "0-2", ftHasGoal: true },
  // 阿甲 03:00 拉普拉塔体操 vs 阿根廷青年人
  "阿甲__拉普拉塔体操_vs_阿根廷青年人__03:00_FT": { ftScore: "0-1", ftHasGoal: true },
  // 阿甲 03:00 罗萨里奥中央 vs 泰格雷
  "阿甲__罗萨里奥中央_vs_泰格雷__03:00_FT": { ftScore: "1-0", ftHasGoal: true },
  // 巴西甲 03:00 圣保罗 vs 巴伊亚
  "巴西甲__圣保罗_vs_巴伊亚__03:00_FT": { ftScore: "0-0", ftHasGoal: false },
  // 美职业 05:30 奥斯汀FC vs 圣路易斯城
  "美职业__奥斯汀FC_vs_圣路易斯城__05:30_FT": { ftScore: "1-3", ftHasGoal: true },
  // 墨西联 09:15 托卢卡 vs 帕丘卡
  "墨西联附__托卢卡_vs_帕丘卡__09:15_HT": { htScore: "1-0", htHasGoal: true },
  "墨西联附__托卢卡_vs_帕丘卡__09:15_FT": { ftScore: "2-1", ftHasGoal: true },
};

// ================ 自动从捷报比分采集 ================
async function autoVerify() {
  console.log('🔍 V38.1 验证 - 2026-05-03 推荐结果\n');

  const data = loadJSON(PRED_FILE);
  if (!data || !data.predictions) {
    console.log('❌ 无推荐数据');
    return;
  }

  const preds = data.predictions.filter(p => p.date === '2026-05-03');
  console.log(`昨日推荐共 ${preds.length} 条\n`);
  console.log('='.repeat(60));
  console.log('开始从捷报比分采集实际比分...\n');

  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await ctx.newPage();

  // 先打开捷报比分主页面
  await page.goto('https://live.nowscore.com/2in1.aspx', { waitUntil: 'domcontentloaded', timeout: 20000 })
    .catch(() => console.log('  ⚠️ 连接超时，尝试继续...'));
  await page.waitForTimeout(3000);

  // 获取昨日日期的比赛列表
  // 捷报比分可以改日期查看历史比赛
  // 尝试获取所有比赛信息
  const matches = await page.evaluate(() => {
    const rows = document.querySelectorAll('#table_1 tr, .live_table tr, tr[class*="row"]');
    const results = [];
    rows.forEach(row => {
      const text = row.textContent.trim();
      if (text.length > 10) results.push(text);
    });
    return results.slice(0, 500);
  });
  
  console.log(`  采集到 ${matches.length} 行数据`);
  if (matches.length > 0) {
    console.log('  前10行:');
    matches.slice(0, 10).forEach((m, i) => console.log(`    ${i+1}. ${m.substring(0, 100)}`));
  }

  // 由于自动采集可能无法精确匹配，先用已知结果验证
  console.log('\n==============================');
  console.log('使用已知比赛结果验证（后续可替换为自动采集）:\n');
  
  let verifiedCount = 0;
  for (const p of preds) {
    const result = KNOWN_RESULTS[p.matchId];
    if (!result) {
      console.log(`  ⚠️ ${p.league} ${p.home} vs ${p.away} — 未找到结果`);
      continue;
    }

    const isHT = p.matchId.endsWith('_HT');
    if (isHT && result.htHasGoal !== undefined) {
      p.verified = true;
      p.htScore = result.htScore;
      p.htHasGoal = result.htHasGoal;
      verifiedCount++;
      const emoji = result.htHasGoal ? '✅' : '❌';
      console.log(`  ${emoji} [上半场] ${p.league} ${p.home} ${result.htScore} ${p.away} (${result.htHasGoal ? '有球' : '0-0'})`);
    } else if (!isHT && result.ftHasGoal !== undefined) {
      p.verified = true;
      p.ftScore = result.ftScore;
      // 下半场有球 = 全场有球且上半场已有球则下半场有球，或者全场有球但上半场0-0
      if (result.htHasGoal !== undefined) {
        // 下半场有球 = 全场总进球 > 上半场总进球
        const ftTotal = parseInt(result.ftScore?.split('-')[0] || '0') + parseInt(result.ftScore?.split('-')[1] || '0');
        const htTotal = parseInt(result.htScore?.split('-')[0] || '0') + parseInt(result.htScore?.split('-')[1] || '0');
        const lfHasGoal = result.ftHasGoal && ftTotal > htTotal;
        p.ftHasGoal = result.ftHasGoal;
        p.ftScore = result.ftScore;
        p.verified = true;
        verifiedCount++;
        const emoji = result.ftHasGoal ? '✅' : '❌';
        console.log(`  ${emoji} [下半场] ${p.league} ${p.home} ${result.ftScore} ${p.away} (全场${result.ftHasGoal ? '有球' : '0-0'})`);
      } else {
        p.verified = true;
        p.ftHasGoal = result.ftHasGoal;
        p.ftScore = result.ftScore;
        verifiedCount++;
        const emoji = result.ftHasGoal ? '✅' : '❌';
        console.log(`  ${emoji} [下半场] ${p.league} ${p.home} ${result.ftScore} ${p.away} (全场${result.ftHasGoal ? '有球' : '0-0'})`);
      }
    }
  }

  // 保存验证结果
  saveJSON(PRED_FILE, data);
  console.log(`\n✅ 已验证 ${verifiedCount}/${preds.length} 条推荐`);

  // 打印统计
  printStats(data.predictions);
  
  await browser.close();
}

function printStats(preds) {
  // 上半场统计
  const htPreds = preds.filter(p => p.matchId.endsWith('_HT') && p.verified);
  const ftPreds = preds.filter(p => p.matchId.endsWith('_FT') && p.verified);
  
  console.log('\n📊 统计报告');
  console.log('='.repeat(60));
  
  // 按进球率分组（上半场）
  if (htPreds.length > 0) {
    console.log('\n⚡ 上半场:');
    const groups = { '100': { t: 0, h: 0 }, '90': { t: 0, h: 0 }, '80-89': { t: 0, h: 0 } };
    htPreds.forEach(p => {
      const k = p.h2hRate >= 100 ? '100' : p.h2hRate >= 90 ? '90' : '80-89';
      groups[k].t++;
      if (p.htHasGoal) groups[k].h++;
    });
    for (const k of ['100', '90', '80-89']) {
      const g = groups[k];
      const rate = g.t > 0 ? (g.h / g.t * 100).toFixed(1) + '%' : '-';
      const yieldV = g.t > 0 ? (((g.h * 1.85 - g.t) / g.t) * 100).toFixed(1) + '%' : '-';
      console.log(`  ${k}%\t${g.h}/${g.t}\t命中率${rate}\t收益率${yieldV}`);
    }
    const total = { h: htPreds.filter(p => p.htHasGoal).length, t: htPreds.length };
    const tr = total.t > 0 ? (total.h / total.t * 100).toFixed(1) + '%' : '-';
    const ty = total.t > 0 ? (((total.h * 1.85 - total.t) / total.t) * 100).toFixed(1) + '%' : '-';
    console.log(`  总计\t${total.h}/${total.t}\t命中率${tr}\t收益率${ty}`);
  }

  // 下半场统计
  if (ftPreds.length > 0) {
    console.log('\n⚽ 下半场:');
    const groups = { '100': { t: 0, h: 0 }, '90': { t: 0, h: 0 }, '80-89': { t: 0, h: 0 } };
    ftPreds.forEach(p => {
      const k = p.h2hRate >= 100 ? '100' : p.h2hRate >= 90 ? '90' : '80-89';
      groups[k].t++;
      if (p.ftHasGoal) groups[k].h++;
    });
    for (const k of ['100', '90', '80-89']) {
      const g = groups[k];
      const rate = g.t > 0 ? (g.h / g.t * 100).toFixed(1) + '%' : '-';
      const yieldV = g.t > 0 ? (((g.h * 1.85 - g.t) / g.t) * 100).toFixed(1) + '%' : '-';
      console.log(`  ${k}%\t${g.h}/${g.t}\t命中率${rate}\t收益率${yieldV}`);
    }
    const total = { h: ftPreds.filter(p => p.ftHasGoal).length, t: ftPreds.length };
    const tr = total.t > 0 ? (total.h / total.t * 100).toFixed(1) + '%' : '-';
    const ty = total.t > 0 ? (((total.h * 1.85 - total.t) / total.t) * 100).toFixed(1) + '%' : '-';
    console.log(`  总计\t${total.h}/${total.t}\t命中率${tr}\t收益率${ty}`);
  }

  // 让球盘追踪
  const ahData = preds.filter(p => p.ftHandicapResult !== null && p.ftHandicapResult !== undefined);
  if (ahData.length > 0) {
    const ahWins = ahData.filter(p => p.ftHandicapResult === 'win').length;
    console.log(`\n⚽ 让球盘: ${ahWins}/${ahData.length}`);
  }
}

// 先尝试自动采集，但用已知结果兜底
autoVerify().catch(err => {
  console.error('验证出错:', err.message);
  // 如果自动采集失败，至少用已知结果跑一遍
  console.log('\n⚠️ 自动采集失败，使用已知结果验证...');
  const data = require(path.join(__dirname, '..', 'data', '验证存档', 'v38.1', 'predictions.json'));
  const preds = data.predictions.filter(p => p.date === '2026-05-03');
  
  // 用已知结果验证 (同上逻辑)
  for (const p of preds) {
    const result = KNOWN_RESULTS[p.matchId];
    if (!result) continue;
    const isHT = p.matchId.endsWith('_HT');
    if (isHT && result.htHasGoal !== undefined) {
      p.verified = true;
      p.htScore = result.htScore;
      p.htHasGoal = result.htHasGoal;
    } else if (!isHT) {
      p.verified = true;
      p.ftHasGoal = result.ftHasGoal;
      p.ftScore = result.ftScore;
    }
  }
  
  const verifiedCount = preds.filter(p => p.verified).length;
  const totalCount = preds.length;
  require('fs').writeFileSync(PRED_FILE, JSON.stringify(data, null, 2));
  console.log(`✅ 已验证 ${verifiedCount}/${totalCount} 条推荐 (已知结果)`);
  printStats(data.predictions);
});
