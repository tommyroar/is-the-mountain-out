const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  
  const responses = [];
  page.on('response', response => {
    responses.push({
      url: response.url(),
      status: response.status()
    });
  });

  console.log('Navigating to http://localhost:5173/classify/ ...');
  try {
    await page.goto('http://localhost:5173/classify/', { waitUntil: 'networkidle' });
    
    const redirects = responses.filter(r => r.status >= 300 && r.status < 400);
    console.log('Redirects detected:', redirects.length);
    if (redirects.length > 2) {
      console.error('FAIL: Too many redirects detected!');
      process.exit(1);
    }

    const h1 = await page.innerText('h1').catch(() => 'NOT FOUND');
    console.log('H1 Text:', h1);
    
    if (h1 === 'NOT FOUND') {
      console.error('FAIL: UI content not found!');
      process.exit(1);
    }

    console.log('PASS: No redirect loop and UI content verified.');
  } catch (e) {
    console.error('Navigation failed:', e.message);
    process.exit(1);
  } finally {
    await browser.close();
  }
})();
