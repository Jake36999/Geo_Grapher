const {chromium}=require('@playwright/test');
const AxeBuilder=require('@axe-core/playwright').default;
const fs=require('fs');
(async()=>{
 fs.mkdirSync('output/browser',{recursive:true});
 const browser=await chromium.launch({channel:'msedge',headless:true});
 const context=await browser.newContext({viewport:{width:1440,height:900},deviceScaleFactor:1});const page=await context.newPage();
 const errors=[],external=[];page.on('pageerror',e=>errors.push(String(e)));page.on('request',r=>{if(!r.url().startsWith('http://127.0.0.1:8765'))external.push(r.url());});
 await page.goto('http://127.0.0.1:8765/?debug');
 await page.waitForFunction(()=>window.__geographerMetrics?.nodeCount>0,{},{timeout:120000});
 await page.waitForFunction(()=>document.querySelector('.status-bar')?.textContent.includes('ready.'),null,{timeout:120000});
 await page.waitForTimeout(1200);await page.screenshot({path:'output/browser/desktop-dark.png',fullPage:true});
 const dark=await new AxeBuilder({page}).analyze();
 console.log(JSON.stringify({errors,external,axe:dark.violations.map(v=>({id:v.id,impact:v.impact,nodes:v.nodes.map(n=>n.target)})),metrics:await page.evaluate(()=>window.__geographerMetrics)},null,2));
 await page.getByRole('button',{name:'Use light theme'}).click();await page.screenshot({path:'output/browser/desktop-light.png',fullPage:true});
 await browser.close();
})().catch(e=>{console.error(e);process.exitCode=1;});
