#!/usr/bin/env node
/**
 * API-Football 数据采集器 v1
 * 数据源: https://www.api-football.com (v3 API)
 * 
 * 用法: node tools/api-football-scraper-v1.js
 */

const https = require('https');
const fs = require('fs');
const path = require('path');

const API_KEY = 'e5e315b1f9ba1ba51dc2124b35f07a01';
const API_HOST = 'v3.football.api-sports.io';
const PRED_FILE = path.join(__dirname, '..', 'data', '验证存档', 'apif-v1', 'predictions.json');
const LEAGUE_CFG = require('./apif-config.js');

function api(endpoint) {
  return new Promise((resolve, reject) => {
    const url = new URL(endpoint, `https://${API_HOST}`);
    https.get(url.toString(), { headers: { 'x-apisports-key': API_KEY } }, res => {
      let data = '';
      res.on('data', c => data += c);
      res.on('end', () => {
        try {
          const parsed = JSON.parse(data);
          if (parsed.errors && Object.keys(parsed.errors).length > 0) {
            reject(new Error(JSON.stringify(parsed.errors)));
          } else {
            resolve(parsed);
          }
        } catch(e) {
          reject(new Error('Parse: ' + data.substring(0,80)));
        }
      });
    }).on('error', reject);
  });
}

async function getH2H(team1Id, team2Id, lastCount = 10) {
  const r = await api(`/fixtures/headtohead?h2h=${team1Id}-${team2Id}&last=${lastCount}`);
  return r.response || [];
}

async function getOdds(fixtureId, bookmaker = 8) {
  try {
    const r = await api(`/odds?fixture=${fixtureId}&bookmaker=${bookmaker}`);
    if (r.response && r.response.length > 0) {
      return r.response[0].bookmakers || [];
    }
  } catch(e) {}
  return [];
}

