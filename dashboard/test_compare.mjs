import { chromium } from 'playwright';

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();

await page.goto('http://localhost:3000/documents');
await page.waitForLoadState('networkidle');

// Switch to Compare mode
await page.click('button:has-text("Compare Two Policies")');
await page.waitForTimeout(500);
console.log('Switched to Compare mode');

// Upload same file to both slots
const inputs = page.locator('input[type="file"]');
await inputs.nth(0).setInputFiles('/Users/swastik/python/projects-ai-ml/insurance-advisor-ai/data/policies/insurance_policy.pdf');
await inputs.nth(1).setInputFiles('/Users/swastik/python/projects-ai-ml/insurance-advisor-ai/data/policies/insurance_policy.pdf');

await page.waitForTimeout(500);
const fileNames = await page.locator('text=insurance_policy.pdf').count();
console.log(`Files shown in dropzones: ${fileNames}`);

await page.screenshot({ path: '/tmp/docs_compare_ready.png', fullPage: true });

// Submit
await page.click('button:has-text("Compare Policies")');
console.log('Clicked Compare...');

await page.waitForSelector('text=Quick Summary', { timeout: 90000 });
console.log('Compare result visible ✓');

await page.screenshot({ path: '/tmp/docs_compare_result.png', fullPage: true });

await browser.close();
