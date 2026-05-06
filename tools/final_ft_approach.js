// The key insight is:
// ft1.js has data for both 04-25 and 04-26
// But our V17 matches have completely different team names in the data
// Let me look more carefully at the raw data to find ALL Apr 26 matches

const fs = require('fs');
const text = fs.readFileSync('/tmp/ft1_full.txt', 'utf-8');

// Extract ALL Apr 26 matches from A array with full data
const lines = text.split('\n');
let count = 0;

console.log('=== ALL Apr 26 MATCHES IN ft1.js ===');
for (const line of lines) {
  const trimmed = line.trim();
  if (trimmed.startsWith('A[') && (trimmed.includes("'04-26'") || trimmed.includes("'04-26,"))) {
    // Extract quoted strings
    const quoted = trimmed.match(/'([^']*)'/g);
    if (!quoted || quoted.length < 8) continue;
    
    const homeCN = quoted[0].replace(/'/g,'');
    const awayCN = quoted[3].replace(/'/g,'');
    const homeEN = quoted[2].replace(/'/g,'');
    const awayEN = quoted[5].replace(/'/g,'');
    const time = quoted[6].replace(/'/g,'');
    
    // Skip youth/women matches
    if (homeCN.includes('女足') || awayCN.includes('女足') || 
        homeCN.includes('U2') || awayCN.includes('U2') ||
        homeCN.includes('青年') || awayCN.includes('青年') ||
        homeCN.includes('后备') || awayCN.includes('后备')) continue;
    
    // Extract scores from hard-coded positions in the array
    const parts = trimmed.match(/\[([^\]]+)\]/);
    if (!parts) continue;
    
    const arrStr = parts[1];
    // The format is: [int,int,int,int,'str',...,status,homeTotal,awayTotal,halfHome,halfAway,...]
    // After 12 quoted strings (indices 0-11 in quotes), we get to numeric fields
    // The status is index after the 9th comma after last quoted string... 
    // Let me just split and find the score values
    
    // Find position after the date string (12th field)  
    // A[i]=[ matchID, leagueIdx, homeTeamId, awayTeamId, 
    //        'homeCN','homeTW','homeEN','awayCN','awayTW','awayEN',
    //        'time','date',
    //        status, homeTotal, awayTotal, halfHome, halfAway, ... ]
    
    // Count commas to find position after the date field
    // The array has: number,number,number,number,'q','q','q','q','q','q','q','q',rest
    // rest = status,num,num,num,num,...
    // Where 'q' = quoted string. Date is the 8th quoted string.
    // So after the 8th quote close, we skip to next numeric values
    
    // Extract scores from remaining numeric part
    // Find everything after the last quoted string
    const lastQuoteIdx = trimmed.lastIndexOf("'");
    if (lastQuoteIdx >= 0) {
      const afterQuotes = trimmed.substring(lastQuoteIdx + 1).trim();
      // Remove trailing ]; if present
      const cleanAfter = afterQuotes.replace(/\];?\s*$/, '');
      const nums = cleanAfter.split(',').filter(s => s.trim() !== '').map(s => parseInt(s.trim()));
      // After date, should be: status, homeTotal, awayTotal, halfHome, halfAway, ...
      if (nums.length >= 5) {
        const status = nums[0];
        const homeTotal = nums[1];
        const awayTotal = nums[2];
        const halfHome = nums[3];
        const halfAway = nums[4];
        
        count++;
        console.log(`${time} ${homeCN} vs ${awayCN} FT ${homeTotal}-${awayTotal} HT ${halfHome}-${halfAway} (status=${status})`);
      }
    }
  }
}
console.log(`\nTotal Apr 26 meaningful matches found: ${count}`);
