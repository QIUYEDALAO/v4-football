#!/usr/bin/env node
/**
 * fetch-odds-all.js — 批量拉取 Odds（不限 bookmaker）
 * 
 * 不再指定 bookmaker=8，而是拉取所有可用的庄家赔率
 * 按日期从最近到最早倒序处理，覆盖最大化
 * 
 * 用法: node engine/fetch-odds-all.js
 */

const https = require('https');
const fs = require('fs');
const path = require('path');

const API_KEY = 'e5e315b1f9ba1ba51dc2124b35f07a01';
const API_HOST = 'v3.football.api-sports.io';
const RAW_DIR = path.join(__dirname, '..', 'data', 'raw_fixtures');
const oddsDir = path.join(RAW_DIR, 'odds');

let reqCount = 0;

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

function api(path) {
  return new Promise((resolve, reject) => {
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
          reject(new Error(`Parse error: ${data.substring(0, 80)}`));
        }
      });
    }).on('error', reject);
  });
}

async function retryApi(path, retries = 2) {
  for (let i = 0; i < retries; i++) {
    try {
      return await api(path);
    } catch (e) {
      if (i < retries - 1) {
        await sleep(1000 * (i + 1));
      } else {
        throw e;
      }
    }
  }
}

async function main() {
  fs.mkdirSync(oddsDir, { recursive: true });

  // 读取赛程列表 + 已采集的 odds
  const fixtures = JSON.parse(fs.readFileSync(path.join(RAW_DIR, 'fixtures_list.json'), 'utf8'));
  const doneOdds = new Set(fs.readdirSync(oddsDir).map(f => parseInt(f.replace('.json', ''))));

  // 按日期倒序排列（最近的在前面）
  const sorted = [...fixtures].sort((a, b) => b.date.localeCompare(a.date));

  console.log('='.repeat(60));
  console.log('Odds 批量拉取器（不限 bookmaker）');
  console.log(`总比赛: ${fixtures.length}`);
  console.log(`已有 odds: ${doneOdds.size}`);
  console.log(`待拉取: ${fixtures.length - doneOdds.size}`);
  console.log('='.repeat(60) + '\n');

  let success = 0;
  let empty = 0;
  let skip = 0;
  let batchStart = Date.now();
  let batchCount = 0;

  for (let i = 0; i < sorted.length; i++) {
    const f = sorted[i];
    const fid = f.id;

    // 跳过已有
    if (doneOdds.has(fid)) {
      skip++;
      continue;
    }

    const label = `${f.date.substring(0, 10)} ${f.home} vs ${f.away}`.substring(0, 45);

    try {
      // 不指定 bookmaker，拉取所有可用庄家
      const r = await retryApi(`/odds?fixture=${fid}`);
      
      if (r.response && r.response[0]) {
        const odds = r.response[0];
        if (odds.bookmakers && odds.bookmakers.length > 0) {
          fs.writeFileSync(path.join(oddsDir, `${fid}.json`), JSON.stringify(odds, null, 2));
          success++;
        } else {
          empty++;
        }
      } else {
        empty++;
      }
    } catch (e) {
      empty++;
    }

    batchCount++;

    // 每 10 场输出进度
    if (batchCount % 10 === 0) {
      const elapsed = ((Date.now() - batchStart) / 1000).toFixed(0);
      const pct = ((i + 1) / sorted.length * 100).toFixed(1);
      const totalDone = doneOdds.size + success;
      console.log(`[${i + 1}/${sorted.length}] ${pct}% | odds: ${totalDone} | 空: ${empty} | 请求: ${reqCount} | ${elapsed}s`);
    }

    // 每 60 场打印详细状态
    if (batchCount % 60 === 0) {
      const totalDone = doneOdds.size + success;
      console.log(`   📊 Odds 总计: ${totalDone}/${fixtures.length} (${(totalDone/fixtures.length*100).toFixed(1)}%)`);
    }

    // 限频
    await sleep(80); // 限频
  }

  const totalDone = doneOdds.size + success;
  console.log('\n' + '='.repeat(60));
  console.log(`✅ 完成!`);
  console.log(`📊 Odds: ${totalDone}/${fixtures.length} (${(totalDone/fixtures.length*100).toFixed(1)}%)`);
  console.log(`📊 新增: ${success} | 空数据(无赔率): ${empty} | 已跳过: ${skip}`);
  console.log(`📊 总请求: ${reqCount}`);
  console.log('='.repeat(60));
}

main().catch(e => {
  console.error('\n❌ 错误:', e.message);
  process.exit(1);
});
