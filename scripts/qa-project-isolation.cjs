const {chromium}=require('@playwright/test');
const fs=require('node:fs');
(async()=>{
 const origin='http://127.0.0.1:8773';
 const browser=await chromium.launch({channel:'msedge',headless:true});
 const page=await browser.newPage({viewport:{width:1440,height:1000}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 try {
  const framePromise=page.waitForResponse(r=>r.url().endsWith('/viewport/frame')&&r.request().method()==='POST');
  await page.goto(origin,{waitUntil:'domcontentloaded'});const response=await framePromise;const envelope=await response.json();
  if(response.status()!==200)throw Error(JSON.stringify(envelope));
  const roots=envelope.data.nodes.filter(n=>n.kind==='repository');
  if(roots.length!==2||roots[0].parent_id!==roots[1].parent_id)throw Error('Independent project roots missing');
  await page.locator('canvas').waitFor();await page.waitForTimeout(300);
  const labels=await page.locator('.scene-node-label').allTextContents();
  if(!labels.includes('librarian-v2')||!labels.includes('timeline-mapping')||labels.includes('Workspace'))throw Error('Root cluster labels incorrect: '+labels);
  await page.screenshot({path:'output/project-isolation/clusters-desktop.png',fullPage:true});
  await page.getByLabel('Search intent',{exact:true}).selectOption('documentation');
  const first=page.waitForResponse(r=>r.url().endsWith('/search_entities')&&r.request().method()==='POST');
  await page.getByLabel('Search entities',{exact:true}).fill('research');
  const firstResponse=await first;const firstResult=await firstResponse.json();
  const firstRequest=firstResponse.request().postDataJSON();
  if(firstRequest.repo_ids.length!==1||firstRequest.repo_ids[0]!=='librarian-v2')throw Error('Default search is not scoped');
  if(firstResult.error||firstResult.data.nodes.some(n=>n.repo_id!=='librarian-v2'))throw Error('Search blended projects');
  const second=page.waitForResponse(r=>r.url().endsWith('/search_entities')&&r.request().method()==='POST');
  await page.getByLabel('Search project',{exact:true}).selectOption('timeline-mapping');
  const secondResponse=await second;const secondResult=await secondResponse.json();
  if(secondResult.error||secondResult.data.nodes.some(n=>n.repo_id!=='timeline-mapping'))throw Error('Timeline search blended projects');
  const all=page.waitForResponse(r=>r.url().endsWith('/search_entities')&&r.request().method()==='POST');
  await page.getByLabel('Search project',{exact:true}).selectOption('@all');
  const allResponse=await all;const allRequest=allResponse.request().postDataJSON();
  if(allRequest.repo_ids.length!==2)throw Error('Workspace comparison not explicit');
  await page.setViewportSize({width:1006,height:884});await page.waitForTimeout(300);
  await page.getByLabel('Search entities',{exact:true}).fill('');
  await page.screenshot({path:'output/project-isolation/clusters-1006.png',fullPage:true});
  if(errors.length||await page.locator('.error-banner').count())throw Error(errors.join('\n')||await page.locator('.error-banner').innerText());
  const result={ok:true,origin,roots:roots.map(n=>({id:n.id,repo_id:n.repo_id,parent_id:n.parent_id})),labels,defaultSearch:firstRequest.repo_ids,timelineSearch:secondResponse.request().postDataJSON().repo_ids,explicitComparison:allRequest.repo_ids,errors};
  fs.writeFileSync('output/project-isolation/browser.json',JSON.stringify(result,null,2));console.log(JSON.stringify(result));
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
