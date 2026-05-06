#!/usr/bin/env node
const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    viewport: { width: 1280, height: 800 },
  });

  await page.goto('https://live.nowscore.com/2in1.aspx', { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.waitForTimeout(8000);

  // Dump the full page structure to understand the table layout
  const structure = await page.evaluate(() => {
    const table = document.getElementById('table_live');
    if (!table) return 'table_live not found';

    const rows = table.rows;
    const parts = [];
    for (let i = 0; i < Math.min(30, rows.length); i++) {
      const row = rows[i];
      const cells = Array.from(row.cells).map(c => ({
        html: c.innerHTML.substring(0, 100),
        text: c.textContent.trim().substring(0, 50),
        className: c.className,
        rowSpan: c.rowSpan,
        colSpan: c.colSpan,
        style: c.getAttribute('style'),
      }));
      parts.push(`Row ${i}: ${JSON.stringify(cells)}`);
    }
    return parts.join('\n');
  });

  console.log(structure);
  await browser.close();
})();
