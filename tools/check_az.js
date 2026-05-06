const fs = require('fs');
const text = fs.readFileSync('/tmp/ft1_full.txt', 'utf-8');

// Search for "阿尔克马尔" 
const lines = text.split('\n');
for (const line of lines) {
  if (line.includes('阿尔克马尔') && !line.includes('女') && !line.includes('U1') && !line.includes('U2') && !line.includes('青年')) {
    console.log('AZ:', line.substring(0, 500));
  }
}

// Also check if there's any 荷甲 match on Apr 26
console.log('\n\n=== 荷甲 Apr 26 matches ===');
for (const line of lines) {
  if (line.includes("'04-26'") && line.includes('荷甲')) {
    // Extract home and away teams from quoted strings
    const firstQuote = line.indexOf("'");
    const rest = line.substring(firstQuote);
    const quoted = rest.match(/'[^']*'/g);
    if (quoted && quoted.length >= 7) {
      const homeCN = quoted[0].replace(/'/g, '');
      const awayCN = quoted[3].replace(/'/g, '');
      const time = quoted[6].replace(/'/g, '');
      
      if (!homeCN.includes('女') && !awayCN.includes('女') && !homeCN.includes('U2') && !homeCN.includes('青年')) {
        console.log(`${time} ${homeCN} vs ${awayCN}`);
      }
    }
  }
}

// Check Swedish Allsvenskan matches on Apr 26
console.log('\n=== 瑞典超 Apr 26 matches ===');
for (const line of lines) {
  if ((line.includes('瑞典超') || line.includes('瑞超')) && line.includes("'04-26'")) {
    const firstQuote = line.indexOf("'");
    const rest = line.substring(firstQuote);
    const quoted = rest.match(/'[^']*'/g);
    if (quoted && quoted.length >= 7) {
      const homeCN = quoted[0].replace(/'/g, '');
      const awayCN = quoted[3].replace(/'/g, '');
      const time = quoted[6].replace(/'/g, '');
      if (!homeCN.includes('女') && !awayCN.includes('女')) {
        console.log(`${time} ${homeCN} vs ${awayCN}`);
      }
    }
  }
}

// Check Greek Super League Apr 26
console.log('\n=== 希腊超 Apr 26 matches ===');
for (const line of lines) {
  if (line.includes("'04-26'") && (line.includes('希腊') || line.includes('希超') || line.includes('Super League'))) {
    const firstQuote = line.indexOf("'");
    const rest = line.substring(firstQuote);
    const quoted = rest.match(/'[^']*'/g);
    if (quoted && quoted.length >= 7) {
      const homeCN = quoted[0].replace(/'/g, '');
      const awayCN = quoted[3].replace(/'/g, '');
      const time = quoted[6].replace(/'/g, '');
      if (!homeCN.includes('女') && !awayCN.includes('女') && !homeCN.includes('U')) {
        console.log(`${time} ${homeCN} vs ${awayCN}`);
      }
    }
  }
}
