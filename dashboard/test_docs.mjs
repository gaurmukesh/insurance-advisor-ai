import { chromium } from 'playwright';

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();

await page.goto('http://localhost:3000/documents');
await page.waitForLoadState('networkidle');

// Check what the "1 Issue" badge is about  
const issueEl = await page.$('[data-nextjs-toast], [class*="issue"], [class*="Issue"]');
console.log('Issue element:', issueEl ? 'found' : 'not found in DOM');

// Upload file
const fileInput = page.locator('input[type="file"]').first();
await fileInput.setInputFiles('/Users/swastik/python/projects-ai-ml/insurance-advisor-ai/data/policies/insurance_policy.pdf');

await page.waitForSelector('text=insurance_policy.pdf', { timeout: 5000 });
console.log('File selected in dropzone ✓');

await page.screenshot({ path: '/tmp/docs_file_selected.png', fullPage: true });

// Click submit
await page.click('button:has-text("Summarize Document")');
console.log('Clicked Summarize...');

// Wait for LLM result
await page.waitForSelector('text=Key Highlights', { timeout: 60000 });
console.log('Summary result visible ✓');

await page.screenshot({ path: '/tmp/docs_result.png', fullPage: true });

await browser.close();
console.log('All tests passed.');
