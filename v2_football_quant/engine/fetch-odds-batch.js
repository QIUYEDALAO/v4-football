#!/usr/bin/env node
/**
 * fetch-odds-batch.js — 智能批量拉取 Odds
 * 
 * 策略：
 * 1. 先扫一遍所有无 odds 的比赛，标记哪些 API 能返回数据
 * 2. 只保存有赔率的（减少磁盘空文件）
 * 3. 记录"无赔率"比赛 ID 避免重复请求
 * 
 * 用法: node engine/fetch-odds-batch.js
 */

const https = require('https');
const fs = require('fs');
const path = require('path');

const API_KEY = '你的API-KEY请替换';
const API_HOST = 'v3.football.api-sports.io';
const RAW_DIR = path.join(__dirname, '..', 'data', 'raw_fixtures');
const oddsDir = path.join(RAW_DIR, 'odds');
const SKIP_FILE = path.join(oddsDir, '_no_odds.json');

let totalReqs = 0;
let skippedEmpty = new Set();
let startTime = Date.now();

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

function api(path) {
  return new Promise((resolve, reject) => {
    const url = new URL(path, `https://${API_HOST}`);
    https.get(url.toString(), { headers: { 'x-apisports-key': API_KEY } }, res => {
      let data = '';
      res.on('data', c => data += c);
      res.on('end', () => {
        totalReqs++;
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

  // 读取赛程列表 + 已有 odds + 已知无赔率列表
  const fixtures = JSON.parse(fs.readFileSync(path.join(RAW_DIR, 'fixtures_list.json'), 'utf8'));
  const doneOdds = new Set(fs.readdirSync(oddsDir)
    .filter(f => f.endsWith('.json') && !f.startsWith('_'))
    .map(f => parseInt(f.replace('.json', ''))));

  // 加载已知无赔率的 ID
  if (fs.existsSync(SKIP_FILE)) {
    const skipData = JSON.parse(fs.readFileSync(SKIP_FILE, 'utf8'));
    if (Array.isArray(skipData)) skipData.forEach(id => skippedEmpty.add(id));
    console.log(`📋 已标记 ${skippedEmpty.size} 场无赔率（跳过）`);
  }

  const pending = fixtures.filter(f => !doneOdds.has(f.id) && !skippedEmpty.has(f.id));

  // 按日期倒序
  pending.sort((a, b) => b.date.localeCompare(a.date));

  console.log('='.repeat(60));
  console.log('Odds 智能批量拉取器');
  console.log(`总比赛: ${fixtures.length}`);
  console.log(`已有 odds: ${doneOdds.size}`);
  console.log(`已跳过(无赔率): ${skippedEmpty.size}`);
  console.log(`待拉取: ${pending.length}`);
  console.log('='.repeat(60) + '\n');

  let success = 0;
  let empty = 0;
  let batchStart = Date.now();
  const total = pending.length;

  for (let i = 0; i < pending.length; i++) {
    const f = pending[i];
    const fid = f.id;
    const elapsed = ((Date.now() - batchStart) / 1000).toFixed(0);

    try {
      const r = await retryApi(`/odds?fixture=${fid}`);
      
      if (r.response && r.response[0]) {
        const odds = r.response[0];
        if (odds.bookmakers && odds.bookmakers.length > 0) {
          fs.writeFileSync(path.join(oddsDir, `${fid}.json`), JSON.stringify(odds, null, 2));
          success++;
        } else {
          empty++;
          skippedEmpty.add(fid);
        }
      } else {
        empty++;
        skippedEmpty.add(fid);
      }
    } catch (e) {
      empty++;
      skippedEmpty.add(fid);
    }

    // 每 5 场保存一次跳过列表（防止崩了丢数据）
    if (i % 5 === 0 && skippedEmpty.size > 0) {
      fs.writeFileSync(SKIP_FILE, JSON.stringify([...skippedEmpty]));
    }

    // 每 20 场输出进度
    if (i % 20 === 0 || i === pending.length - 1) {
      const pct = ((i + 1) / pending.length * 100).toFixed(1);
      const totalOdds = doneOdds.size + success;
      const rate = success > 0 ? (success / (i + 1) * 100).toFixed(1) : '0.0';
      console.log(`[${i + 1}/${pending.length}] ${pct}% | 新增: ${success} | 空: ${empty} | 命中率: ${rate}% | 总计: ${totalOdds} | 请求: ${totalReqs} | ${elapsed}s`);
    }

    // 限频 80ms
    await sleep(80);
  }

  // 最终保存跳过列表
  fs.writeFileSync(SKIP_FILE, JSON.stringify([...skippedEmpty]));

  const finalOdds = doneOdds.size + success;
  const totalElapsed = ((Date.now() - startTime) / 1000 / 60).toFixed(1);
  console.log('\n' + '='.repeat(60));
  console.log(`✅ 完成! 用时 ${totalElapsed} 分钟`);
  console.log(`📊 Odds: ${finalOdds}/${fixtures.length} (${(finalOdds/fixtures.length*100).toFixed(1)}%)`);
  console.log(`📊 新增: ${success} | 空数据: ${empty} | 已标记无赔率: ${skippedEmpty.size}`);
  console.log(`📊 总请求: ${totalReqs}`);
  console.log(`📊 API 剩余约: ${7500 - totalReqs} 次（今日）`);
  console.log('='.repeat(60));
}

main().catch(e => {
  console.error('\n❌ 错误:', e.message);
  process.exit(1);
});
