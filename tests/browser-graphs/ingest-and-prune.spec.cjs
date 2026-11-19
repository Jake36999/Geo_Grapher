const {test,expect}=require('@playwright/test');
const {showGraphsMode,openSettings,useTheme}=require('../browser/panel-helpers.cjs');
async function graphsMenu(page){await showGraphsMode(page);const menu=page.locator('.workspace-graph-picker');if(!await menu.evaluate(e=>e.open))await menu.locator(':scope > summary').click();return page.getByRole('group',{name:'Graphs to display'});}
// Other specs expect only the fixture's Alpha/Beta graphs: delete every graph this file creates.
let baseline=null;
test.beforeAll(async({request})=>{baseline=new Set((await(await request.get('/api/graphs')).json()).graphs.map(g=>g.graph_id));});
test.afterAll(async({request})=>{
 for(const g of (await(await request.get('/api/graphs')).json()).graphs)
  if(!baseline.has(g.graph_id))await request.delete(`/api/graphs/${g.graph_id}`,{data:{confirm_label:g.label}});
});
const watch=page=>{const errors=[];page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});return errors;};

test('add folder: browse, toggle a partition off, ingest; the new graph appears',async({page,request})=>{
 const errors=watch(page);
 const before=(await(await request.get('/api/graphs')).json()).graphs.length;
 await page.goto('/');await expect(page.getByRole('searchbox',{name:'Search entities'})).toBeEnabled();
 await graphsMenu(page);
 await page.getByRole('button',{name:'Add folder…'}).click();
 const panel=page.getByRole('region',{name:'Add folder'});
 await expect(panel.getByTestId('ingest-path')).toContainText('ws');
 await panel.getByRole('button',{name:'Preview this folder'}).click();
 const table=panel.getByRole('table',{name:'Ingest preview'});await expect(table).toBeVisible();
 const boxes=table.getByRole('checkbox');expect(await boxes.count()).toBeGreaterThan(1);
 await table.getByRole('checkbox',{name:'Ingest partition docs'}).uncheck();
 await panel.getByRole('button',{name:'Ingest selected partitions'}).click();
 await expect(panel.getByTestId('ingest-job-state')).toHaveText(/Job done/,{timeout:60000});
 await expect.poll(async()=>(await(await request.get('/api/graphs')).json()).graphs.length).toBe(before+(await boxes.count())-1);
 expect(errors).toEqual([]);
});

test('box-select nodes, prune: a derived graph appears and the source is unchanged',async({page,request})=>{
 const errors=watch(page);
 const graphs=(await(await request.get('/api/graphs')).json()).graphs;const alpha=graphs.find(g=>g.label==='Alpha');
 await page.goto(`/graphs/${alpha.graph_id}/?view=spatial&debug`);
 await expect(page.getByRole('searchbox',{name:'Search entities'})).toBeEnabled();
 await page.getByRole('button',{name:'Wider',exact:true}).click();
 const canvas=page.locator('canvas');await canvas.scrollIntoViewIfNeeded();const box=await canvas.boundingBox();
 await page.getByRole('button',{name:'Box select',exact:true}).click();
 await page.mouse.move(box.x+64,box.y+80);await page.mouse.down();
 await page.mouse.move(box.x+box.width-12,box.y+box.height-48,{steps:5});await page.mouse.up();
 await expect(page.getByTestId('layout-selection-status')).not.toHaveText('0 selected');
 await page.getByRole('button',{name:'Prune selection…'}).click();
 const form=page.getByRole('form',{name:'Prune selection'});await expect(form).toBeVisible();
 await form.getByLabel('New graph label').fill('Alpha pruned');
 await form.getByRole('button',{name:'Create pruned graph'}).click();
 await expect(form.getByRole('status')).toContainText('Created derived graph',{timeout:60000});
 const after=(await(await request.get('/api/graphs')).json()).graphs;
 expect(after.find(g=>g.label==='Alpha pruned')).toBeTruthy();
 expect(after.find(g=>g.graph_id===alpha.graph_id).snapshot_id).toBe(alpha.snapshot_id);
 expect(errors).toEqual([]);
});
