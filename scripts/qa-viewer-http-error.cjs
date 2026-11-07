const { chromium } = require('@playwright/test');
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try {
  const page=await browser.newPage();
  await page.route('**/api/v1.1/viewport/frame',r=>r.fulfill({status:405,contentType:'text/plain',body:'Method Not Allowed'}));
  await page.goto('http://127.0.0.1:8765/',{waitUntil:'domcontentloaded'});
  const banner=page.locator('.error-banner');await banner.waitFor();
  const text=await banner.innerText();
  if(!text.includes('405')||!text.includes('restart')||text.includes('Unexpected token'))throw Error(text);
  require('fs').writeFileSync('output/viewer-qa/http405.json',JSON.stringify({ok:true,simulatedBrowserResponse:true,message:text},null,2));
  console.log('PASS: simulated plain-text 405 produces actionable backend mismatch message');
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
