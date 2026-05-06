#!/usr/bin/env node
/**
 * 验证4月29日16场推荐的半场进球结果
 * 单元格[7]格式: 角球主-客半场主-客 (如 5-50-1)
 */

const { chromium } = require('playwright');

// 4月29日推荐的16场比赛
const MATCHES = [
  { league: '日职联', time: '12:00', home: '清水鼓动', away: '长崎成功丸', rate: 100, action: '强烈推荐' },
  { league: '泰超', time: '20:00', home: '罗勇', away: '武里南联', rate: 100, action: '强烈推荐' },
  { league: '埃及超降', time: '22:00', home: '艾尔格纳', away: '哈伊赫多', rate: 100, action: '强烈推荐' },
  { league: '芬兰杯', time: '23:15', home: 'PIF帕拉宁', away: '伊洛特', rate: 100, action: '强烈推荐' },
  { league: '荷乙附', time: '00:45', home: '邓伯什', away: '阿尔梅勒城', rate: 100, action: '强烈推荐' },
  { league: '挪超', time: '01:00', home: '特罗姆瑟', away: '布兰', rate: 100, action: '强烈推荐' },
  { league: '日职乙', time: '17:00', home: '松本山雅', away: '磐田喜悦', rate: 83, action: '推荐' },
  { league: '葡超', time: '03:15', home: '葡萄牙体育', away: '通德拉', rate: 83, action: '推荐' },
  { league: '解放者杯', time: '08:30', home: '波特诺山丘', away: '帕尔梅拉斯', rate: 83, action: '谨慎' },
  { league: '日职联', time: '13:00', home: '神户胜利船', away: '大阪樱花', rate: 80, action: '推荐' },
  { league: '日职乙', time: '13:00', home: '秋田蓝色闪电', away: '山形山神', rate: 80, action: '推荐' },
  { league: '日职乙', time: '13:00', home: '大分三神', away: '熊本深红', rate: 80, action: '推荐' },
  { league: '日职联', time: '14:00', home: '浦和红钻', away: '川崎前锋', rate: 80, action: '推荐' },
  { league: '乌兹超', time: '23:00', home: '本尤德科', away: '纳曼干新春', rate: 80, action: '推荐' },
  { league: '芬超', time: '00:00', home: '图尔库国际', away: '赫尔辛基', rate: 80, action: '推荐' },
  { league: '沙特联', time: '00:00', home: '利雅得体育', away: '卡达西亚', rate: 80, action: '推荐' },
];

(async () => {
  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({ viewport: { width: 1400, height: 900 } });
  const page = await ctx.newPage();
  
  await page.goto('https://live.nowscore.com/2in1.aspx', { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.waitForTimeout(5000);
  
  // 点击完场
  await page.evaluate(() => {
    for (const el of document.querySelectorAll('a')) {
      if (el.textContent.trim() === '完场') {
        el.click();
        return;
      }
    }
  });
  await page.waitForTimeout(4000);
  
  // 获取所有完场比赛行数据
  const allRows = await page.evaluate(() => {
    const rows = document.querySelectorAll('tr');
    const results = [];
    for (const row of rows) {
      const cells = row.querySelectorAll('td');
      if (cells.length >= 8) {
        const rowData = [];
        for (let i = 0; i < cells.length; i++) {
          rowData.push(cells[i].textContent.trim().replace(/\n/g, '|'));
        }
        results.push(rowData);
      }
    }
    return results;
  });
  
  // 构建查找表
  const found = {};
  for (const row of allRows) {
    // cells[4]=主队, cells[5]=比分, cells[6]=客队, cells[7]=角球/半场
    if (row.length >= 8) {
      const home = row[4] || '';
      const score = row[5] || '';
      const away = row[6] || '';
      const extra = row[7] || ''; // 角球主-客半场主-客
      
      // 提取半场比分 (从extra的最后部分)
      // extra格式: "5-50-1" → 角球5-5, 半场0-1
      let ht = null;
      const htMatch = extra.match(/(\d+)-(\d+)$/);
      if (htMatch) {
        ht = { home: parseInt(htMatch[1]), away: parseInt(htMatch[2]) };
      }
      
      // 全场比分
      let ft = null;
      const ftMatch = score.match(/(\d+)-(\d+)/);
      if (ftMatch) {
        ft = { home: parseInt(ftMatch[1]), away: parseInt(ftMatch[2]) };
      }
      
      // 存储在查找表中，用主队名和客队名
      found[home] = { home, away, score: extra, ft, ht };
      found[away] = { home, away, score: extra, ft, ht };
    }
  }
  
  // 对每场比赛查找结果
  console.log('#  |联赛        |时间 |比赛                            |进球率|推荐     |全场    |半场    |结果');
  console.log('-'.repeat(120));
  
  let hits = 0, total = 0, unknown = 0;
  
  for (let i = 0; i < MATCHES.length; i++) {
    const m = MATCHES[i];
    
    // 先在已找到的比赛中匹配
    let matchData = found[m.home] || found[m.away];
    
    // 匹配检查
    if (matchData) {
      // 确认是同一个比赛
      const h = matchData.home;
      const a = matchData.away;
      if ((h === m.home && a === m.away) || (h === m.away && a === m.home)) {
        // OK
      } else {
        matchData = null;
      }
    }
    
    if (matchData && matchData.ht) {
      total++;
      const ht0 = matchData.ht.home;
      const ht1 = matchData.ht.away;
      const isHit = (ht0 > 0 || ht1 > 0); // 上半场有进球
      if (isHit) hits++;
      
      const status = isHit ? '✓ 命中' : '✗ 未中';
      const ftStr = matchData.ft ? `${matchData.ft.home}-${matchData.ft.away}` : '?';
      const htStr = `${ht0}-${ht1}`;
      
      console.log(`${String(i+1).padEnd(3)}|${m.league.padEnd(10)}|${m.time.padEnd(6)}|${(m.home+' vs '+m.away).padEnd(30)}|${m.rate}%${' '.repeat(5)}|${m.action.padEnd(8)}|${ftStr.padEnd(6)}|${htStr.padEnd(6)}|${status}`);
    } else {
      unknown++;
      console.log(`${String(i+1).padEnd(3)}|${m.league.padEnd(10)}|${m.time.padEnd(6)}|${(m.home+' vs '+m.away).padEnd(30)}|${m.rate}%${' '.repeat(5)}|${m.action.padEnd(8)}|${'?'.padEnd(6)}|${'?'.padEnd(6)}|? 未找到`);
    }
  }
  
  console.log(`\n可验证: ${total}场, 命中: ${hits}场, 未命中: ${total-hits}场, 未找到: ${unknown}场`);
  if (total > 0) {
    console.log(`命中率: ${(hits/total*100).toFixed(0)}%`);
  }
  
  await browser.close();
})();
