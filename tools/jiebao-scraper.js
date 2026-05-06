#!/usr/bin/env node
/**
 * 捷报比分数据采集器
 * 自动点击比赛，提取分析数据，保存为文本
 */

const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

// 配置
const CONFIG = {
  baseUrl: 'https://live.nowscore.com/2in1.aspx',
  outputFile: '/tmp/jiebao-analysis.txt',
  headless: false, // 显示浏览器窗口
  timeout: 30000
};

// 主流联赛关键词
const MAJOR_LEAGUES = [
  '英超', '西甲', '意甲', '德甲', '法甲',
  '巴甲', '阿甲', '日职', '韩K', '澳超',
  '美职业', '墨超', '葡超', '荷甲', '俄超',
  '土超', '比甲', '奥甲', '苏超', '瑞典超', '挪超'
];

async function main() {
  console.log('========================================');
  console.log('捷报比分数据采集器');
  console.log('========================================\n');

  // 设置超时自动关闭（5分钟）
  const timeout = setTimeout(() => {
    console.log('\n超时自动关闭...');
    process.exit(0);
  }, 5 * 60 * 1000);

  const browser = await chromium.launch({
    headless: CONFIG.headless,
    slowMo: 100
  });

  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 }
  });

  const page = await context.newPage();

  try {
    // 1. 访问捷报比分
    console.log('步骤1: 访问捷报比分...');
    await page.goto(CONFIG.baseUrl, { waitUntil: 'networkidle', timeout: CONFIG.timeout });
    await page.waitForTimeout(3000);

    // 2. 提取未开赛比赛
    console.log('步骤2: 提取未开赛比赛...');
    const matches = await page.evaluate((majorLeagues) => {
      const results = [];
      const rows = document.querySelectorAll('tr');

      rows.forEach(row => {
        const cells = Array.from(row.querySelectorAll('td'));
        if (cells.length >= 7) {
          const league = cells[1]?.textContent.trim();
          const time = cells[2]?.textContent.trim();
          const status = cells[3]?.textContent.trim();
          const home = cells[4]?.textContent.trim();
          const score = cells[5]?.textContent.trim();
          const away = cells[6]?.textContent.trim();

          // 未开赛比赛
          if (status === '' || status === '-' || status === '阵容' || score === '-' || score === '阵容') {
            // 检查是否主流联赛
            const isMajor = majorLeagues.some(l => league.includes(l));

            // 提取matchId
            const rowHtml = row.innerHTML;
            const match = rowHtml.match(/(?:detail|analysis)\/(\d{7,})\.html/);
            const matchId = match ? match[1] : '';

            results.push({
              league,
              time,
              home,
              away,
              matchId,
              isMajor,
              row: Array.from(rows).indexOf(row)
            });
          }
        }
      });

      return results;
    }, MAJOR_LEAGUES);

    console.log(`找到 ${matches.length} 场未开赛比赛`);
    console.log(`其中主流联赛: ${matches.filter(m => m.isMajor).length} 场\n`);

    // 3. 分析每场比赛
    console.log('步骤3: 分析比赛数据...\n');
    const results = [];

    for (let i = 0; i < Math.min(matches.length, 50); i++) {
      const match = matches[i];

      // 只分析主流联赛
      if (!match.isMajor) {
        console.log(`跳过: [${match.league}] ${match.home} vs ${match.away} (非主流联赛)`);
        continue;
      }

      console.log(`分析: [${match.league}] ${match.time} ${match.home} vs ${match.away}`);

      try {
        // 点击比赛行
        await page.evaluate((rowIndex) => {
          const rows = document.querySelectorAll('tr');
          if (rows[rowIndex]) {
            rows[rowIndex].click();
          }
        }, match.row);

        await page.waitForTimeout(1000);

        // 查找分析按钮
        const analysisButton = await page.$('text=数据分析, text=分析, text=历史交锋');

        if (analysisButton) {
          await analysisButton.click();
          await page.waitForTimeout(2000);

          // 提取H2H数据
          const h2hData = await page.evaluate(() => {
            const matches = [];
            const text = document.body.innerText;
            const lines = text.split('\n');

            for (const line of lines) {
              // 匹配比分格式: 2-1 (1-0)
              const match = line.match(/(\d+)\s*-\s*(\d+)\s*\(\s*(\d+)\s*-\s*(\d+)\s*\)/);
              if (match) {
                matches.push({
                  fullHome: parseInt(match[1]),
                  fullAway: parseInt(match[2]),
                  htHome: parseInt(match[3]),
                  htAway: parseInt(match[4])
                });
                if (matches.length >= 10) break;
              }
            }

            return matches;
          });

          if (h2hData.length > 0) {
            // 计算上半场进球率
            let htGoals = 0;
            h2hData.forEach(m => {
              if (m.htHome + m.htAway > 0) htGoals++;
            });

            const rate = Math.round((htGoals / h2hData.length) * 100);

            console.log(`  历史交锋: ${h2hData.length}场`);
            console.log(`  上半场进球: ${htGoals}场`);
            console.log(`  上半场进球率: ${rate}%`);
            console.log(`  推荐: ${rate >= 70 ? '⭐⭐⭐' : rate >= 60 ? '⭐⭐' : '❌'}\n`);

            results.push({
              league: match.league,
              time: match.time,
              home: match.home,
              away: match.away,
              matchId: match.matchId,
              h2hCount: h2hData.length,
              htGoals,
              rate,
              h2hData
            });
          } else {
            console.log(`  无历史交锋数据\n`);
          }

          // 关闭弹窗
          await page.keyboard.press('Escape');
          await page.waitForTimeout(500);

        } else {
          console.log(`  未找到分析按钮\n`);
        }

      } catch (e) {
        console.log(`  错误: ${e.message}\n`);
      }

      // 避免请求过快
      await page.waitForTimeout(500);
    }

    // 4. 保存结果
    console.log('步骤4: 保存结果...');

    const output = {
      date: new Date().toISOString().split('T')[0],
      timestamp: new Date().toISOString(),
      total: results.length,
      matches: results
    };

    // 保存JSON
    fs.writeFileSync(
      '/tmp/jiebao-analysis.json',
      JSON.stringify(output, null, 2)
    );

    // 保存文本（用于发送给AI）
    let textOutput = `捷报比分分析报告\n`;
    textOutput += `日期: ${output.date}\n`;
    textOutput += `分析场次: ${results.length}场\n\n`;

    textOutput += `=== 强烈推荐（≥70%）===\n\n`;
    results.filter(r => r.rate >= 70).forEach((r, i) => {
      textOutput += `${i + 1}. [${r.league}] ${r.time} ${r.home} vs ${r.away}\n`;
      textOutput += `   上半场进球率: ${r.rate}% (${r.htGoals}/${r.h2hCount}场)\n`;
      textOutput += `   历史交锋:\n`;
      r.h2hData.slice(0, 5).forEach(m => {
        textOutput += `     ${m.fullHome}-${m.fullAway} (半场${m.htHome}-${m.htAway})\n`;
      });
      textOutput += `\n`;
    });

    textOutput += `=== 可考虑（60-69%）===\n\n`;
    results.filter(r => r.rate >= 60 && r.rate < 70).forEach((r, i) => {
      textOutput += `${i + 1}. [${r.league}] ${r.time} ${r.home} vs ${r.away} - ${r.rate}%\n`;
    });

    fs.writeFileSync(CONFIG.outputFile, textOutput);

    console.log(`\n结果已保存:`);
    console.log(`  JSON: /tmp/jiebao-analysis.json`);
    console.log(`  文本: ${CONFIG.outputFile}`);

    // 5. 输出统计
    console.log('\n========================================');
    console.log('分析完成');
    console.log('========================================\n');

    const recommended = results.filter(r => r.rate >= 70);
    const consider = results.filter(r => r.rate >= 60 && r.rate < 70);

    console.log(`强烈推荐: ${recommended.length}场`);
    console.log(`可考虑: ${consider.length}场`);
    console.log(`不推荐: ${results.length - recommended.length - consider.length}场`);

    // 等待用户确认后关闭
    console.log('\n按回车键关闭浏览器...');
    await new Promise(resolve => {
      process.stdin.once('data', resolve);
    });

  } catch (e) {
    console.error('错误:', e.message);
  } finally {
    await browser.close();
  }
}

main().catch(console.error);
