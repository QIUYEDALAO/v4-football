#!/usr/bin/env node
/**
 * 从捷报比分获取比赛半场比分 - v2
 * 直接访问比赛列表页，点击进入比赛详情
 */

const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await ctx.newPage();
  
  await page.goto('https://live.nowscore.com/2in1.aspx', { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.waitForTimeout(5000);
  
  // 点击"完场"
  await page.evaluate(() => {
    for (const el of document.querySelectorAll('a')) {
      if (el.textContent.trim() === '完场') {
        el.click();
        return;
      }
    }
  });
  await page.waitForTimeout(4000);
  
  // 获取页面文本
  const text = await page.evaluate(() => document.body.innerText);
  
  // 解析比赛结果 - 捷报比分格式
  // 格式: 联赛 \t 时间 \t 状态 \t 主队 \t 比分 \t 客队 \t ...
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
    
    // 只看完场
    if (status !== '完') continue;
    if (!home || !away || !score) continue;
    
    // 解析比分 (格式可能是 "1-2" 或 "1-2\n0-1" 其中第二行是半场)
    const scoreLines = score.split('\n');
    let ft = scoreLines[0] || '';
    let ht = scoreLines[1] || '';
    
    // 如果只有一行，尝试从其他位置获取半场
    if (!ht && parts.length > 7) {
      // 角球数据可能在后面，格式 "2-1\n1-0"
      const cornerData = parts[7]?.trim() || '';
      if (cornerData.includes('\n')) {
        // 不是半场比分，是角球
      }
    }
    
    // 提取数字
    const ftMatch = ft.match(/(\d+)-(\d+)/);
    const htMatch = ht.match(/(\d+)-(\d+)/);
    
    results.push({
      league,
      time,
      home,
      away,
      ft: ftMatch ? `${ftMatch[1]}-${ftMatch[2]}` : ft,
      ht: htMatch ? `${htMatch[1]}-${htMatch[2]}` : '未知',
      ftHome: ftMatch ? parseInt(ftMatch[1]) : null,
      ftAway: ftMatch ? parseInt(ftMatch[2]) : null,
      htHome: htMatch ? parseInt(htMatch[1]) : null,
      htAway: htMatch ? parseInt(htMatch[2]) : null
    });
  }
  
  // 筛选我们关注的比赛
  const targetTeams = ['新英格兰革命', '奥兰多城', '芝加哥火焰', '圣路易斯城', '波特诺山丘', '帕尔梅拉斯', '马纳瓜', '马塔加尔帕FC'];
  
  const filtered = results.filter(r => 
    targetTeams.includes(r.home) || targetTeams.includes(r.away)
  );
  
  console.log(JSON.stringify({ all: results.slice(0, 30), filtered }, null, 2));
  
  await browser.close();
})();
