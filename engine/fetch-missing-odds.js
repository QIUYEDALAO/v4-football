#!/usr/bin/env node
// 拉取4月27日~5月4日区间缺失的赔率
const https = require('https');
const fs = require('fs');
const path = require('path');

const API_KEY = 'e5e315b1f9ba1ba51dc2124b35f07a01';
const RAW_DIR = path.join(__dirname, '..', 'data', 'raw_fixtures');
const oddsDir = path.join(RAW_DIR, 'odds');

const fixtures = JSON.parse(fs.readFileSync(path.join(RAW_DIR, 'fixtures_list.json'), 'utf8'));
const doneOdds = new Set(fs.readdirSync(oddsDir).filter(f => f.endsWith('.json') && !f.startsWith('_')).map(f => parseInt(f.replace('.json',''))));

// 只扫 4月27日~5月4日 缺失的
const missing = fixtures.filter(f => f.date.substring(0,10) >= '2026-04-27' && !doneOdds.has(f.id));

console.log(`4月27日~5月4日区间: 缺失 ${missing.length} 场`);
if (missing.length === 0) {
  console.log('全部已覆盖!');
  process.exit(0);
}

let i = 0;
function next() {
  if (i >= missing.length) {
    const finalCount = fs.readdirSync(oddsDir).filter(f => f.endsWith('.json') && !f.startsWith('_')).length;
    console.log(`\n✅ 完成! Odds 总数: ${finalCount}`);
    process.exit(0);
  }
  const f = missing[i];
  https.get(`https://v3.football.api-sports.io/odds?fixture=${f.id}`, { headers: { 'x-apisports-key': API_KEY } }, res => {
    let d = '';
    res.on('data', c => d += c);
    res.on('end', () => {
      try {
        const j = JSON.parse(d);
        if (j.response && j.response[0] && j.response[0].bookmakers && j.response[0].bookmakers.length > 0) {
          fs.writeFileSync(path.join(oddsDir, `${f.id}.json`), JSON.stringify(j.response[0], null, 2));
          process.stdout.write(`✅`);
        } else {
          process.stdout.write(`⛔`);
        }
      } catch(e) {
        process.stdout.write(`❌`);
      }
      i++;
      setTimeout(next, 100);
    });
  }).on('error', () => { i++; setTimeout(next, 100); });
}
next();
