const {chromium}=require('@playwright/test');
const fs=require('fs');
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try{
 const context=await browser.newContext({viewport:{width:1440,height:900},deviceScaleFactor:1});const page=await context.newPage();
 const errors=[],requests=[];page.on('pageerror',e=>errors.push(String(e)));page.on('response',async r=>{if(r.url().includes('/api/v1/viewport/'))requests.push({url:r.url(),status:r.status(),at:Date.now()});});
 const start=Date.now();await page.goto('http://127.0.0.1:8766/?debug');await page.waitForFunction(()=>window.__geographerMetrics?.nodeCount>0,null,{timeout:180000});const first=Date.now()-start;
 await page.waitForFunction(()=>document.querySelector('.status-bar')?.textContent.includes('ready.')||document.querySelector('.status-bar')?.textContent.includes('Overview ready.'),null,{timeout:300000});
 const cdp=await context.newCDPSession(page);await cdp.send('Performance.enable');const memory=[];
 const duration=Number(process.env.GEOGRAPHER_SOAK_MS??600000),soakStart=Date.now();let iteration=0;
 while(Date.now()-soakStart<duration){
   await page.getByRole('button',{name:'Zoom in',exact:true}).click();await page.getByRole('button',{name:'Zoom out',exact:true}).click();
   if(iteration%2===0){await page.getByRole('button',{name:'List',exact:true}).click();await page.getByRole('button',{name:'3D space',exact:true}).click();}
   await page.waitForTimeout(1000);await cdp.send('HeapProfiler.collectGarbage');const metrics=(await cdp.send('Performance.getMetrics')).metrics;
   const scene=await page.evaluate(()=>{const m=window.__geographerMetrics;return {...m,fps:m.fps.slice(-120).sort((a,b)=>a-b)[Math.floor(Math.min(120,m.fps.length)*.05)]};});
   memory.push({elapsed_ms:Date.now()-soakStart,heap:metrics.find(m=>m.name==='JSHeapUsedSize')?.value,scene});
   if(iteration%10===0)console.log(JSON.stringify({elapsed_ms:Date.now()-soakStart,heap:memory.at(-1).heap,nodes:scene.nodeCount,curves:scene.curveCount,geometries:scene.geometries}));
   iteration++;await page.waitForTimeout(4000);
 }
 const report={build:await page.locator('script[src]').evaluateAll(xs=>xs.map(x=>x.src)),browser:browser.version(),viewport:[1440,900,1],first_usable_ms:first,full_scene_ms:requests.at(-1)?.at-start,requests,errors,duration_ms:Date.now()-soakStart,memory};fs.writeFileSync('output/browser/reference-performance.json',JSON.stringify(report,null,2));await page.screenshot({path:'output/browser/reference-scene.png'});console.log(JSON.stringify({completed:true,first_usable_ms:first,errors,samples:memory.length}));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
