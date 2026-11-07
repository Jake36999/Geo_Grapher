const {test,expect}=require('@playwright/test');
const fs=require('node:fs'),ts=require('typescript');
const AxeBuilder=require('@axe-core/playwright').default;
async function ready(page){await expect(page.getByRole('searchbox',{name:'Search entities'})).toBeEnabled();await expect(page.locator('.view-content')).toHaveAttribute('aria-busy','false');await expect(page.getByText('Loading selected graphs…',{exact:true})).toHaveCount(0);await expect(page.getByRole('alert')).toHaveCount(0);await expect(page.locator('.filter-count')).toHaveText(/[1-9]\d* groups/);}
async function graphs(page){const menu=page.locator('.workspace-graph-picker');if(!await menu.evaluate(e=>e.open))await menu.locator(':scope > summary').click();return page.getByRole('group',{name:'Graphs to display'});}

test('original workspace shell contains all graph modes, filters and inspector on one page',async({page})=>{
 const errors=[];page.on('pageerror',e=>errors.push(e.message));await page.goto('/');await ready(page);
 await expect(page.getByRole('link',{name:'Geo Grapher home'})).toBeVisible();
 await expect(page.getByRole('complementary',{name:'Repository hierarchy'})).toBeVisible();
 await expect(page.getByRole('complementary',{name:'Entity details'})).toBeVisible();
 await expect(page.getByRole('combobox',{name:'Repository snapshot'})).toBeVisible();
 await expect(page.getByRole('combobox',{name:'Abstraction grouping'})).toBeVisible();
 await expect(page.locator('iframe')).toHaveCount(0);
 await page.getByRole('button',{name:'List',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Visible architecture groups'})).toBeVisible();
 await expect(page.locator('.list-entity').filter({hasText:'Alpha'})).toHaveCount(1);
 await expect(page.locator('.list-entity').filter({hasText:'Beta'})).toHaveCount(1);
 await page.getByRole('button',{name:'Matrix',exact:true}).click();await expect(page.getByRole('table')).toBeVisible();
 await expect(page.locator('.matrix-zero')).toHaveCount(2); // No invented Alpha–Beta edges.
 await page.getByRole('button',{name:'3D space',exact:true}).click();await expect(page.locator('canvas')).toBeVisible();
 await expect(page).toHaveURL('http://127.0.0.1:8775/');expect(errors).toEqual([]);
});

test('list and matrix selections activate their graph and use the existing inspector',async({page,request})=>{
 const data=(await(await request.get('/api/graphs')).json()).graphs,beta=data.find(g=>g.label==='Beta');
 await page.goto('/');await ready(page);await page.getByRole('button',{name:'List',exact:true}).click();
 await page.locator('.list-entity').filter({hasText:'Beta'}).click();
 await expect(page.getByRole('combobox',{name:'Active graph'})).toHaveValue(beta.graph_id);
 await expect(page.getByRole('button',{name:'List',exact:true})).toHaveAttribute('aria-pressed','true');
 await expect(page.getByRole('tablist',{name:'Entity inspector'})).toBeVisible();
 await page.getByRole('button',{name:'Matrix',exact:true}).click();
 await page.getByRole('button',{name:/Alpha to Alpha: [1-9]/}).click();
 await expect(page.getByRole('combobox',{name:'Active graph'})).toHaveValue(data.find(g=>g.label==='Alpha').graph_id);
 await expect(page.getByRole('button',{name:'Matrix',exact:true})).toHaveAttribute('aria-pressed','true');
 await expect(page.locator('iframe')).toHaveCount(0);
 await expect(page.getByRole('alert')).toHaveCount(0);
});

test('main context, grouping and certainty controls apply to selected graphs',async({page})=>{
 await page.goto('/');await ready(page);
 const captured=page.waitForResponse(r=>r.url().endsWith('/api/graphs/frame')&&r.request().postDataJSON().graphs.every(g=>g.grouping?.mode==='atomic'&&g.filter?.resolution_statuses.includes('unresolved')&&g.context_radius===2));
 await page.getByRole('combobox',{name:'Relationship visibility preset'}).selectOption('all_uncertainty');
 await page.getByRole('combobox',{name:'Abstraction grouping'}).selectOption('atomic');await page.getByRole('button',{name:'Wider',exact:true}).click();
 const response=await captured;expect(response.ok()).toBeTruthy();const body=await response.json();expect(body.frames.every(f=>f.frame&&!f.error)).toBeTruthy();
 await expect(page.getByRole('alert')).toHaveCount(0);
 const findings=await new AxeBuilder({page}).include('.application').analyze();expect(findings.violations).toEqual([]);
 await page.screenshot({path:'output/integrated-workspace/main.png'});
});

test('graph checklist and centre selection do not navigate to another viewer',async({page,request})=>{
 await page.goto('/');await ready(page);let menu=await graphs(page);
 for(const item of await menu.getByRole('checkbox').all())if((await item.getAttribute('type'))==='checkbox'&&!((await item.textContent())||'').includes('bridges')){const label=await item.evaluate(e=>e.closest('label').textContent);if(!label.includes('bridges'))await item.uncheck();}
 await expect(page.locator('.filter-count')).toHaveText('0 groups · 0 curves');
 await page.reload();await expect(page.getByRole('searchbox',{name:'Search entities'})).toBeEnabled();menu=await graphs(page);
 await expect(menu.getByRole('checkbox',{name:'Alpha',exact:true})).not.toBeChecked();
 await menu.getByRole('checkbox',{name:'Alpha',exact:true}).check();await menu.getByRole('checkbox',{name:'Beta',exact:true}).check();
 const beta=(await(await request.get('/api/graphs')).json()).graphs.find(g=>g.label==='Beta');
 await menu.getByRole('button',{name:'Centre graph Beta'}).click();
 await expect.poll(()=>page.evaluate(()=>JSON.parse(localStorage.getItem('geographer.graphs.v1'))[0])).toBe(beta.graph_id);
 await expect(page.locator('iframe')).toHaveCount(0);await expect(page).toHaveURL('http://127.0.0.1:8775/');
});

test('reviewed merge remains an integrated tool; stale source plans are rejected',async({page,request})=>{
 await page.goto('/');await ready(page);await graphs(page);
 await page.getByText('Create a physically merged graph',{exact:true}).click();await page.getByLabel('New graph name').fill('Integrated union');
 await page.getByRole('button',{name:'Review merge plan'}).click();await expect(page.getByRole('region',{name:'Merge plan review'})).toBeVisible();
 expect((await request.post('/__qa/advance',{data:{}})).ok()).toBeTruthy();
 await page.getByLabel('I reviewed these sources and want a new merged graph.').check();await page.getByRole('button',{name:'Create reviewed merged graph'}).click();
 await expect(page.getByRole('alert').filter({hasText:'Merge plan changed'})).toBeVisible();
 await page.getByRole('button',{name:'Review merge plan'}).click();await page.getByLabel('I reviewed these sources and want a new merged graph.').check();await page.getByRole('button',{name:'Create reviewed merged graph'}).click();
 await expect.poll(async()=> (await(await request.get('/api/graphs')).json()).graphs.find(g=>g.label==='Integrated union')?.graph_id).toBeTruthy();
 await expect(page.getByRole('combobox',{name:'Active graph'})).toHaveValue((await(await request.get('/api/graphs')).json()).graphs.find(g=>g.label==='Integrated union').graph_id);
 await expect(page.locator('iframe')).toHaveCount(0);await expect(page.getByRole('combobox',{name:'Repository snapshot'})).toBeVisible();
});

test('old viewer links resolve to the same root workspace',async({page,request})=>{
 const alpha=(await(await request.get('/api/graphs')).json()).graphs.find(g=>g.label==='Alpha');
 await page.goto('/graphs/'+alpha.graph_id+'/?debug');await ready(page);
 expect(new URL(page.url()).pathname).toBe('/');await expect(page.getByRole('combobox',{name:'Active graph'})).toHaveValue(alpha.graph_id);
});

test('saved views restore graph selection and search remains scoped to the active graph',async({page,request})=>{
 await page.goto('/');await ready(page);let menu=await graphs(page);
 for(const choice of await menu.getByRole('checkbox').all()){
  const text=await choice.evaluate(e=>e.closest('label').textContent);if(!text.includes('Alpha')&&!text.includes('bridges'))await choice.uncheck();
 }
 await page.locator('.workspace-graph-picker > summary').click();
 await page.getByRole('button',{name:'Save view',exact:true}).click();await page.getByLabel('View name').fill('Only Alpha');
 await page.getByRole('button',{name:'Save',exact:true}).click();menu=await graphs(page);await menu.getByRole('checkbox',{name:'Beta',exact:true}).check();
 await page.locator('.workspace-graph-picker > summary').click();await page.getByRole('combobox',{name:'Restore saved view'}).selectOption('Only Alpha');
 menu=await graphs(page);await expect(menu.getByRole('checkbox',{name:'Beta',exact:true})).not.toBeChecked();
 await page.locator('.workspace-graph-picker > summary').click();
 const beta=(await(await request.get('/api/graphs')).json()).graphs.find(g=>g.label==='Beta');
 await page.getByRole('combobox',{name:'Active graph'}).selectOption(beta.graph_id);
 const response=page.waitForResponse(r=>r.url().includes('/graphs/'+beta.graph_id+'/api/v1/search_entities'));
 await expect(page.getByRole('searchbox',{name:'Search entities'})).toBeEnabled();await page.getByRole('searchbox',{name:'Search entities'}).fill('entry');
 const data=await(await response).json();expect(data.data.nodes.every(n=>n.repo_id===beta.graph_id)).toBeTruthy();
 await expect(page.locator('iframe')).toHaveCount(0);expect(new URL(page.url()).pathname).toBe('/');
});

async function moduleFrom(file){
 const code=ts.transpile(fs.readFileSync(file,'utf8'),{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext});
 return import('data:text/javascript;base64,'+Buffer.from(code).toString('base64'));
}

test('display transforms qualify IDs and preserve spline geometry and lane offsets',async()=>{
 const {composeScene}=await moduleFrom('frontend/src/composition.ts');
 const {samples}=await moduleFrom('frontend/src/curves.ts');
 const curve={relationship_id:'edge',canonical_source:'a',canonical_target:'b',reversed:false,control_points:[[0,0,0],[1,2,1],[3,1,0],[4,0,0]],degree:3,knots:[0,0,0,0,1,1,1,1],normal:[0,1,0],binormal:[0,0,1],lane_index:1,lane_count:2,lane_spacing:.08,sample_count:48};
 const frame={nodes:[{id:'a',entity_id:'a',parent_id:null,kind:'function'},{id:'b',entity_id:'b',parent_id:'a',kind:'function'}],relationships:[{id:'edge',source:'a',target:'b'}],spheres:[{node_id:'a',center:[0,0,0],radius:1},{node_id:'b',center:[4,0,0],radius:.5}],curves:[curve]};
 const input={frames:['graph-A','graph-B'].map((graph_id,i)=>({graph_id,snapshot_id:'snapshot',root_id:'root',label:graph_id,transform:{scale:2,translation:[i*20,3,4]},frame}))};
 const rendered=composeScene(input);
 expect(new Set(rendered.data.nodes.map(n=>n.id)).size).toBe(4);
 expect(new Set(rendered.data.relationships.map(n=>n.id)).size).toBe(2);
 expect(rendered.origins.get(rendered.data.nodes[2].id).graph_id).toBe('graph-B');
 const lens={enabled:false,center:[0,0,0],radius:5,strength:.8};
 const before=samples(curve,.8,lens),after=samples(rendered.data.curves[1],.8,lens);
 for(let i=0;i<before.length;i++)for(let j=0;j<3;j++)expect(after[i][j]).toBeCloseTo(before[i][j]*2+[20,3,4][j],10);
 expect(frame.curves[0].lane_spacing).toBe(.08);
});

