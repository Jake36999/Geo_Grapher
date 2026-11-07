const {chromium,expect}=require('@playwright/test');const fs=require('node:fs');
(async()=>{
 const origin='http://127.0.0.1:8765',home=await fetch(origin+'/',{redirect:'manual'}),html=await home.text();
 if(home.status!==200||!html.includes('name="geographer-workspace" content="integrated"'))throw Error('Integrated main workspace unavailable');
 const bootstrap=await(await fetch(origin+'/api/v1/bootstrap')).json();if(!bootstrap.snapshots?.length)throw Error('Original API unavailable');
 const metadata=await(await fetch(origin+'/api/graphs')).json();
 const browser=await chromium.launch({channel:'msedge',headless:true}),page=await browser.newPage({viewport:{width:1600,height:1100},reducedMotion:'reduce'}),errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 try{
  await page.goto(origin+'/?debug');await expect(page.getByRole('searchbox',{name:'Search entities'})).toBeEnabled({timeout:60000});
  await expect(page.locator('.view-content')).toHaveAttribute('aria-busy','false',{timeout:60000});
  await expect(page.getByText('Loading selected graphs…',{exact:true})).toHaveCount(0,{timeout:60000});
  await expect(page.getByRole('alert')).toHaveCount(0);
  await expect(page.getByRole('complementary',{name:'Repository hierarchy'})).toBeVisible();
  await expect(page.getByRole('complementary',{name:'Entity details'})).toBeVisible();
  await expect(page.locator('canvas')).toBeVisible();await expect(page.locator('iframe')).toHaveCount(0);
  const primary=metadata.graphs.find(g=>g.graph_kind==='registered_store');if(primary)await expect(page.getByRole('combobox',{name:'Active graph'})).toHaveValue(primary.graph_id);
  await page.screenshot({path:'output/integrated-workspace/live-main.png'});
  await page.getByRole('button',{name:'List',exact:true}).click();
  const library=metadata.graphs.find(g=>g.label==='librarian-v2');await page.locator('.list-entity').filter({hasText:'librarian-v2'}).first().click();
  await expect(page.getByRole('combobox',{name:'Active graph'})).toHaveValue(library.graph_id);
  await expect(page.getByRole('button',{name:'List',exact:true})).toHaveAttribute('aria-pressed','true');
  await page.getByRole('button',{name:'Matrix',exact:true}).click();await expect(page.getByRole('table')).toBeVisible();
  await expect(page.getByRole('alert')).toHaveCount(0);if(new URL(page.url()).pathname!=='/')throw Error('View switch navigated away from main page');
  await page.screenshot({path:'output/integrated-workspace/live-matrix.png'});
  if(errors.length)throw Error(errors.join('\n'));
  fs.writeFileSync('output/integrated-workspace/live-browser.json',JSON.stringify({ok:true,origin,registeredGraphs:metadata.graphs.map(g=>({graph_id:g.graph_id,label:g.label})),originalSnapshotCount:bootstrap.snapshots.length,samePageViews:['spatial','list','matrix'],originalHierarchyAndInspector:true,pageErrors:errors},null,2));
  console.log('PASS original main workspace with integrated multi-graph 3D/list/matrix, scoped inspector, original API and no extra viewer pages');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
