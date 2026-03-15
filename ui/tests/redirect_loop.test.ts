import { test, expect } from '@playwright/test';

test('verify no redirect loops on /classify', async ({ page }) => {
  const responses: any[] = [];
  page.on('response', response => {
    responses.push({
      url: response.url(),
      status: response.status(),
      headers: response.headers()
    });
  });

  // We use the local hostname which is what Tailscale proxies to
  await page.goto('http://localhost:5173/classify/');
  
  // Verify we didn't get too many redirects (Playwright would throw, but we can check responses)
  const redirects = responses.filter(r => r.status >= 300 && r.status < 400);
  console.log('Redirects detected:', redirects.length);
  expect(redirects.length).toBeLessThan(3);
  
  await expect(page.locator('h1')).toContainText('Mountain Classifier');
});
