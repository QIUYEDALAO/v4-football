#!/usr/bin/env node
/**
 * 验证4月29日推荐 - 通过搜索分析页面获取半场比分
 * 利用已知的比赛ID或通过搜索引擎获取
 */

const { chromium } = require('playwright');

const MATCHES = [
  { home: '清水鼓动', away: '长崎成功丸' },
  { home: '罗勇', away: '武里南联' },
  { home: '艾尔格纳', away: '哈伊赫多' },
  { home: 'PIF帕拉宁', away: '伊洛特' },
  { home: '邓伯什', away: '阿尔梅勒城' },
  { home: '特罗姆瑟', away: '布兰' },
  { home: '松本山雅', away: '磐田喜悦' },
  { home: '葡萄牙体育', away: '通德拉' },
  { home: '神户胜利船', away: '大阪樱花' },
  { home: '秋田蓝色闪电', away: '山形山神' },
  { home: '大分三神', away: '熊本深红' },
  { home: '浦和红钻', away: '川崎前锋' },
  { home: '本尤德科', away: '纳曼干新春' },
  { home: '图尔库国际', away: '赫尔辛基' },
  { home: '利雅得体育', away: '卡达西亚' },
];

(async () => {
  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({ viewport: { width: 1400, height: 900 } });
  const page = await ctx.newPage();
  
  await page.goto('https://live.nowscore.com/2in1.aspx', { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.waitForTimeout(5000);
  
  // 先保留在当前页面（今日未开赛），点击每个主队查看历史数据
  // 但历史数据不在这个页面...
  
  // 换个思路：直接点开每个主队 → 进入详情页 → 找到半场比分
  const results = [];
  
  for (let i = 0; i < MATCHES.length; i++) {
    const m = MATCHES[i];
    console.log(`[${i+1}/${MATCHES.length}] ${m.home} vs ${m.away}`);
    
    // 在主页面点击主队
    const clicked = await page.evaluate((name) => {
      for (const l of document.querySelectorAll('a')) {
        if (l.textContent.trim() === name) {
          l.click();
          return true;
        }
      }
      return false;
    }, m.home);
    
    if (!clicked) {
      // 尝试点击客队
      const clicked2 = await page.evaluate((name) => {
        for (const l of document.querySelectorAll('a')) {
          if (l.textContent.trim() === name) {
            l.click();
            return true;
          }
        }
        return false;
      }, m.away);
      if (!clicked2) {
        console.log(`  未找到 ${m.home} 或 ${m.away}`);
        results.push({ ...m, ht: null, note: 'not found on page' });
        continue;
      }
    }
    
    await page.waitForTimeout(2500);
    
    const pages = page.context().pages();
    if (pages.length < 2) {
      console.log(`  详情页未打开`);
      results.push({ ...m, ht: null, note: 'detail page not opened' });
      continue;
    }
    
    const np = pages[pages.length - 1];
    await np.waitForTimeout(2000);
    
    // 尝试获取比赛详情URL
    const detailUrl = await np.evaluate(() => window.location.href);
    
    // 点击数据分析
    await np.evaluate(() => {
      for (const l of document.querySelectorAll('a')) {
        if (l.textContent.trim() === '数据分析') { l.click(); return; }
      }
    });
    await np.waitForTimeout(2000);
    
    // 点击简
    try {
      await np.evaluate(() => {
        for (const l of document.querySelectorAll('a,span')) {
          if (l.textContent.trim() === '简') { l.click(); return; }
        }
      });
      await np.waitForTimeout(1500);
    } catch (e) {}
    
    // 获取页面文本，查找对战往绩中的半场比分
    const dt = await np.evaluate(() => document.body.innerText);
    
    // 查找半场比分模式
    let ht = null;
    for (const line of dt.split('\n')) {
      // 查找 "(X-Y)" 格式的比分，后面可能有半场标记
      const m2 = line.match(/\((\d+)-(\d+)\)/);
      if (m2) {
        // 这是历史交锋中的比分（可能是全场）
        // 实际半场比分在"对战往绩"区域
      }
    }
    
    // 从URL和文本中提取比赛ID
    const matchId = detailUrl.match(/id=(\d+)/)?.[1] || detailUrl.match(/\/(\d+)\.html/)?.[1];
    
    console.log(`  URL: ${detailUrl.substring(0, 100)}, matchId: ${matchId || 'unknown'}`);
    
    // 尝试直接读取比赛页面获取半场比分
    // 比赛详情URL模式: https://live.nowscore.com/match/{id}.html
    if (matchId) {
      try {
        await np.goto(`https://live.nowscore.com/match/${matchId}.html`, { waitUntil: 'domcontentloaded', timeout: 10000 });
        await np.waitForTimeout(2000);
        const matchDt = await np.evaluate(() => document.body.innerText);
        
        // 尝试找半场比分
        for (const line of matchDt.split('\n')) {
          const htM = line.match(/半场[：:\s]*(\d+)\s*[-–]\s*(\d+)/i);
          if (htM) {
            ht = { home: parseInt(htM[1]), away: parseInt(htM[2]) };
            break;
          }
          const htM2 = line.match(/HT\s*(\d+)\s*[-–]\s*(\d+)/i);
          if (htM2 && !ht) {
            ht = { home: parseInt(htM2[1]), away: parseInt(htM2[2]) };
          }
        }
      } catch (e) {
        console.log(`  比赛页面读取失败: ${e.message}`);
      }
    }
    
    console.log(`  半场比分: ${ht ? `${ht.home}-${ht.away}` : '未知'}`);
    results.push({ ...m, ht, note: ht ? 'found' : 'not found' });
    
    // 关闭详情页
    try { await np.close(); } catch (e) {}
    await page.waitForTimeout(500);
  }
  
  console.log('\n=== 结果汇总 ===');
  for (const r of results) {
    const htStr = r.ht ? `${r.ht.home}-${r.ht.away}` : '无数据';
    const isHit = r.ht ? (r.ht.home > 0 || r.ht.away > 0) : null;
    const status = isHit === true ? '✓' : isHit === false ? '✗' : '?';
    console.log(`${status} ${r.home.padEnd(12)} vs ${r.away.padEnd(12)} 半场:${htStr}`);
  }
  
  await browser.close();
})();
