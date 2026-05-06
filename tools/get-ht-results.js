#!/usr/bin/env node
/**
 * 获取比赛半场比分 - 用于验证预测
 */

const { chromium } = require('playwright');

const TARGET_MATCHES = [
  { home: '新英格兰革命', away: '奥兰多城' },
  { home: '芝加哥火焰', away: '圣路易斯城' },
  { home: '波特诺山丘', away: '帕尔梅拉斯' },
  { home: '马纳瓜', away: '马塔加尔帕FC' }
];

(async () => {
  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await ctx.newPage();
  
  await page.goto('https://live.nowscore.com/2in1.aspx', { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.waitForTimeout(5000);
  
  // 点击"完场"
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
  
  const results = [];
  
  for (const target of TARGET_MATCHES) {
    console.log(`查找: ${target.home} vs ${target.away}`);
    
    // 点击主队
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
      continue;
    }
    
    await page.waitForTimeout(3000);
    
    const pages = page.context().pages();
    if (pages.length < 2) {
      console.log(`  新标签页未打开`);
      continue;
    }
    
    const np = pages[pages.length - 1];
    await np.waitForTimeout(2000);
    
    // 获取页面文本
    const text = await np.evaluate(() => document.body.innerText);
    
    // 查找半场比分
    let htScore = null;
    for (const line of text.split('\n')) {
      // 常见格式: "半场 1-0" 或 "HT 1-0" 或 "半场比分 1-0"
      const htMatch = line.match(/半场[：:\s]*(\d+)\s*-\s*(\d+)/i);
      if (htMatch) {
        htScore = `${htMatch[1]}-${htMatch[2]}`;
        break;
      }
      // 或者 "HT 1-0"
      const htMatch2 = line.match(/HT\s*(\d+)\s*-\s*(\d+)/i);
      if (htMatch2) {
        htScore = `${htMatch2[1]}-${htMatch2[2]}`;
        break;
      }
    }
    
    // 如果没找到，尝试从页面结构提取
    if (!htScore) {
      // 尝试从表格中提取
      const scoreData = await np.evaluate(() => {
        // 查找包含"半场"的行
        const rows = document.querySelectorAll('tr');
        for (const row of rows) {
          const cells = row.querySelectorAll('td');
          if (cells.length >= 3) {
            const first = cells[0].textContent.trim();
            if (first.includes('半场') || first === 'HT') {
              // 第二和第三个单元格可能是比分
              const scoreText = cells[1].textContent.trim() + '-' + cells[2].textContent.trim();
              return scoreText;
            }
          }
        }
        return null;
      });
      if (scoreData) htScore = scoreData;
    }
    
    // 全场比分
    let ftScore = null;
    for (const line of text.split('\n')) {
      const ftMatch = line.match(/全场[：:\s]*(\d+)\s*-\s*(\d+)/i);
      if (ftMatch) {
        ftScore = `${ftMatch[1]}-${ftMatch[2]}`;
        break;
      }
    }
    
    results.push({
      home: target.home,
      away: target.away,
      ht: htScore || '未知',
      ft: ftScore || '未知'
    });
    
    console.log(`  半场: ${htScore || '未知'}, 全场: ${ftScore || '未知'}`);
    
    // 关闭标签页
    try { await np.close(); } catch (e) {}
    await page.waitForTimeout(1000);
  }
  
  await browser.close();
  
  console.log('\n=== 结果汇总 ===');
  console.log(JSON.stringify(results, null, 2));
})();
