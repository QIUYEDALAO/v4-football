#!/usr/bin/env node
const https = require('https');
const vm = require('vm');
const fs = require('fs');

function fetchUrl(url) {
  return new Promise((resolve, reject) => {
    https.get(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': '*/*',
        'Accept-Language': 'zh-CN,zh;q=0.9',
      },
      timeout: 20000,
    }, (res) => {
      const chunks = [];
      res.on('data', c => chunks.push(c));
      res.on('end', () => resolve(Buffer.concat(chunks)));
    }).on('error', reject).on('timeout', function() { this.destroy(); reject(new Error('timeout')); });
  });
}

function parseBF(raw) {
  let code = raw
    .replace(/ShowBf\(\);?\s*$/, '')
    .replace(/\bShowBf\s*\(\)/g, '0')
    .replace(/^var\s+(A|B|C)\s*=\s*Array\(/gm, 'globalThis.$1=Array(')
    .replace(/^var\s+(matchcount|sclasscount|countrycount|matchdate)\s*=/gm, 'globalThis.$1=')
    .replace(/^A\[(\d+)\]=/gm, 'globalThis.A[$1]=')
    .replace(/^B\[(\d+)\]=/gm, 'globalThis.B[$1]=')
    .replace(/^C\[(\d+)\]=/gm, 'globalThis.C[$1]=');
  
  console.log('Code length:', code.length);
  console.log('First 100 chars:', JSON.stringify(code.slice(0, 100)));
  console.log('Check for \\r:', code.slice(0, 50).includes('\r'));
  
  try {
    const ctx = vm.createContext({ A: [], B: [], C: [] });
    vm.runInContext(code, ctx, { timeout: 5000 });
    return { A: ctx.A, B: ctx.B };
  } catch(e) {
    console.log('VM ERROR:', e.message);
    const m = e.message.match(/position (\d+)/);
    if (m) {
      const pos = parseInt(m[1]);
      console.log('Context:', JSON.stringify(code.slice(Math.max(0,pos-80), pos+80)));
    }
    throw e;
  }
}

async function main() {
  const buf = await fetchUrl('https://live.nowscore.com/data/bf.js?' + Date.now());
  const raw = buf.toString('utf-8');
  console.log('Raw length:', raw.length);
  const { A, B } = parseBF(raw);
  console.log('A:', A.length, 'B:', B.length);
}

main().catch(e => {
  console.error('FATAL:', e.stack || e.message);
  process.exit(1);
});
