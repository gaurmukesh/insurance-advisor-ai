import { chromium } from 'playwright';

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();

await page.goto('http://localhost:3000/documents');
await page.waitForLoadState('networkidle');

const fileInput = page.locator('input[type="file"]').first();
await fileInput.setInputFiles('/Users/swastik/python/projects-ai-ml/insurance-advisor-ai/data/policies/insurance_policy.pdf');
await page.waitForSelector('text=insurance_policy.pdf', { timeout: 5000 });

await page.click('button:has-text("Summarize Document")');

await page.waitForSelector('text=Key Highlights', { timeout: 60000 });
await page.screenshot({ path: '/tmp/docs_markdown_rendered.png', fullPage: true });

// Check that raw markdown is not visible
const rawHash = await page.locator('text=### ').count();
const rawBold = await page.locator('text=**Policy').count();
console.log(`Raw ### found: ${rawHash}, Raw ** found: ${rawBold}`);
if (rawHash === 0 && rawBold === 0) console.log('Markdown rendered correctly ✓');

await browser.close();
