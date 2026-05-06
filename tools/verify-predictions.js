#!/usr/bin/env node
/**
 * 预测验证脚本
 * 用于验证昨天的预测结果，更新统计数据
 */

const fs = require('fs');
const path = require('path');

const CONFIG = {
  dataDir: '/Users/chenguoqing/.openclaw/workspace/data',
  baseUrl: 'https://live.nowscore.com/2in1.aspx'
};

const DB_FILES = {
  predictions: path.join(CONFIG.dataDir, 'predictions.json'),
  results: path.join(CONFIG.dataDir, 'results.json'),
  stats: path.join(CONFIG.dataDir, 'stats.json')
};

// 获取昨天的日期
function getYesterday() {
  const date = new Date();
  date.setDate(date.getDate() - 1);
  return date.toISOString().split('T')[0];
}

// 验证昨天的预测
async function verifyYesterday() {
  console.log('========================================');
  console.log('预测验证脚本');
  console.log('========================================\n');

  // 检查预测文件
  if (!fs.existsSync(DB_FILES.predictions)) {
    console.log('没有找到预测数据');
    return;
  }

  const predictions = JSON.parse(fs.readFileSync(DB_FILES.predictions, 'utf8'));
  
  if (predictions.predictions.length === 0) {
    console.log('没有预测数据');
    return;
  }

  console.log(`验证日期: ${predictions.date}`);
  console.log(`预测场次: ${predictions.predictions.length}场\n`);

  // 显示昨天的预测
  console.log('昨天的预测：\n');
  
  predictions.predictions.forEach((p, i) => {
    console.log(`${i + 1}. [${p.league}] ${p.time} ${p.home} vs ${p.away}`);
    console.log(`   综合评分: ${p.score}% | 推荐: ${p.recommend}`);
  });

  console.log('\n========================================');
  console.log('请手动验证比赛结果');
  console.log('========================================\n');

  console.log('验证方法：');
  console.log('1. 访问捷报比分查看昨天比赛结果');
  console.log('2. 记录每场比赛上半场是否有进球');
  console.log('3. 运行 update-stats.js 更新统计数据');
}

verifyYesterday().catch(console.error);