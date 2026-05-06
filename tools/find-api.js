const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
  });
  const page = await context.newPage();

  const apiUrls = [];
  page.on('request', req => {
    const url = req.url();
    if (url.includes('live.nowscore') || url.includes('data') || url.includes('json') || url.includes('schedule') || url.includes('2in1')) {
      apiUrls.push({ method: req.method(), url });
    }
  });

  page.on('response', async res => {
    const url = res.url();
    if (url.includes('live.nowscore') && (url.includes('.aspx') || url.includes('/data/') || url.includes('/js/') || url.includes('?'))) {
      try {
        const text = await res.text();
        if (text.length < 20000 && text.length > 100) {
          console.log('=== RESPONSE:', res.status(), url, 'len:', text.length);
          console.log(text.substring(0, 1000));
        }
      } catch(e) {}
    }
  });

  await page.goto('https://live.nowscore.com/2in1.aspx', { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.waitForTimeout(8000);

  console.log('\n=== ALL REQUESTS ===');
  apiUrls.forEach(r => console.log(r.method, r.url));

  // Check page state after load
  const title = await page.title();
  const body = await page.evaluate(() => document.body.innerText.substring(0, 500));
  console.log('\n=== PAGE TITLE:', title);
  console.log('BODY:', body);

  await browser.close();
})();
