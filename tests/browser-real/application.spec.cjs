const {test,expect}=require('@playwright/test');
const path=require('path');
const root=path.resolve(process.env.QA_REAL_ROOT||'output/phase67-gates/wave4/application-r1');
let baseline=[];
test.beforeAll(async({request})=>{baseline=(await(await request.get('/api/graphs')).json()).graphs;});
test.afterAll(async({request})=>{
 const now=(await(await request.get('/api/graphs')).json()).graphs;
 for(const g of now)if(!baseline.some(b=>b.graph_id===g.graph_id))expect((await request.delete('/api/graphs/'+g.graph_id,{data:{confirm_label:g.label}})).ok()).toBeTruthy();
 const clean=await(await request.post('/__qa/cleanup',{data:{}})).json();
 expect(clean.extra_graphs).toEqual([]);expect(clean.baseline_preserved).toBe(true);
});
test.beforeEach(async({page})=>{
 page.qaErrors=[];page.on('pageerror',e=>page.qaErrors.push(String(e)));
 page.on('console',m=>{if(m.type()==='error')page.qaErrors.push(m.text());});
});
test.afterEach(async({page},info)=>{
 await info.attach('console-errors',{body:JSON.stringify(page.qaErrors),contentType:'application/json'});
 await info.attach('visible-text',{body:await page.locator('body').innerText().catch(()=>'<page closed>'),contentType:'text/plain'});
 expect(page.qaErrors).toEqual([]);
});
async function open(page,label='ToolSet'){
 const g=baseline.find(g=>g.label===label);expect(g).toBeTruthy();
 await page.goto('/?graph='+g.graph_id);
 await expect(page.getByRole('combobox',{name:'Active graph',exact:true})).toBeVisible();
 await page.getByRole('combobox',{name:'Active graph',exact:true}).selectOption(g.graph_id);
 await expect(page.getByTestId('spatial-scene')).toBeVisible();
 await expect(page.locator('.view-content')).toHaveAttribute('aria-busy','false');
 return g;
}
async function menu(page){
 const m=page.locator('.workspace-graph-picker');
 if(!await m.evaluate(e=>e.open))await m.locator(':scope > summary').click();
 return m;
}
test('real ToolSet spatial view exposes directed QI and renders QI groups',async({page})=>{
 await open(page);
 // An API-only certificate cannot satisfy this visible user workflow.
 const control=page.getByRole('combobox',{name:/QI algorithm|directed QI/i});
 await expect(control).toBeVisible();
 await control.selectOption('directed-helper-condensation-v1');
 await expect(page.locator('[data-qi-group]')).not.toHaveCount(0);
});
test('real ToolSet box selection prunes a copy and preserves source snapshot',async({page,request})=>{
 test.setTimeout(180000);
 const g=await open(page);
 await page.getByRole('button',{name:'Wider',exact:true}).click();
 await expect(page.locator('.view-content')).toHaveAttribute('aria-busy','false');
 await expect(page.locator('.filter-count')).toHaveText(/[1-9]\d* groups/);
 await page.getByRole('button',{name:'Box select',exact:true}).click();
 const canvas=page.getByTestId('spatial-scene').locator('canvas').first();
 const box=await canvas.boundingBox();expect(box).toBeTruthy();
 await page.mouse.move(box.x+12,box.y+80);await page.mouse.down();
 await page.mouse.move(box.x+box.width-12,box.y+box.height-48,{steps:12});await page.mouse.up();
 await page.getByRole('button',{name:/Prune selection/}).click();
 await page.getByRole('textbox',{name:'New graph label'}).fill('qa-real-pruned');
 const created=page.waitForResponse(r=>r.url().endsWith('/prune')&&r.request().method()==='POST',{timeout:90000});
 await page.getByRole('button',{name:'Create pruned graph',exact:true}).click();
 const response=await created;expect(response.ok(),await response.text()).toBe(true);
 await expect(page.getByRole('status').filter({hasText:'Created derived graph'})).toBeVisible({timeout:90000});
 const rows=(await(await request.get('/api/graphs')).json()).graphs;
 expect(rows.some(r=>r.label==='qa-real-pruned')).toBe(true);
 expect(rows.find(r=>r.graph_id===g.graph_id).snapshot_id).toBe(g.snapshot_id);
});
test('real code pair bridge review decides one candidate',async({page})=>{
 test.setTimeout(180000);
 await open(page,'librarian-v2');
 await menu(page);
 const group=page.getByRole('group',{name:'Graphs to display'});
 // The related real Librarian worktree supplies actual overlapping code;
 // unrelated ToolSet/Librarian snapshots need not yield bridge candidates.
 for(const g of baseline)await group.getByRole('checkbox',{name:g.label,exact:true}).setChecked(['librarian-v2','librarian-survey-worktree'].includes(g.label));
 await expect(page.locator('.workspace-graph-picker > summary')).toHaveText('Graphs (2)');
 const panel=page.locator('.bridge-review');
 if(!await panel.evaluate(e=>e.open))await panel.locator(':scope > summary').click();
 await expect(panel.getByRole('button',{name:'Find candidates',exact:true})).toBeEnabled();
 const proposed=page.waitForResponse(r=>r.url().endsWith('/bridge-proposals')&&r.request().method()==='POST',{timeout:90000});
 await panel.getByRole('button',{name:'Find candidates',exact:true}).click();
 const response=await proposed;expect(response.ok(),await response.text()).toBe(true);
 const first=page.getByRole('list',{name:'Bridge candidates'}).getByRole('listitem').first();
 await expect(first).toBeVisible({timeout:90000});
 await first.getByRole('textbox').fill('QA review: lexical overlap alone does not establish equivalence.');
 const decision=page.waitForResponse(r=>r.url().includes('/bridge-proposals/')&&r.request().method()==='POST');
 await first.getByRole('button',{name:'Reject',exact:true}).click();
 expect((await decision).ok()).toBe(true);
});
test('real workspace adds a folder and ingests one selected partition',async({page,request})=>{
 await open(page,'librarian-v2');
 await menu(page);
 await page.getByRole('button',{name:'Add folder…',exact:true}).click();
 const panel=page.getByRole('region',{name:'Add folder',exact:true});
 await panel.getByRole('button',{name:'project',exact:true}).click();
 await panel.getByRole('button',{name:'Preview this folder',exact:true}).click();
 const choices=panel.getByRole('checkbox');await expect(choices).toHaveCount(2);
 await choices.nth(1).uncheck();
 await panel.getByRole('button',{name:'Ingest selected partitions',exact:true}).click();
 await expect(page.getByTestId('ingest-job-state')).toHaveText('Job done',{timeout:90000});
 const now=(await(await request.get('/api/graphs')).json()).graphs;
 expect(now.filter(g=>!baseline.some(b=>b.graph_id===g.graph_id)&&g.label!=='qa-real-pruned')).toHaveLength(1);
});
test('picker refuses traversal, UNC, junction and outside absolute directory',async({request})=>{
 const paths=['..','\\\\localhost\\C$',path.join(root,'browse','junction'),path.join(root,'outside-browse')];
 for(const p of paths){const r=await request.get('/api/fs/list',{params:{path:p}});expect(r.status(),p).toBe(403);}
});
