// 从近期战绩部分提取上半场进球率（优化版）
function extractRecentRate(section) {
  const matches = [];
  // 匹配格式：2-3(1-0) 或 0-0(0-0)
  const regex = /(\d+)\s*[-–]\s*(\d+)\s*\(\s*(\d+)\s*[-–]\s*(\d+)\s*\)/g;
  let match;
  
  while ((match = regex.exec(section)) !== null && matches.length < 10) {
    matches.push({
      htHome: parseInt(match[3]),
      htAway: parseInt(match[4])
    });
  }
  
  if (matches.length === 0) return null;
  
  let htGoals = 0;
  matches.forEach(m => {
    if (m.htHome + m.htAway > 0) htGoals++;
  });
  
  return Math.round((htGoals / matches.length) * 100);
}

// 从页面提取所有数据（优化版）
function extractMatchData(pageText, homeTeam, awayTeam) {
  const result = {
    h2hRate: null,
    homeRecentRate: null,
    awayRecentRate: null
  };
  
  // 1. 提取历史交锋上半场进球率
  const h2hSection = pageText.split('對戰往績')[1];
  if (h2hSection) {
    // 找到"近期戰績"作为结束标记
    const endIndex = h2hSection.indexOf('近期戰績');
    const h2hText = endIndex !== -1 ? h2hSection.substring(0, endIndex) : h2hSection;
    result.h2hRate = extractRecentRate(h2hText);
  }
  
  // 2. 提取近期战绩上半场进球率
  const recentSection = pageText.split('近期戰績')[1];
  if (recentSection) {
    // 找到主队近期战绩
    const homeIdx = recentSection.indexOf(homeTeam);
    const awayIdx = recentSection.indexOf(awayTeam);
    
    if (homeIdx !== -1) {
      // 主队近期数据：从主队名称到下一个球队名称或"數據對比"
      let homeEndIdx = awayIdx !== -1 && awayIdx > homeIdx ? awayIdx : recentSection.indexOf('數據對比');
      if (homeEndIdx === -1) homeEndIdx = recentSection.length;
      const homeSection = recentSection.substring(homeIdx, homeEndIdx);
      result.homeRecentRate = extractRecentRate(homeSection);
    }
    
    if (awayIdx !== -1) {
      // 客队近期数据：从客队名称到"數據對比"
      let awayEndIdx = recentSection.indexOf('數據對比');
      if (awayEndIdx === -1) awayEndIdx = recentSection.length;
      const awaySection = recentSection.substring(awayIdx, awayEndIdx);
      result.awayRecentRate = extractRecentRate(awaySection);
    }
  }
  
  return result;
}