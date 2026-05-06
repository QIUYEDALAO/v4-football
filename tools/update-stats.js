#!/usr/bin/env node
/**
 * 更新统计数据脚本
 * 用于记录验证结果，更新统计数据
 */

const fs = require('fs');
const path = require('path');

const CONFIG = {
  dataDir: '/Users/chenguoqing/.openclaw/workspace/data'
};

const DB_FILES = {
  predictions: path.join(CONFIG.dataDir, 'predictions.json'),
  results: path.join(CONFIG.dataDir, 'results.json'),
  stats: path.join(CONFIG.dataDir, 'stats.json')
};

// 更新统计
function updateStats(verificationData) {
  // 读取统计数据
  const stats = JSON.parse(fs.readFileSync(DB_FILES.stats, 'utf8'));
  
  // 读取预测数据
  const predictions = JSON.parse(fs.readFileSync(DB_FILES.predictions, 'utf8'));
  
  // 更新统计
  verificationData.forEach(v => {
    const prediction = predictions.predictions.find(p => 
      p.home === v.home && p.away === v.away
    );
    
    if (!prediction) return;
    
    stats.totalPredictions++;
    stats.verifiedPredictions++;
    
    // 按评分区间统计
    const scoreRange = prediction.score >= 100 ? '100' : 
                       prediction.score >= 90 ? '90-99' : '80-89';
    
    stats.hitRate[scoreRange].predicted++;
    if (v.htGoal) {
      stats.hitRate[scoreRange].actual++;
    }
    
    // 按联赛统计
    if (!stats.leagueStats[prediction.league]) {
      stats.leagueStats[prediction.league] = {
        total: 0,
        hit: 0
      };
    }
    stats.leagueStats[prediction.league].total++;
    if (v.htGoal) {
      stats.leagueStats[prediction.league].hit++;
    }
  });
  
  // 保存统计数据
  fs.writeFileSync(DB_FILES.stats, JSON.stringify(stats, null, 2));
  
  // 保存结果
  const results = JSON.parse(fs.readFileSync(DB_FILES.results, 'utf8'));
  results.results.push({
    date: predictions.date,
    verified: verificationData.length,
    data: verificationData
  });
  fs.writeFileSync(DB_FILES.results, JSON.stringify(results, null, 2));
  
  console.log('统计数据已更新');
  showStats();
}

// 显示统计
function showStats() {
  const stats = JSON.parse(fs.readFileSync(DB_FILES.stats, 'utf8'));
  
  console.log('\n========================================');
  console.log('统计数据');
  console.log('========================================\n');
  
  console.log(`总预测: ${stats.totalPredictions}场`);
  console.log(`已验证: ${stats.verifiedPredictions}场\n`);
  
  console.log('按评分区间统计：');
  Object.entries(stats.hitRate).forEach(([range, data]) => {
    const rate = data.predicted > 0 ? Math.round((data.actual / data.predicted) * 100) : 0;
    console.log(`  ${range}%: 预测${data.predicted}场, 命中${data.actual}场, 实际命中率${rate}%`);
  });
  
  console.log('\n按联赛统计：');
  Object.entries(stats.leagueStats).forEach(([league, data]) => {
    const rate = data.total > 0 ? Math.round((data.hit / data.total) * 100) : 0;
    console.log(`  ${league}: ${data.total}场, 命中${data.hit}场, ${rate}%`);
  });
}

// 命令行参数处理
const args = process.argv.slice(2);

if (args.length === 0) {
  showStats();
  console.log('\n使用方法：');
  console.log('  node update-stats.js \'[{"home":"主队","away":"客队","htGoal":true},...]\'');
  console.log('\n示例：');
  console.log('  node update-stats.js \'[{"home":"蔚山HD","away":"大田市民","htGoal":true}]\'');
} else {
  try {
    const data = JSON.parse(args[0]);
    updateStats(data);
  } catch (e) {
    console.error('解析错误:', e.message);
  }
}