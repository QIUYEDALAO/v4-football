const fs = require('fs');
const text = fs.readFileSync('/tmp/ft1_full.txt', 'utf-8');

// Direct search for 博洛尼亚 and 罗马
const lines = text.split('\n');
for (const line of lines) {
  if (line.includes('博洛尼亚') && line.includes('罗马')) {
    console.log('Found:', line.substring(0, 500));
  }
  if (line.includes('阿尔克马尔') || (line.includes('AZ') && line.includes("'荷甲"))) {
    console.log('AZ line:', line.substring(0, 500));
  }
  if (line.includes('赫根') || line.includes('Hacken') || line.includes('Häcken')) {
    console.log('Hacken:', line.substring(0, 500));
  }
  if (line.includes('帕纳辛') || line.includes('Panathinaikos')) {
    console.log('Panathinaikos:', line.substring(0, 500));
  }
}
