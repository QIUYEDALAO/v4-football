const fs = require('fs');
const text = fs.readFileSync('/tmp/ft1_full.txt', 'utf-8');

const lines = text.split('\n');
const apr26Matches = [];

for (const line of lines) {
  const trimmed = line.trim();
  if (!trimmed.startsWith('A[')) continue;
  if (!trimmed.includes("'04-26'") && !trimmed.includes("'04-26,")) continue;
  
  const quoted = trimmed.match(/'([^']*)'/g);
  if (!quoted || quoted.length < 8) continue;
  
  const homeCN = quoted[0].replace(/'/g,'');
  const awayCN = quoted[3].replace(/'/g,'');
  const time = quoted[6].replace(/'/g,'');
  
  // Skip women's/youth/reserve
  const skipTerms = ['女足','女','U23','U22','U21','U20','U19','U18','U17','U16','U15','U14','青年队',
    '后备队','预备队','B队','青年','Reserve','Reserves','后备'];
  let shouldSkip = false;
  for (const t of skipTerms) {
    if (homeCN.includes(t) || awayCN.includes(t)) { shouldSkip = true; break; }
  }
  if (shouldSkip) continue;
  
  // Extract scores from the array  
  const lastQuoteIdx = trimmed.lastIndexOf("'");
  const afterQuote = trimmed.substring(lastQuoteIdx + 1);
  
  let numStr = afterQuote.replace(/^,/, '').replace(/\];?\s*$/, '');
  const nums = numStr.split(',').map(s => {
    const n = parseInt(s.trim());
    return isNaN(n) ? null : n;
  }).filter(n => n !== null);
  
  // nums = [status, homeTotal, awayTotal, halfHome, halfAway, ...]
  // But empty strings in the array mess up counting. Let me try differently.
  // Looking at the actual data: 
  // A[i]=[int,int,int,int,'','','','','','','','',status,hTotal,aTotal,halfH,halfA,corner,cornerE,cornerH,homeRank,awayRank,,'',,,'','','',,0,0,0];
  // So positions after date (index 11): 12=status, 13=homeTotal, 14=awayTotal, 15=halfHome, 16=halfAway
  
  // Better: split by comma
  const rawParts = trimmed.replace(/^A\[\d+\]=\[/, '').replace(/\];?\s*$/, '');
  const parts = rawParts.split(',');
  
  // Count which field index we're at - quoted strings span differently
  // Let me count: first 4 are unquoted ints, then 8 quoted strings, then unquoted
  let unquotedCount = 0;
  let inQuotes = false;
  let fieldIdx = 0;
  let statusIdx = -1, hTotalIdx = -1, aTotalIdx = -1, halfHIdx = -1, halfAIdx = -1;
  
  for (let i = 0; i < rawParts.length; i++) {
    const part = rawParts[i];
    
    // Count quotes to determine if starting/ending a quoted field
    const quoteCount = (part.match(/'/g) || []).length;
    
    if (!inQuotes) {
      // This is an unquoted field (or start of quoted)
      if (quoteCount === 0) {
        // pure unquoted
        fieldIdx++;
      } else if (quoteCount === 2) {
        // Complete quoted string
        fieldIdx++;
      } else if (quoteCount === 1) {
        // Start of quoted string
        inQuotes = true;
        fieldIdx++;
      }
    } else {
      // We're in a quoted string
      if (quoteCount === 1) {
        // End of quoted string
        inQuotes = false;
      }
      // Continue without incrementing fieldIdx for continuation
    }
    
    if (fieldIdx === 12) statusIdx = i;
    if (fieldIdx === 13) hTotalIdx = i;
    if (fieldIdx === 14) aTotalIdx = i;
    if (fieldIdx === 15) halfHIdx = i;
    if (fieldIdx === 16) halfAIdx = i;
  }
  
  if (statusIdx >= 0 && hTotalIdx >= 0 && halfHIdx >= 0) {
    const status = parseInt(parts[statusIdx].trim());
    const hTotal = parseInt(parts[hTotalIdx].trim());
    const aTotal = parts[aTotalIdx] ? parseInt(parts[aTotalIdx].trim()) : 0;
    const halfH = parts[halfHIdx] ? parseInt(parts[halfHIdx].trim()) : 0;
    const halfA = parts[halfAIdx] ? parseInt(parts[halfAIdx].trim()) : 0;
    
    if (status === -1 && !isNaN(hTotal) && !isNaN(aTotal)) {
      apr26Matches.push({
        time, homeCN, awayCN,
        homeTotal: hTotal, awayTotal: aTotal,
        halfHome: isNaN(halfH) ? 0 : halfH,
        halfAway: isNaN(halfA) ? 0 : halfA,
        hasHTGoal: (isNaN(halfH) ? 0 : halfH) + (isNaN(halfA) ? 0 : halfA) > 0
      });
    }
  }
}

console.log(`Found ${apr26Matches.length} Apr 26 matches\n`);

// Print them all
for (const m of apr26Matches) {
  console.log(`${m.time} ${m.homeCN} vs ${m.awayCN} → FT ${m.homeTotal}-${m.awayTotal} HT ${m.halfHome}-${m.halfAway} ${m.hasHTGoal ? '✅' : '❌'}`);
}
