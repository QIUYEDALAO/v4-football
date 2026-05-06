console.log('==========================================================');
console.log('  V17 推荐列表完整明细（4月26日）');
console.log('==========================================================\n');

// All data from the page and head-to-head analysis
// NOTE: 阿尔克马尔、赫根、帕纳辛纳科斯 - need to verify
// From ft1.js and search data:

const fs = require('fs');
const text = fs.readFileSync('/tmp/ft1_full.txt', 'utf-8');

// Check what league/opponent these V17 teams actually played on Apr 26
// Search for 阿尔克马尔 in the full ft1
const lines = text.split('\n');

console.log('=== Searching for 阿尔克马尔/AZ ===');
for (const line of lines) {
  if ((line.includes('阿尔克马尔') || (line.includes('AZ ') && line.includes('荷甲'))) && !line.includes('女足') && !line.includes('U2')) {
    // Parse date
    const idx = line.indexOf("'04-");
    if (idx >= 0) {
      const dateStr = line.substring(idx, idx+7);
      // Find teams
      const rest = line.substring(line.indexOf("'"));
      const quoted = rest.match(/'[^']*'/g);
      if (quoted && quoted.length >= 7) {
        const homeCN = quoted[0].replace(/'/g,'');
        const awayCN = quoted[3].replace(/'/g,'');
        const homeEN = quoted[2].replace(/'/g,'');
        const awayEN = quoted[5].replace(/'/g,'');
        const time = quoted[6].replace(/'/g,'');
        console.log(`Date=${dateStr} Time=${time} ${homeCN}/${homeEN} vs ${awayCN}/${awayEN}`);
      }
    }
  }
}

console.log('\n=== Searching for 赫根/Hacken ===');
for (const line of lines) {
  if ((line.includes('赫根') || line.includes('Hacken')) && !line.includes('(W)') && !line.includes('女足') && !line.includes('U2') && !line.includes('B队')) {
    const idx = line.indexOf("'04-");
    if (idx >= 0) {
      const dateStr = line.substring(idx, idx+7);
      const rest = line.substring(line.indexOf("'"));
      const quoted = rest.match(/'[^']*'/g);
      if (quoted && quoted.length >= 7) {
        const homeCN = quoted[0].replace(/'/g,'');
        const awayCN = quoted[3].replace(/'/g,'');
        const time = quoted[6].replace(/'/g,'');
        console.log(`Date=${dateStr} Time=${time} ${homeCN} vs ${awayCN}`);
      }
    }
  }
}

console.log('\n=== Searching for 帕纳辛纳科斯/Panathinaikos ===');
for (const line of lines) {
  if ((line.includes('帕纳辛') || line.includes('Panathinaikos')) && !line.includes('U19') && !line.includes('U20')) {
    const idx = line.indexOf("'04-");
    if (idx >= 0) {
      const dateStr = line.substring(idx, idx+7);
      const rest = line.substring(line.indexOf("'"));
      const quoted = rest.match(/'[^']*'/g);
      if (quoted && quoted.length >= 7) {
        const homeCN = quoted[0].replace(/'/g,'');
        const awayCN = quoted[3].replace(/'/g,'');
        const time = quoted[6].replace(/'/g,'');
        console.log(`Date=${dateStr} Time=${time} ${homeCN} vs ${awayCN}`);
      }
    }
  }
}

// If not found in ft1, let's check the sc1.js for future data
console.log('\n=== Checking if these teams played on Apr 25 (ft2 matches) ===');
const ft2Text = fs.readFileSync('/tmp/ft2_full.txt', 'utf-8');
const ft2Lines = ft2Text.split('\n');

for (const [teamName, teamFile] of [['阿尔克马尔', '/tmp/ft2_full.txt'], ['赫根', '/tmp/ft2_full.txt'], ['帕纳辛纳科斯', '/tmp/ft2_full.txt']]) {
  for (const line of ft2Lines) {
    if (line.includes(teamName) && !line.includes('女') && !line.includes('U2') && !line.includes('B队')) {
      console.log(`In ft2: ${line.substring(0, 200)}`);
    }
  }
}
