const fs = require('fs');
const text = fs.readFileSync('/tmp/ft1_full.txt', 'utf-8');

// Simple approach: find all A[N]= lines with 04-26 and manually parse the obvious ones
const lines = text.split('\n');
for (const line of lines) {
  const trimmed = line.trim();
  if (!trimmed.startsWith('A[')) continue;
  if (!trimmed.includes("'04-26'")) continue;
  
  // Get the team names from the first 4 Chinese quote pairs
  const firstQuote = trimmed.indexOf("'");
  const restAfterFirstQuote = trimmed.substring(firstQuote);
  
  const quoted = restAfterFirstQuote.match(/'[^']*'/g);
  if (!quoted || quoted.length < 4) continue;
  
  const homeCN = quoted[0].replace(/'/g, '');
  const awayCN = quoted[3].replace(/'/g, '');
  const homeEN = quoted[2].replace(/'/g, '');
  const awayEN = quoted[5].replace(/'/g, '');
  const time = quoted[6].replace(/'/g, '');
  
  // Skip women/youth
  if (homeCN.includes('女') || awayCN.includes('女') || 
      homeEN.includes('(W)') || awayEN.includes('(W)') ||
      homeCN.includes('青年') || awayCN.includes('青年') ||
      homeCN.includes('U') || awayCN.includes('U') ||
      homeCN.includes('后备') || awayCN.includes('后备')) continue;
  
  // Find the score numbers
  // The format after all quoted strings is: ,-1,homeTotal,awayTotal,halfHome,halfAway,...
  // Simplified: find the comma positions around the 8th quote  
  const quote8 = trimmed.indexOf("'", trimmed.indexOf("'") + 1);
  // Actually just find patterns like ,-1, or ,0, after the last quote
  
  // Count: there are 8 single-quoted words before scores
  // homeCN(0),homeTW(1),homeEN(2),awayCN(3),awayTW(4),awayEN(5),time(6),date(7)
  // After date, the next values are: status,homeTotal,awayTotal,...
  
  // Find the 8th quoted string
  let idx = -1;
  for (let q = 0; q < 8; q++) {
    idx = trimmed.indexOf("'", idx + 1);
    idx = trimmed.indexOf("'", idx + 1); // closing quote
  }
  
  const afterQuotes = trimmed.substring(idx + 1).trim();
  // afterQuotes starts with comma
  const nums = afterQuotes.replace(/^,/, '').split(',');
  
  // nums[0] = status (-1 for finished)
  // nums[1] = home total goals
  // nums[2] = away total goals
  // nums[3] = half time home goals
  // nums[4] = half time away goals
  
  const status = parseInt(nums[0]);
  if (status !== -1) continue;
  
  const homeTotal = parseInt(nums[1]);
  const awayTotal = parseInt(nums[2]);
  const halfHome = parseInt(nums[3]);
  const halfAway = parseInt(nums[4]);
  
  const isNaN = (n) => Number.isNaN(n);
  
  if (!Number.isNaN(homeTotal) && !Number.isNaN(awayTotal)) {
    const hh = Number.isNaN(halfHome) ? 0 : halfHome;
    const ha = Number.isNaN(halfAway) ? 0 : halfAway;
    console.log(`${time} ${homeCN} vs ${awayCN} → FT ${homeTotal}-${awayTotal} HT ${hh}-${ha} ✅${hh+ha > 0}`);
  }
}
