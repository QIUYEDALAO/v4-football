#!/usr/bin/env node
/**
 * Flashscore 数据采集器 v1 — 取代捷报比分
 * 
 * 数据源: https://www.flashscore.com
 * 功能:
 *   1. 获取今日所有未开赛比赛列表（按联赛）
 *   2. 对每场比赛采集 H2H 历史交锋（含半场比分）
 *   3. 采集近期战绩
 *   4. 采集盘口（大小球、亚盘）
 *   5. 计算上半场进球率 → 推荐
 * 
 * 用法: node tools/flashscore-scraper-v1.js
 */

const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const PRED_FILE = path.join(__dirname, '..', 'data', '验证存档', 'flashscore-v1', 'predictions.json');

// ===== 联赛白名单 =====
const ALLOWED_LEAGUES = [
  'Premier League', // 英超
  'LaLiga', 'La Liga', // 西甲
  'Serie A', // 意甲
  'Bundesliga', // 德甲
  'Ligue 1', // 法甲
  'Eredivisie', // 荷甲
  'Liga Portugal', 'Primeira Liga', // 葡超
  'Jupiler Pro League', 'Belgian Pro League', // 比甲
  'Scottish Premiership', // 苏超
  'Super Lig', // 土超
  'Premier League', // 俄超 - 实际叫 Russian Premier League
  'Eliteserien', // 挪超
  'Allsvenskan', // 瑞典超
  'Superliga', // 丹超
  'Bundesliga', // 奥甲 - Austrian Bundesliga
  'Super League', // 瑞士超
  'Ekstraklasa', // 波兰超
  'Super Liga', // 塞尔超
  'HNL', // 克亚甲 - Hrvatska NL
  'Liga I', // 罗甲
  'Danish Superliga', // 丹麦超
  'Ukrainian Premier League', // 乌超
  'Icelandic League', 'Besta deild', // 冰岛超
  'Championship', // 英冠
  '2. Bundesliga', // 德乙
  'LaLiga 2', 'La Liga 2', // 西乙
  'Serie B', // 意乙
  'Ligue 2', // 法乙
  'FNL', // 俄甲
  'J1 League', // 日职联
  'J2 League', // 日职乙
  'K League 1', // 韩K
  'A-League', // 澳超
  'MLS', // 美职业
  'Liga MX', // 墨西联
  'Brasileiro', 'Serie A', // 巴西甲
  'Liga Profesional', // 阿甲
  'Indonesian Liga', 'Liga 1', // 印尼超
  'Indian Super League', // 印度超
  'Saudi Pro League', // 沙特联
  'Primera Division', // 乌拉甲
  'Primera Division', // 秘鲁甲 - Peruvian
  'Primera Division', // 玻利甲
  'Egyptian Premier League', // 埃及超
  'League of Ireland', // 爱超
  'Finnish League', 'Veikkausliiga', // 芬超
];

// ===== 忽略的词语（友谊赛、杯赛等） =====
const IGNORE_KEYWORDS = ['Cup', 'Women', 'U19', 'U20', 'U21', 'U23', 'U17', 'Youth', 'Reserve', 'II', 'III', 'Friendlies'];

function isLeagueAllowed(league) {
  if (!league) return false;
  // 如果有忽略关键词，直接跳过
  for (const kw of IGNORE_KEYWORDS) {
    if (league.includes(kw)) return false;
  }
  // 对白名单进行前缀匹配
  for (const allowed of ALLOWED_LEAGUES) {
    if (league.startsWith(allowed)) return true;
  }
  return false;
}

async function pageWait(page, ms) {
  try { await page.waitForTimeout(ms); } catch (e) {}
}

async function main() {
  const start = Date.now();
  console.log('='.repeat(70));
  console.log('Flashscore 数据采集器 v1');
  console.log('启动: ' + new Date().toLocaleString('zh-CN', {timeZone:'Asia/Shanghai'}));
  console.log('='.repeat(70) + '\n');

  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({
    userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    viewport: { width: 1920, height: 1080 }
  });

  // === Step 1: 获取今日所有比赛 ===
  console.log('📡 获取今日赛程...');
  await page.goto('https://www.flashscore.com', { 
    waitUntil: 'networkidle', timeout: 30000 
  }).catch(() => {});
  await pageWait(page, 5000);

  // 提取页面上的所有比赛
  const rawData = await page.evaluate(() => {
    const text = document.body.innerText;
    const lines = text.split('\n');
    
    // 解析比赛行: 时间 主队 vs 客队
    const matches = [];
    let currentLeague = null;
    let currentCountry = null;
    
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i].trim();
      
      // 检测联赛标题: "联赛名 COUNTRY:"
      if (line.endsWith(':') && line.length > 3 && line.length < 50 && !line.includes('http')) {
        const countryMatch = i > 0 ? lines[i-1] : '';
        if (countryMatch && countryMatch === countryMatch.toUpperCase() && countryMatch.length > 2 && countryMatch.length < 30) {
          currentCountry = countryMatch;
        }
        currentLeague = line.replace(':', '').trim();
        continue;
      }
      
      // 检测比赛: "时间 主队 客队" 或 "时间 vs 客队"
      // Flashscore格式: "HH:MM 主队 客队" 或 "HH:MM 主队 vs 客队" 或 "HH:MM PREVIEW"
      const timeMatch = line.match(/^(\d{2}:\d{2})\s+(.+)/);
      if (timeMatch) {
        const time = timeMatch[1];
        const rest = timeMatch[2];
        
        // 排除状态行 Finished等
        if (rest === 'PREVIEW' || !rest.includes(' ')) continue;
        
        // 解析主客队: "主队 客队" 或 "主队 vs 客队"
        let home = '', away = '';
        const vsIdx = rest.lastIndexOf(' ');
        if (vsIdx > 0) {
          home = rest.substring(0, vsIdx).trim();
          // 客队应该是下一个行或者同一行末尾
        }
        
        matches.push({
          league: currentLeague,
          country: currentCountry,
          time,
          home,
          away: rest.split(' ').pop() || '',
          raw: line
        });
      }
    }
    
    return matches;
  });
  
  console.log(`  找到 ${rawData.length} 条比赛记录`);
  
  // 过滤白名单联赛
  const filtered = rawData.filter(m => isLeagueAllowed(m.league));
  console.log(`  白名单内: ${filtered.length} 场\n`);
  
  // 按联赛分组显示
  const byLeague = {};
  filtered.forEach(m => {
    if (!byLeague[m.league]) byLeague[m.league] = [];
    byLeague[m.league].push(m);
  });
  
  for (const [league, ms] of Object.entries(byLeague).sort()) {
    console.log(`  ✅ ${league} (${ms.length}场):`);
    ms.forEach(m => console.log(`     ${m.time} ${m.home} vs ${m.away}`));
  }
  
  // 后续步骤: 
  // Step 2: 获取每场比赛的 H2H 数据
  // Step 3: 获取每场比赛的盘口
  // Step 4: 计算并推荐
  
  const elapsed = ((Date.now() - start) / 1000).toFixed(0);
  console.log(`\n✅ 完成 (${elapsed}s)`);
  
  await browser.close();
}

main().catch(e => {
  console.error('❌ 错误:', e.message);
  process.exit(1);
});
