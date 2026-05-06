const fs = require('fs');
const text = fs.readFileSync('/tmp/ft1_full.txt', 'utf-8');

// Let's search for ALL matches with time after 18:00 (6pm) on any date
// These are the "prime" matches 
const lines = text.split('\n');
const lateMatches = [];

for (const line of lines) {
  if (!line.trim().startsWith('A[')) continue;
  
  // Extract quoted strings
  const quoted = line.match(/'([^']*)'/g);
  if (!quoted || quoted.length < 8) continue;
  
  const homeCN = quoted[0].replace(/'/g,'');
  const awayCN = quoted[3].replace(/'/g,'');
  const time = quoted[6].replace(/'/g,'');
  const date = quoted[7].replace(/'/g,'');
  
  // Only look at meaningful matches (not youth/women/reserve/B teams)
  const skipKeywords = ['女足', 'U23', 'U21', 'U20', 'U19', 'U17', 'U16', 'U15', 'U14', 'B队', '预备队', '后备队', '青年队', 'Reserve'];
  const shouldSkip = skipKeywords.some(k => homeCN.includes(k) || awayCN.includes(k));
  
  if (!shouldSkip && (date === '04-26' || (date === '04-25' && parseInt(time) >= 18))) {
    lateMatches.push({ homeCN, awayCN, time, date });
  }
}

console.log(`Found ${lateMatches.length} meaningful matches on Apr 25 18:00+ and Apr 26`);
lateMatches.slice(0, 50).forEach((m, i) => {
  console.log(`${i+1}. ${m.date} ${m.time} ${m.homeCN} vs ${m.awayCN}`);
});

// Now specifically search for the V17 matches without filtering
console.log('\n\n=== BROAD SEARCH FOR V17 MATCHES ===');
const searchTerms = ['根特', '莫尔德', 'Molde', 'Excelsior', 'SBV', '诺夫哥罗德', 'Nizhny', 
  '佛罗伦萨', 'Fiorentina', '流浪者', 'Rangers', 'Motherwell',
  '莫斯科迪纳摩', '克拉斯诺达尔'];

for (const term of searchTerms) {
  const positions = [];
  let pos = -1;
  while ((pos = text.indexOf(term, pos + 1)) !== -1) {
    positions.push(pos);
  }
  if (positions.length > 0) {
    // For each occurrence, find complete line
    for (const p of positions) {
      const start = text.lastIndexOf('\n', p);
      const end = text.indexOf('\n', p);
      const line = text.substring(start, end);
      
      if (!line.includes('女足') && !line.includes('U2') && !line.includes('后备') && !line.includes('青年') && !line.includes('B队') && !line.includes('Reserve')) {
        console.log(`${term}: ${line.substring(0, 300)}`);
      }
    }
  }
}

// ALSO search sc1.js (tomorrow's future data)
// This might have Apr 26 late matches that were so recent they're in 'today' 

console.log('\n\n=== NOW LET ME TRY THE RIGHT URL ===');
// The default page loads ft1.js but maybe for Apr 27 the data file is different
// Tomorrow's data uses sc1, sc2 etc
// April 26 is yesterday - maybe there's a different data file
// Let me check if the site uses yyyy-mm-dd-based filenames
console.log('Possible URLs to try:');
console.log('https://live.nowscore.com/data/ft1.js?1777255917000 - has Apr 25');
console.log('https://live.nowscore.com/data/16828.js etc.');
console.log('');
console.log('Or maybe the site loads from a different source now since it\'s a new day');

fs.writeFileSync('/tmp/ft1_filtered.txt', JSON.stringify(lateMatches, null, 2));
console.log('\nSaved to /tmp/ft1_filtered.txt');
