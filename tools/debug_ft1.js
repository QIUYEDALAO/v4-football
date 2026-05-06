const fs = require('fs');
const text = fs.readFileSync('/tmp/ft1_full.txt', 'utf-8');

// Show a single Apr 26 match line in detail
const lines = text.split('\n');
for (const line of lines) {
  if (line.trim().startsWith('A[') && line.includes("'04-26'")) {
    const trimmed = line.trim();
    const quoted = trimmed.match(/'([^']*)'/g);
    
    if (quoted && quoted.length >= 4) {
      const homeCN = quoted[0].replace(/'/g,'');
      const awayCN = quoted[3].replace(/'/g,'');
      
      // Skip women's/youth/reserve matches
      if (homeCN.includes('女') || awayCN.includes('女') || 
          homeCN.includes('后备') || homeCN.includes('青年') ||
          homeCN.includes('B队') || homeCN.includes('U2') || homeCN.includes('U1') ||
          awayCN.includes('后备') || awayCN.includes('青年') ||
          awayCN.includes('B队')) continue;
      
      // Show the full line for analysis
      console.log('FULL LINE:', trimmed.substring(0, 500));
      
      // Now count: quoted strings are positions 0-11 (12 total before scores)
      // After them: ,status,homeTotal,awayTotal,halfHome,halfAway,...
      // The array starts with: [int,int,int,int,...] before the quoted strings
      
      // Find position after 7th comma after the last quote
      const lastQuoteIdx = trimmed.lastIndexOf("'");
      const afterQuote = trimmed.substring(lastQuoteIdx + 1);
      
      // The sequence: ],...rest after last quote
      // After the last quote, we have: ,-1,1,4,0,2,... (status,homeTotal,awayTotal,halfHome,halfAway,...)
      // Remove leading comma if present
      let numStr = afterQuote.replace(/^,/, '').replace(/\];?\s*$/, '');
      const nums = numStr.split(',').map(s => parseInt(s.trim())).filter(n => !isNaN(n));
      console.log('Numbers after last quote:', nums.join(','));
      
      if (nums.length >= 5) {
        const status = nums[0];
        const homeTotal = nums[1];
        const awayTotal = nums[2];
        const halfHome = nums[3];
        const halfAway = nums[4];
        console.log(`→ ${homeCN} vs ${awayCN} FT ${homeTotal}-${awayTotal} HT ${halfHome}-${halfAway} (hasHTGoal=${halfHome+halfAway > 0})`);
      }
      console.log('');
      break; // Just show first example
    }
  }
}
