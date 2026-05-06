#!/usr/bin/env node
/**
 * 获取比赛半场比分 - v3
 * 点击比赛进入详情页获取半场比分
 */

const { chromium } = require('playwright');

const TARGET_MATCHES = [
  { league: '美公开赛', home: '新英格兰革命', away: '奥兰多城' },
  { league: '美公开赛', home: '芝加哥火焰', away: '圣路易斯城' },
  { league: '解放者杯', home: '波特诺山丘', away: '帕尔梅拉斯' },
  { league: '尼拉甲附', home: '马纳瓜', away: '马塔加尔帕FC' }
];

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
  
  const results = [];
  
  for (const target of TARGET_MATCHES) {
    console.log(`查找: ${target.home} vs ${target.away}`);
    
    // 点击主队进入详情页
    const clicked = await page.evaluate((name) => {
      for (const l of document.querySelectorAll('a')) {
        if (l.textContent.trim() === name) {
          l.click();
          return true;
        }
      }
      return false;
    }, target.home);
    
    if (!clicked) {
      console.log(`  未找到 ${target.home}`);
      results.push({ ...target, ht: '未找到', ft: '未找到', hit: null });
      continue;
    }
    
    await page.waitForTimeout(3000);
    
    const pages = page.context().pages();
    if (pages.length < 2) {
      console.log(`  详情页未打开`);
      results.push({ ...target, ht: '未打开', ft: '未打开', hit: null });
      continue;
    }
    
    const detailPage = pages[pages.length - 1];
    await detailPage.waitForTimeout(2000);
    
    // 获取详情页文本
    const detailText = await detailPage.evaluate(() => document.body.innerText);
    
    // 解析半场比分 - 捷报比分格式: "半场 1-0" 或 "HT 1-0"
    let htScore = null;
    let ftScore = null;
    
    for (const line of detailText.split('\n')) {
      // 半场比分
      const htMatch = line.match(/半场[：:\s]*(\d+)\s*[-–]\s*(\d+)/i);
      if (htMatch) {
        htScore = { home: parseInt(htMatch[1]), away: parseInt(htMatch[2]) };
      }
      
      // HT格式
      const htMatch2 = line.match(/HT\s*(\d+)\s*[-–]\s*(\d+)/i);
      if (htMatch2 && !htScore) {
        htScore = { home: parseInt(htMatch2[1]), away: parseInt(htMatch2[2]) };
      }
      
      // 全场比分
      const ftMatch = line.match(/全场[：:\s]*(\d+)\s*[-–]\s*(\d+)/i);
      if (ftMatch) {
        ftScore = { home: parseInt(ftMatch[1]), away: parseInt(ftMatch[2]) };
      }
      
      // 完场格式
      const ftMatch2 = line.match(/完场[：:\s]*(\d+)\s*[-–]\s*(\d+)/i);
      if (ftMatch2 && !ftScore) {
        ftScore = { home: parseInt(ftMatch2[1]), away: parseInt(ftMatch2[2]) };
      }
    }
    
    // 如果没找到，尝试从页面结构提取
    if (!htScore) {
      const scoreData = await detailPage.evaluate(() => {
        // 查找比分表格
        const tables = document.querySelectorAll('table');
        for (const table of tables) {
          const rows = table.querySelectorAll('tr');
          for (const row of rows) {
            const cells = row.querySelectorAll('td');
            const text = row.textContent;
            if (text.includes('半场') || text.includes('HT')) {
              // 尝试提取数字
              const nums = text.match(/\d+/g);
              if (nums && nums.length >= 2) {
                return { home: parseInt(nums[0]), away: parseInt(nums[1]) };
              }
            }
          }
        }
        return null;
      });
      if (scoreData) htScore = scoreData;
    }
    
    // 判断是否命中（上半场有进球 = 非0-0）
    const hit = htScore ? (htScore.home > 0 || htScore.away > 0) : null;
    
    results.push({
      ...target,
      ht: htScore ? `${htScore.home}-${htScore.away}` : '未知',
      ft: ftScore ? `${ftScore.home}-${ftScore.away}` : '未知',
      htHome: htScore?.home,
      htAway: htScore?.away,
      hit
    });
    
    console.log(`  半场: ${htScore ? `${htScore.home}-${htScore.away}` : '未知'}, 全场: ${ftScore ? `${ftScore.home}-${ftScore.away}` : '未知'}, 命中: ${hit === true ? '✓' : hit === false ? '✗' : '未知'}`);
    
    // 关闭详情页
    try { await detailPage.close(); } catch (e) {}
    await page.waitForTimeout(1000);
  }
  
  await browser.close();
  
  console.log('\n=== 验证结果汇总 ===');
  console.log(JSON.stringify(results, null, 2));
})();