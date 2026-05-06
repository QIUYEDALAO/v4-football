#!/usr/bin/env node
/**
 * 获取比赛完场比分
 */

const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  
  await page.goto('https://live.nowscore.com/2in1.aspx', { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.waitForTimeout(5000);
  
  // 点击"完场"查看已完赛比赛
  try {
    await page.evaluate(() => {
      for (const el of document.querySelectorAll('a')) {
        if (el.textContent.trim() === '完场') {
          el.click();
          return;
        }
      }
    });
    await page.waitForTimeout(3000);
  } catch (e) {}
  
  // 获取页面文本
  const text = await page.evaluate(() => document.body.innerText);
  
  // 解析比赛结果
  const results = [];
  const lines = text.split('\n');
  
  for (const line of lines) {
    const parts = line.split('\t');
    if (parts.length < 8) continue;
    
    const league = parts[1]?.trim() || '';
    const time = parts[2]?.trim() || '';
    const status = parts[3]?.trim() || '';
    const home = parts[4]?.trim() || '';
    const score = parts[5]?.trim() || '';
    const away = parts[6]?.trim() || '';
    
    // 只看完场或半场
    if (!['完', '半场'].includes(status)) continue;
    if (!home || !away || !score) continue;
    
    // 解析比分
    const scoreMatch = score.match(/(\d+)-(\d+)/);
    if (!scoreMatch) continue;
    
    results.push({
      league,
      time,
      status,
      home,
      away,
      ft: `${scoreMatch[1]}-${scoreMatch[2]}`,
      ftHome: parseInt(scoreMatch[1]),
      ftAway: parseInt(scoreMatch[2])
    });
  }
  
  // 输出JSON
  console.log(JSON.stringify(results, null, 2));
  
  await browser.close();
})();
