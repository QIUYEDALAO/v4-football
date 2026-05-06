#!/usr/bin/env node
/**
 * V38.1 快速验证 — 从捷报比分完赛页面获取昨天比赛结果
 * 用法: node tools/quick-verify.js
 */
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const PRED_FILE = path.join(__dirname, '..', 'data', '验证存档', 'v38.1', 'predictions.json');

async function main() {
  console.log('🔍 V38.1 验证 - 2026-05-03\n');
  
  const data = JSON.parse(fs.readFileSync(PRED_FILE, 'utf8'));
  const preds = data.predictions.filter(p => p.date === '2026-05-03');
  console.log(`昨日推荐共 ${preds.length} 条\n`);

  // 打开完赛页面获取昨天比赛
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1280, height: 2000 } });
  
  // 完赛页面 ft1
  await page.goto('https://live.nowscore.com/schedule.aspx?f=ft1&d=2026-05-03', { 
    waitUntil: 'networkidle', timeout: 30000 
  }).catch(() => {});
  await page.waitForTimeout(3000);
  
  // 获取页面完整内容
  const html = await page.content();
  fs.writeFileSync('/tmp/jiebao-ft1.html', html);
  console.log('页面已保存，大小:', html.length);
  
  // 尝试提取比赛数据
  const pageText = await page.evaluate(() => document.body.innerText);
  console.log('\n页面文本前1000字:', pageText.substring(0, 1000));
  
  await browser.close();
}

main().catch(e => {
  console.error('错误:', e.message);
  process.exit(1);
});
