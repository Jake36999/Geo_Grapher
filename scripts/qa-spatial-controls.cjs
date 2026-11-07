// Read-only reproduction of the Librarian screenshot's directory/uncertainty view.
const {chromium,expect}=require('@playwright/test');const fs=require('node:fs');
(async()=>{
 const origin='http://127.0.0.1:8765',metadata=await(await fetch(origin+'/api/graphs')).json();
 const graph=metadata.graphs.find(g=>g.label==='librarian-v2');if(!graph)throw Error('Librarian sample not registered');
 const browser=await chromium.launch({channel:'msedge',headless:true});
 const page=await browser.newPage({viewport:{width:1440,height:1000},reducedMotion:'reduce'}),errors=[];
 const sphereMap=new Map();let activePartition;page.on('pageerror',e=>errors.push(e.message));
 page.on('response',async response=>{
  if(!/\/viewport\/(frame|page)$/.test(response.url()))return;
  try{
   const q=response.request().postDataJSON();
   const data=(await response.json()).data;
   if(response.url().endsWith('/frame')){
    if(q.grouping?.kind!=='directory'||!q.filter?.resolution_statuses?.includes('unresolved'))return;
    activePartition=data?.partition_digest;sphereMap.clear();
   }
   if(!activePartition||data?.partition_digest!==activePartition)return;
   for(const s of data?.spheres??[])if(s.role==='representative')sphereMap.set(data.ids?.[s.node_id]??s.node_id,s);
  }catch{}
 });
 try{
  await page.goto(`${origin}/graphs/${graph.graph_id}/?view=spatial&label=librarian-v2&debug`);
  await expect(page.getByRole('searchbox',{name:'Search entities'})).toBeEnabled();
  await page.locator('.workspace-graph-picker > summary').click();
  const menu=page.getByRole('group',{name:'Graphs to display'});
  for(const g of metadata.graphs)if(g.graph_id!==graph.graph_id)await menu.getByRole('checkbox',{name:g.label,exact:true}).uncheck();
  await page.locator('.workspace-graph-picker > summary').click();

  await page.locator('.node-select[title="src"]').press('Shift+Enter');
  await expect(page.getByRole('heading',{level:1,name:'src',exact:true})).toBeVisible();
  await page.getByLabel('Abstraction grouping').selectOption('directory');
  await page.getByLabel('Relationship visibility preset').selectOption('all_uncertainty');
  await page.getByRole('button',{name:'Wider',exact:true}).click();
  await expect.poll(()=>page.evaluate(()=>window.__geographerMetrics?.nodeCount??0),{timeout:30000}).toBeGreaterThan(100);
  await expect(page.locator('.view-content')).toHaveAttribute('aria-busy','false');
  await expect(page.getByRole('alert')).toHaveCount(0);
  const canvas=page.locator('canvas');await expect(canvas).toBeVisible();
  await page.getByRole('button',{name:'Fit displayed groups',exact:true}).click();
  await page.screenshot({path:'output/spatial-controls/librarian-directories.png'});
  const values=[...sphereMap.values()],spans=[0,1,2].map(j=>Math.max(...values.map(s=>s.center[j]))-Math.min(...values.map(s=>s.center[j])));
  if(values.length<100||Math.min(...spans)<=0||Math.max(...spans)/Math.min(...spans)>10)throw Error('Directory fallback is still effectively linear: '+JSON.stringify(spans));
  const metrics=await page.evaluate(()=>({nodes:window.__geographerMetrics?.nodeCount,curves:window.__geographerMetrics?.curveCount}));
  if(errors.length)throw Error(errors.join('\n'));
  fs.writeFileSync('output/spatial-controls/live-reproduction.json',JSON.stringify({graph_id:graph.graph_id,snapshot_id:graph.snapshot_id,focus:'src',grouping:'directory',visibility:'all_uncertainty',...metrics,representativeSpans:spans,spanRatio:Math.max(...spans)/Math.min(...spans),errors},null,2));
  console.log('PASS real Librarian directory/uncertainty view: '+JSON.stringify(metrics)+', 3D span ratio '+(Math.max(...spans)/Math.min(...spans)).toFixed(2));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
