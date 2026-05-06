#!/usr/bin/env node
/**
 * V33+ 定时任务后处理 — 严格按照固定格式输出报告
 *
 * 流程: 验证昨天 → 采集今天 → 生成报告
 * 输出: 完全固定的文本格式，不经过任何模型加工
 */
const { execSync } = require('child_process');
const path = require('path');
const fs = require('fs');

const TOOLS = path.join(__dirname);

function run(cmd) {
  try {
    return execSync(cmd, { cwd: TOOLS, timeout: 600000, encoding: 'utf-8', maxBuffer: 5 * 1024 * 1024 });
  } catch (e) {
    return e.stdout || '';
  }
}

function main() {
  const date = new Date().toISOString().split('T')[0];
  const lines = [];

  // === 1. 验证昨天 ===
  lines.push('📊 昨日验证');
  const verifyOut = run('node verify-v33-auto.js --stats 2>&1');
  // 提取统计行
  for (const line of verifyOut.split('\n')) {
    if (line.includes('%') && (line.includes('|') || line.includes('/'))) {
      lines.push(line.trim());
    }
  }
  lines.push('');

  // === 2. 采集分析 ===
  const scrapeOut = run('node jiebao-scraper-v33.js 2>&1');
  const scrapeLines = scrapeOut.split('\n');
  for (const line of scrapeLines) {
    if (line.includes('工作器') || line.includes('Fatal') || line.includes('错误')) {
      lines.push(line.trim());
    }
  }

  // === 3. 生成报告 ===
  const reportOut = run('node report-v33.js 2>&1');
  lines.push(reportOut.trim());

  // === 4. 最终输出 ===
  const output = lines.join('\n').trim();
  console.log(output);

  // 也写到临时文件
  const reportFile = '/tmp/v33-daily-report.txt';
  fs.writeFileSync(reportFile, output);
}

main();
