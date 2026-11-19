const {test,expect}=require('@playwright/test');
const {showGraphsMode,showBuildMode,openScope}=require('../browser/panel-helpers.cjs');
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
 await showGraphsMode(page);
 await expect(page.getByRole('combobox',{name:'Active graph',exact:true})).toBeVisible();
 await page.getByRole('combobox',{name:'Active graph',exact:true}).selectOption(g.graph_id);
 await expect(page.getByTestId('spatial-scene')).toBeVisible();
 await expect(page.locator('.view-content')).toHaveAttribute('aria-busy','false');
 return g;
}
async function menu(page){
 await showGraphsMode(page);
 const m=page.locator('.workspace-graph-picker');
 if(!await m.evaluate(e=>e.open))await m.locator(':scope > summary').click();
 return m;
}
async function selectGraphs(page,labels){
 const m=await menu(page),group=page.getByRole('group',{name:'Graphs to display'});
 for(const label of labels)await group.getByRole('checkbox',{name:label,exact:true}).check();
 for(const row of await group.locator('.workspace-graph-choice').all()){
  const label=(await row.locator('label').innerText()).trim();
  if(!labels.includes(label))await row.getByRole('checkbox').uncheck();
 }
 await expect(m.locator(':scope > summary')).toHaveText(`Graphs (${labels.length})`);
 return m;
}
async function only(page,label){
 const m=await selectGraphs(page,[label]);await m.locator(':scope > summary').click();
}
test('real ToolSet spatial view exposes directed QI and renders QI groups',async({page})=>{
 await open(page);
 await only(page,'ToolSet');
 const control=page.getByRole('combobox',{name:'QI algorithm'});
 await openScope(page);
 await expect(control).toBeDisabled();
 await expect(page.getByText('Requires atomic grouping and exact static relationships.')).toBeVisible();
 const when=predicate=>page.waitForResponse(r=>r.url().endsWith('/viewport/frame')&&r.request().method()==='POST'&&predicate(r.request().postDataJSON()));
 const atomic=when(q=>q.grouping?.mode==='atomic'&&!q.qi?.enabled);
 await page.getByLabel('Abstraction grouping').selectOption('atomic');
 const original=(await(await atomic).json()).data.partition_digest;
 await expect(page.locator('.view-content')).toHaveAttribute('aria-busy','false',{timeout:60000});
 await openScope(page);
 await expect(control).toBeEnabled();
 const directed=when(q=>q.qi?.enabled&&q.qi.algorithm==='directed-helper-condensation-v1');
 await openScope(page);
 await control.selectOption('directed-helper-condensation-v1');
 const data=(await(await directed).json()).data;
 expect(data.qi.directed_reachability_preserved).toBe(true);expect(data.qi.group_count).toBeGreaterThan(1);
 await expect(page.locator('.view-content')).toHaveAttribute('aria-busy','false',{timeout:60000});
 await expect(page.getByTestId('qi-certificate')).toContainText('reachability preserved (existential)');
 await expect.poll(async()=>Number(await page.getByTestId('spatial-scene').getAttribute('data-qi-group-count'))).toBeGreaterThan(1);
 await page.screenshot({path:process.env.QA_REAL_SCREENSHOT||'output/qa-real/review2-directed-visible.png'});
 await openScope(page);
 await page.locator('.qi-blocks > summary').click();
 const button=page.locator('[data-qi-group]').first();await expect(button).toBeVisible();
 const old=await button.getAttribute('data-qi-group');const expanded=when(q=>q.qi?.enabled&&q.pins.length>0);
 await button.click();expect((await expanded).ok()).toBe(true);
 await expect(page.locator('.view-content')).toHaveAttribute('aria-busy','false',{timeout:60000});
 expect(await page.locator('[data-qi-group]').evaluateAll(nodes=>nodes.map(n=>n.getAttribute('data-qi-group')))).not.toContain(old);
 await openScope(page);
 const off=when(q=>!q.qi?.enabled);await control.selectOption('off');
 expect((await(await off).json()).data.partition_digest).toBe(original);
 await expect(page.locator('.view-content')).toHaveAttribute('aria-busy','false',{timeout:60000});
 await expect(page.getByTestId('spatial-scene')).toHaveAttribute('data-qi-group-count','0');
 const helpers=when(q=>q.qi?.enabled&&q.qi.algorithm==='helper_tree_balls_v1');
 await openScope(page);
 await control.selectOption('helper_tree_balls_v1');expect((await(await helpers).json()).data.qi.mode).toBe('helper_tree_balls_v1');
 await expect(page.locator('.view-content')).toHaveAttribute('aria-busy','false',{timeout:60000});
 await expect(page.getByTestId('qi-certificate')).toContainText('undirected hop bound');
 await openScope(page);
 await control.selectOption('off');
});
test('real ToolSet box selection prunes a copy and preserves source snapshot',async({page,request})=>{
 test.setTimeout(180000);
 const g=await open(page);
 await only(page,'ToolSet');
 const wider=page.waitForResponse(r=>r.url().endsWith('/viewport/frame')&&r.request().method()==='POST'&&r.request().postDataJSON().context_radius===2);
 await page.getByRole('button',{name:'Wider',exact:true}).click();
 expect((await wider).ok()).toBe(true);
 await expect(page.locator('.view-content')).toHaveAttribute('aria-busy','false');
 await expect(page.locator('.filter-count')).toHaveText(/[1-9]\d* groups/);
 await page.getByRole('button',{name:'Box select',exact:true}).click();
 const canvas=page.getByTestId('spatial-scene').locator('canvas').first();
 const box=await canvas.boundingBox();expect(box).toBeTruthy();
 await page.mouse.move(box.x+12,box.y+80);await page.mouse.down();
 await page.mouse.move(box.x+box.width-12,box.y+box.height-48,{steps:12});await page.mouse.up();
 await page.getByRole('button',{name:/Keep only or remove selection/}).click();
 const derive=page.getByRole('form',{name:'Keep only or remove the selection'});
 await derive.getByRole('radio',{name:'Remove these'}).check(); // what the earlier prune did
 await expect(derive.getByTestId('derive-preview')).toContainText(/^Removes \d+ of \d+ files/,{timeout:90000});
 await derive.getByRole('textbox',{name:'New graph name'}).fill('qa-real-pruned');
 await expect(derive.getByRole('button',{name:'Create graph without these',exact:true})).toBeEnabled();
 const created=page.waitForResponse(r=>r.url().endsWith('/prune')&&r.request().method()==='POST',{timeout:90000});
 await derive.getByRole('button',{name:'Create graph without these',exact:true}).click();
 const response=await created;expect(response.ok(),await response.text()).toBe(true);
 await expect(derive.getByRole('status').filter({hasText:'Made “qa-real-pruned”'})).toBeVisible({timeout:90000});
 const rows=(await(await request.get('/api/graphs')).json()).graphs;
 expect(rows.some(r=>r.label==='qa-real-pruned')).toBe(true);
 expect(rows.find(r=>r.graph_id===g.graph_id).snapshot_id).toBe(g.snapshot_id);
});
test('real code pair bridge review decides one candidate',async({page})=>{
 test.setTimeout(180000);
 await open(page,'librarian-v2');
 // The related real Librarian worktree supplies actual overlapping code;
 // unrelated ToolSet/Librarian snapshots need not yield bridge candidates.
 await selectGraphs(page,['librarian-v2','librarian-survey-worktree']);
 await expect(page.locator('.workspace-graph-picker > summary')).toHaveText('Graphs (2)');
 await showBuildMode(page);
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
 await showBuildMode(page);
 await page.getByRole('button',{name:'Add folder…',exact:true}).click();
 const panel=page.getByRole('region',{name:'Add folder',exact:true});
 await panel.getByRole('button',{name:'project',exact:true}).click();
 await panel.getByRole('button',{name:'Read this folder',exact:true}).click();
 const sheet=page.getByRole('dialog',{name:'How this folder was read'});
 const choices=sheet.getByRole('checkbox');await expect(choices).toHaveCount(2);
 await choices.nth(1).uncheck();
 await sheet.getByRole('button',{name:'Ingest 1 selected part',exact:true}).click();
 await expect(page.getByTestId('ingest-job-state')).toHaveText('Job done',{timeout:90000});
 const now=(await(await request.get('/api/graphs')).json()).graphs;
 expect(now.filter(g=>!baseline.some(b=>b.graph_id===g.graph_id)&&g.label!=='qa-real-pruned')).toHaveLength(1);
});
test('picker refuses traversal, UNC, junction and outside absolute directory',async({request})=>{
 const paths=['..','\\\\localhost\\C$',path.join(root,'browse','junction'),path.join(root,'outside-browse')];
 for(const p of paths){const r=await request.get('/api/fs/list',{params:{path:p}});expect(r.status(),p).toBe(403);}
});
