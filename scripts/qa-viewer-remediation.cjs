const { chromium } = require('@playwright/test');
const fs = require('node:fs');
const path = require('node:path');
async function run() {
  const origin = process.argv[2] || 'http://127.0.0.1:8765';
  const parsed = new URL(origin);
  if (!['127.0.0.1', 'localhost', '[::1]'].includes(parsed.hostname)) throw Error('Local viewer check only');
  const label = process.argv[3] || 'live';
  if (!/^[a-z0-9-]+$/.test(label)) throw Error('Invalid artifact label');
  let ready=false;
  for(let i=0;i<40;i++) {
    try { ready=(await fetch(origin+'/api/v1/bootstrap',{signal:AbortSignal.timeout(1000)})).ok; } catch {}
    if(ready)break;
    await new Promise(resolve=>setTimeout(resolve,250));
  }
  if(!ready)throw Error('Local viewer was not ready');
  const browser = await chromium.launch({channel:'msedge',headless:true});
  const page = await browser.newPage({viewport:{width:1006,height:884}});
  const evidence = {origin,viewport:{width:1006,height:884},frames:[],errors:[]};
  page.on('pageerror', e => evidence.errors.push(e.message));
  page.on('response', r => { if (r.url().includes('/viewport/frame')) evidence.frames.push({url:r.url(),status:r.status()}); });
  try {
    const first = page.waitForResponse(r => r.url().includes('/viewport/frame') && r.request().method()==='POST',{timeout:60000});
    first.catch(()=>{});
    await page.goto(origin,{waitUntil:'domcontentloaded'});
    const response = await first;
    if (response.status()!==200) throw Error(`Initial viewport HTTP ${response.status()}`);
    const frame = await response.json();
    evidence.initial = {nodes:frame.data.nodes.length,curves:frame.data.curves.length,snapshot_id:frame.snapshot_id};
    if (!frame.data.nodes.length) throw Error('Empty viewport nodes');
    const next = page.waitForResponse(r => r.url().includes('/viewport/frame') && r.request().method()==='POST',{timeout:60000});
    await page.getByRole('button',{name:'Nearby',exact:true}).click();
    const expanded = await next;
    if (expanded.status()!==200) throw Error(`Nearby viewport HTTP ${expanded.status()}`);
    evidence.nearby = {nodes:(await expanded.json()).data.nodes.length};
    await page.waitForTimeout(500);
    if (await page.locator('.error-banner').count()) throw Error(await page.locator('.error-banner').innerText());
    if (!await page.locator('canvas').count()) throw Error('Canvas missing');
    if (evidence.errors.length) throw Error(evidence.errors.join('\n'));
    evidence.ok=true;
  } catch(e) { evidence.ok=false;evidence.failure=e.message;throw e; }
  finally {
    fs.mkdirSync('output/viewer-qa',{recursive:true});
    await page.screenshot({path:path.join('output/viewer-qa',label+'.png'),fullPage:true});
    fs.writeFileSync(path.join('output/viewer-qa',label+'.json'),JSON.stringify(evidence,null,2));
    await browser.close();
  }
  console.log(JSON.stringify(evidence));
}
run().catch(e=>{console.error(e);process.exitCode=1;});
