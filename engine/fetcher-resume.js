#!/usr/bin/env node
/**
 * fetcher-resume.js — 断点续跑
 * 只拉取未完成的 H2H / Predictions / Odds
 */
const https = require('https');
const fs = require('fs');
const path = require('path');

const API_KEY = 'e5e315b1f9ba1ba51dc2124b35f07a01';
const API_HOST = 'v3.football.api-sports.io';
const RAW_DIR = path.join(__dirname, '..', 'data', 'raw_fixtures');
const h2hDir = path.join(RAW_DIR, 'h2h');
const predDir = path.join(RAW_DIR, 'predictions');
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
        try { resolve(JSON.parse(data)); }
        catch(e) { reject(new Error('Parse: ' + data.substring(0,60))); }
      });
    }).on('error', reject);
  });
}

async function main() {
  const fixtures = JSON.parse(fs.readFileSync(path.join(RAW_DIR, 'fixtures_list.json'), 'utf8'));
  const doneH2H = new Set(fs.readdirSync(h2hDir).map(f => parseInt(f.replace('.json',''))));
  const donePred = new Set(fs.readdirSync(predDir).map(f => parseInt(f.replace('.json',''))));
  const doneOdds = new Set(fs.readdirSync(oddsDir).map(f => parseInt(f.replace('.json',''))));

  console.log(`断点续跑: 总计${fixtures.length}场`);
  console.log(`已拉取: H2H=${doneH2H.size} Pred=${donePred.size} Odds=${doneOdds.size}`);

  let fetchCount = 0;
  for (let i = 0; i < fixtures.length; i++) {
    const f = fixtures[i];
    const fid = f.id;
    const hId = f.homeId;
    const aId = f.awayId;

    // 跳过全部已完成的
    if (doneH2H.has(fid) && donePred.has(fid) && doneOdds.has(fid)) continue;

    if (i % 100 === 0) {
      const pct = (i / fixtures.length * 100).toFixed(1);
      console.log(`[${i}/${fixtures.length}] ${pct}% | 请求: ${reqCount}`);
    }

    // H2H
    if (!doneH2H.has(fid)) {
      try {
        const r = await api(`/fixtures/headtohead?h2h=${hId}-${aId}&last=10`);
        if (r.response) fs.writeFileSync(path.join(h2hDir, `${fid}.json`), JSON.stringify(r.response));
      } catch(e) {}
      await sleep(250);
    }

    // Predictions
    if (!donePred.has(fid)) {
      try {
        const r = await api(`/predictions?fixture=${fid}`);
        if (r.response) fs.writeFileSync(path.join(predDir, `${fid}.json`), JSON.stringify(r.response[0]));
      } catch(e) {}
      await sleep(250);
    }

    // Odds (Pinnacle bookmaker=8)
    if (!doneOdds.has(fid)) {
      try {
        const r = await api(`/odds?fixture=${fid}&bookmaker=8`);
        if (r.response) fs.writeFileSync(path.join(oddsDir, `${fid}.json`), JSON.stringify(r.response[0]));
      } catch(e) {}
      await sleep(250);
    }

    fetchCount++;
    if (fetchCount % 50 === 0) {
      const h = fs.readdirSync(h2hDir).length;
      const p = fs.readdirSync(predDir).length;
      const o = fs.readdirSync(oddsDir).length;
      console.log(`  进度: H2H=${h} Pred=${p} Odds=${o} | 已用请求: ${reqCount}`);
    }
  }

  const h = fs.readdirSync(h2hDir).length;
  const p = fs.readdirSync(predDir).length;
  const o = fs.readdirSync(oddsDir).length;
  console.log(`\n✅ 完成! H2H=${h} Pred=${p} Odds=${o} | 总请求: ${reqCount}`);
}

main().catch(e => {
  console.error('错误:', e.message);
  process.exit(1);
});