async function main() {
  const startTime = Date.now();
  console.log('='.repeat(70));
  console.log('API-Football v1 采集器');
  console.log(`启动: ${new Date().toLocaleString('zh-CN', {timeZone:'Asia/Shanghai'})}`);
  console.log('='.repeat(70) + '\n');

  const today = new Date().toISOString().split('T')[0];
  let reqCount = 0;

  // Step 1: 获取今日赛程
  console.log(`📡 获取 ${today} 赛程...`);
  const schedule = await api(`/fixtures?date=${today}`);
  reqCount++;
  const allMatches = schedule.response || [];
  console.log(`  总比赛: ${allMatches.length} 场`);

  // 过滤白名单联赛
  const allowedIds = Object.keys(LEAGUE_CFG.leagueId).map(Number);
  const filtered = allMatches.filter(item => allowedIds.includes(item.league.id));

  // 只处理未开赛
  const upcoming = filtered.filter(item =>
    ['Not Started', 'Scheduled', 'Time to be defined'].includes(item.fixture.status.long)
  );

  console.log(`  白名单: ${filtered.length} 场`);
  console.log(`  未开赛: ${upcoming.length} 场\n`);

  if (upcoming.length === 0) {
    console.log('今日无符合条件比赛。\n');
    return;
  }

  // 显示赛程
  for (const item of upcoming) {
    const cn = LEAGUE_CFG.leagueId[item.league.id];
    const dt = new Date(item.fixture.date);
    const time = dt.toLocaleTimeString('zh-CN', {timeZone:'Asia/Shanghai', hour:'2-digit', minute:'2-digit'});
    console.log(`  📅 ${time} ${cn}: ${item.teams.home.name} vs ${item.teams.away.name}`);
  }
  console.log();

  // Step 2: 采集 H2H + 盘口
  console.log('📊 采集 H2H + 赔率...\n');

  const results = [];

  for (let i = 0; i < upcoming.length; i++) {
    const item = upcoming[i];
    const homeId = item.teams.home.id;
    const awayId = item.teams.away.id;
    const cn = LEAGUE_CFG.leagueId[item.league.id];
    const home = item.teams.home.name;
    const away = item.teams.away.name;
    const fixtureId = item.fixture.id;

    process.stdout.write(`  [${i+1}/${upcoming.length}] ${cn} ${home} vs ${away}... `);

    try {
      // 查 H2H（最近10场）
      const h2h = await getH2H(homeId, awayId);
      reqCount++;

      if (h2h.length === 0) {
        process.stdout.write(`无H2H记录\n`);
        continue;
      }

      // 计算上半场进球率
      const withHT = h2h.filter(m => m.score.halftime.home !== null);
      const total = withHT.length;
      const withGoal = withHT.filter(m => (m.score.halftime.home || 0) + (m.score.halftime.away || 0) > 0).length;
      const zeroZero = total - withGoal;
      const avgGoal = total > 0
        ? withHT.reduce((s, m) => s + (m.score.halftime.home || 0) + (m.score.halftime.away || 0), 0) / total
        : 0;
      const rate = total > 0 ? Math.round(withGoal / total * 100) : 0;

      // 检查条件
      if (total >= 4 && rate >= 80 && zeroZero <= 2) {
        // 查赔率
        const odds = await getOdds(fixtureId);
        reqCount++;

        // 提取半场大小球盘口
        let htOverUnder = null;
        let htOverOdds = null;
        for (const bm of odds) {
          for (const bet of bm.bets || []) {
            if (bet.name === 'Goals Over/Under First Half') {
              const over05 = bet.values.find(v => v.value === 'Over 0.5');
              const under05 = bet.values.find(v => v.value === 'Under 0.5');
              htOverUnder = over05 ? `大0.5@${over05.odd}` : null;
              break;
            }
          }
          if (htOverUnder) break;
        }

        process.stdout.write(`✅ ${rate}% H2H${total} 场均${avgGoal.toFixed(2)}球`);
        if (htOverUnder) process.stdout.write(` | ${htOverUnder}`);

        const level = rate === 100 ? '🔥🔥推荐' : (total <= 5 ? '⚡样本小' : '✅推荐');
        results.push({
          date: today, league: cn, time: new Date(item.fixture.date).toLocaleTimeString('zh-CN', {timeZone:'Asia/Shanghai', hour:'2-digit', minute:'2-digit'}),
          home, away, h2hRate: rate, h2hAvg: avgGoal, h2hCount: total, h2hZeroCount: zeroZero,
          htOverUnder, level, fixtureId, homeId, awayId
        });
        process.stdout.write(` | ${level}\n`);
      } else {
        const reasons = [];
        if (total < 4) reasons.push(`H2H${total}场<4`);
        if (rate < 80) reasons.push(`进球率${rate}%<80%`);
        if (zeroZero > 2) reasons.push(`0-0${zeroZero}场>2`);
        process.stdout.write(`❌ ${reasons.join(', ')}\n`);
      }
    } catch (e) {
      process.stdout.write(`⚠️ ${e.message.substring(0,60)}\n`);
    }
  }

  // Step 3: 输出报告
  const elapsed = ((Date.now() - startTime) / 1000).toFixed(0);

  console.log(`\n${'='.repeat(70)}`);
  console.log(`  API-Football 推荐清单 (${elapsed}s, ${results.length}场推荐, ${reqCount}次请求)`);
  console.log(`${'='.repeat(70)}\n`);

  if (results.length === 0) {
    console.log('无符合条件比赛。\n');
    return;
  }

  results.sort((a, b) => a.time.localeCompare(b.time));

  const h100 = results.filter(r => r.h2hRate === 100);
  const other = results.filter(r => r.h2hRate !== 100);

  if (h100.length > 0) {
    console.log('🔥🔥 100%进球率（优先推荐）');
    console.log('-'.repeat(100));
    h100.forEach(r => {
      const odds = r.htOverUnder ? ` | ${r.htOverUnder}` : '';
      console.log(`  ${r.time} ${r.league} | ${r.home} vs ${r.away} | H2H${r.h2hCount}场 场均${r.h2hAvg.toFixed(2)}球${odds} | ${r.level}`);
    });
    console.log();
  }

  if (other.length > 0) {
    console.log('✅ 80-89%进球率');
    console.log('-'.repeat(100));
    other.forEach(r => {
      const odds = r.htOverUnder ? ` | ${r.htOverUnder}` : '';
      console.log(`  ${r.time} ${r.league} | ${r.home} vs ${r.away} | ${r.h2hRate}% H2H${r.h2hCount}场 场均${r.h2hAvg.toFixed(2)}球${odds} | ${r.level}`);
    });
    console.log();
  }

  console.log(`共 ${results.length} 场推荐（100%: ${h100.length} · 80-89%: ${other.length}）`);

  // 保存
  fs.mkdirSync(path.dirname(PRED_FILE), { recursive: true });
  fs.writeFileSync(PRED_FILE, JSON.stringify({
    version: 'apif-v1', date: today, predictions: results
  }, null, 2));

  console.log(`\n✅ 已保存至 ${PRED_FILE}`);
  console.log(`📊 今日请求: ${reqCount}/7500`);
}

main().catch(e => {
  console.error('\n❌ 错误:', e.message);
  process.exit(1);
});
