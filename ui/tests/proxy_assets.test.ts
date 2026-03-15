import { test, expect } from '@playwright/test';

test('check if assets load through proxy', async ({ page }) => {
  const failedRequests: string[] = [];
  const consoleErrors: string[] = [];

  page.on('requestfailed', request => {
    failedRequests.push(`${request.url()}: ${request.failure()?.errorText}`);
  });

  page.on('response', response => {
    if (response.status() >= 400) {
      failedRequests.push(`${response.url()}: ${response.status()}`);
    }
  });

  page.on('pageerror', error => {
    consoleErrors.push(error.message);
  });

  // Use the local IP + Host header to simulate tailscale if DNS is flaky in test env
  // But first try the direct local port to see what the paths look like
  await page.goto('http://localhost:5173/classify/');
  
  // Wait for React to mount
  await page.waitForTimeout(2000);

  console.log('Failed Requests:', failedRequests);
  console.log('Console Errors:', consoleErrors);

  // Assertions
  expect(failedRequests.length, `Found ${failedRequests.length} failed requests`).toBe(0);
  expect(consoleErrors.length, `Found ${consoleErrors.length} console errors`).toBe(0);
  await expect(page.locator('h1')).toContainText('Mountain Classifier');
});
