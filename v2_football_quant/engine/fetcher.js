#!/usr/bin/env node
/**
 * fetcher.js — API-Football 数据拉取器
 * 负责: 批量拉取赛程/H2H/赔率/预测，落盘到本地
 * 
 * 用法: node engine/fetcher.js
 */

const https = require('https');
const fs = require('fs');
const path = require('path');

const API_KEY = '你的API-KEY请替换';
const API_HOST = 'v3.football.api-sports.io';
const LEAGUES = require('../config/leagues_whitelist.json').leagueId;
const LEAGUE_IDS = Object.keys(LEAGUES).map(Number);

const RAW_DIR = path.join(__dirname, '..', 'data', 'raw_fixtures');
const LOG_DIR = path.join(__dirname, '..', 'logs');

let reqCount = 0;
const MAX_REQUESTS = 6500; // 软上限

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

function api(path) {
  return new Promise((resolve, reject) => {
    if (reqCount >= MAX_REQUESTS) {
      reject(new Error(`Request limit reached (${MAX_REQUESTS})`));
      return;
    }
    const url = new URL(path, `https://${API_HOST}`);
    https.get(url.toString(), { headers: { 'x-apisports-key': API_KEY } }, res => {
      let data = '';
      res.on('data', c => data += c);
      res.on('end', () => {
        reqCount++;
        try {
          const parsed = JSON.parse(data);
          if (parsed.errors && Object.keys(parsed.errors).length > 0 && !parsed.response) {
            reject(new Error(JSON.stringify(parsed.errors)));
          } else {
            resolve(parsed);
          }
        } catch (e) {
          reject(new Error(`Parse error: ${data.substring(0,80)}`));
        }
      });
    }).on('error', reject);
  });
}

async function retryApi(path, retries = 3) {
  for (let i = 0; i < retries; i++) {
    try {
      return await api(path);
    } catch (e) {
      if (i < retries - 1) {
        const wait = 1000 * (i + 1);
        console.log(`  ⚠️ 重试 ${path.substring(0,40)}... (${i+1}/${retries})`);
        await sleep(wait);
      } else {
        throw e;
      }
    }
  }
}

async function main() {
  fs.mkdirSync(RAW_DIR, { recursive: true });
  fs.mkdirSync(LOG_DIR, { recursive: true });

  console.log('='.repeat(70));
  console.log('API-Football 批量拉取器');
  console.log('开始: ' + new Date().toISOString());
  console.log(`联赛: ${LEAGUE_IDS.length}个`);
  console.log(`请求上限: ${MAX_REQUESTS}`);
  console.log('='.repeat(70) + '\n');

  const today = new Date().toISOString().split('T')[0];
  // 拉取3个月的历史数据 (3月5日 ~ 今天)
  const startDate = new Date();
  startDate.setDate(startDate.getDate() - 60); // 60天
  const startStr = startDate.toISOString().split('T')[0];
  
  console.log(`📡 拉取 ${startStr} ~ ${today} 的历史数据...\n`);

  // Step 1: 拉取所有联赛的赛程
  const allFixtures = [];
  
  for (const lid of LEAGUE_IDS) {
    const cn = LEAGUES[lid];
    process.stdout.write(`  [联赛] ${cn}(ID:${lid})... `);

    try {
      // 分批拉取，按日期分段避免超时
      const r = await retryApi(`/fixtures?league=${lid}&season=2025&status=FT`);
      
      if (!r.response || r.response.length === 0) {
        process.stdout.write(`空\n`);
        continue;
      }

      // 只保留 60天内的
      const recent = r.response.filter(f => {
        const d = f.fixture.date.substring(0, 10);
        return d >= startStr && d <= today;
      });

      process.stdout.write(`${recent.length}场\n`);
      allFixtures.push(...recent);
    } catch (e) {
      process.stdout.write(`❌ ${e.message.substring(0,40)}\n`);
    }

    await sleep(500); // 限频
  }

  // 去重
  const seen = new Set();
  const unique = allFixtures.filter(f => {
    if (seen.has(f.fixture.id)) return false;
    seen.add(f.fixture.id);
    return true;
  });

  console.log(`\n📊 总计 ${unique.length} 场已完赛比赛`);

  // 保存赛程列表
  const fixtureList = unique.map(f => ({
    id: f.fixture.id,
    date: f.fixture.date,
    league: f.league.id,
    home: f.teams.home.name,
    away: f.teams.away.name,
    homeId: f.teams.home.id,
    awayId: f.teams.away.id,
    htHome: f.score.halftime.home,
    htAway: f.score.halftime.away,
    ftHome: f.goals.home,
    ftAway: f.goals.away,
  }));

  fs.writeFileSync(path.join(RAW_DIR, 'fixtures_list.json'), JSON.stringify(fixtureList, null, 2));
  console.log(`✅ 已保存赛程列表: ${fixtureList.length} 场`);

  // Step 2: 批量拉取 H2H + Predictions + Odds
  console.log(`\n📡 拉取每场比赛的深度数据...\n`);

  const h2hDir = path.join(RAW_DIR, 'h2h');
  const predDir = path.join(RAW_DIR, 'predictions');
  const oddsDir = path.join(RAW_DIR, 'odds');
  fs.mkdirSync(h2hDir, { recursive: true });
  fs.mkdirSync(predDir, { recursive: true });
  fs.mkdirSync(oddsDir, { recursive: true });

  let success = 0, fail = 0;

  for (let i = 0; i < unique.length; i++) {
    const f = unique[i];
    const fid = f.fixture.id;
    const progress = `[${i+1}/${unique.length}]`;
    const label = `${f.teams.home.name} vs ${f.teams.away.name}`.substring(0, 35);

    // H2H
    process.stdout.write(`  ${progress} ${label}... `);
    try {
      const h2h = await retryApi(`/fixtures/headtohead?h2h=${f.teams.home.id}-${f.teams.away.id}&last=10`);
      if (h2h.response) {
        fs.writeFileSync(path.join(h2hDir, `${fid}.json`), JSON.stringify(h2h.response, null, 2));
      }
    } catch (e) {
      // 有些球队没有H2H
    }

    // Predictions
    try {
      const pred = await retryApi(`/predictions?fixture=${fid}`);
      if (pred.response) {
        fs.writeFileSync(path.join(predDir, `${fid}.json`), JSON.stringify(pred.response[0], null, 2));
      }
    } catch (e) {}

    // Odds (Pinnacle=8)
    try {
      const odds = await retryApi(`/odds?fixture=${fid}&bookmaker=8`);
      if (odds.response) {
        fs.writeFileSync(path.join(oddsDir, `${fid}.json`), JSON.stringify(odds.response[0], null, 2));
      }
    } catch (e) {}

    await sleep(300);
    success++;
    process.stdout.write(`✅\n`);
  }

  console.log(`\n✅ 完成! ${success}场成功, ${fail}场失败`);
  console.log(`📊 共 ${reqCount}/${MAX_REQUESTS} 次请求`);
  console.log(`📁 数据路径: ${RAW_DIR}`);
}

main().catch(e => {
  console.error('\n❌ 错误:', e.message);
  process.exit(1);
});
