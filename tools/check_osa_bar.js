#!/usr/bin/env node
const { chromium } = require('playwright');

(async () => {
  const b = await chromium.launch({ headless: true });
  const p = await b.newPage({
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
  });

  // Open match detail page for Osasuna vs Barcelona (id=2804630)
  await p.goto('https://live.nowscore.com/detail/2804630.html', { waitUntil: 'domcontentloaded', timeout: 30000 });
  await p.waitForTimeout(3000);
  
  const text = await p.evaluate(() => document.body.innerText);
  console.log(text.substring(0, 4000));
  
  await b.close();
})();
