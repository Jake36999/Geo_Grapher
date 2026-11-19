const {test,expect}=require('@playwright/test');
const {showGraphsMode,showBuildMode,openSettings,useTheme}=require('../browser/panel-helpers.cjs');
async function graphsMenu(page){await showGraphsMode(page);const menu=page.locator('.workspace-graph-picker');if(!await menu.evaluate(e=>e.open))await menu.locator(':scope > summary').click();return page.getByRole('group',{name:'Graphs to display'});}

test('review bridge candidates: accept one with a rationale creates exactly one bridge',async({page,request})=>{
 const errors=[];page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
 await page.goto('/');await expect(page.getByRole('searchbox',{name:'Search entities'})).toBeEnabled();
 const graphs=(await(await request.get('/api/graphs')).json()).graphs.filter(g=>g.label==='Alpha'||g.label==='Beta');
 const ids=graphs.map(g=>g.graph_id);
 const count=async()=>(await(await request.post('/api/graphs/bridges',{data:{graph_ids:ids}})).json()).bridges.length;
 const before=await count();
 const menu=await graphsMenu(page);
 for(const label of ['Alpha','Beta']){const box=menu.getByRole('checkbox',{name:label,exact:true});if(!await box.isChecked())await box.check();}
 await showBuildMode(page);
 const panel=page.locator('details.bridge-review');await panel.locator(':scope > summary').click();
 await panel.getByRole('button',{name:'Find candidates'}).click();
 const list=panel.getByRole('list',{name:'Bridge candidates'});await expect(list.getByRole('listitem').first()).toBeVisible();
 const first=list.getByRole('listitem').first();
 await expect(first.getByRole('button',{name:'Accept'})).toBeDisabled();  // a rationale is required
 await first.getByPlaceholder('Rationale (required)').fill('Reviewed: same helper in both fixtures');
 await first.getByRole('button',{name:'Accept'}).click();
 await expect.poll(count).toBe(before+1);
 expect(errors).toEqual([]);
});
