const {test,expect}=require('@playwright/test');
async function graphsMenu(page){const menu=page.locator('.workspace-graph-picker');if(!await menu.evaluate(e=>e.open))await menu.locator(':scope > summary').click();return page.getByRole('group',{name:'Graphs to display'});}

test('copy a graph, then delete the copy with label confirmation',async({page,request})=>{
 const errors=[];page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
 await page.goto('/');await expect(page.getByRole('searchbox',{name:'Search entities'})).toBeEnabled();
 let menu=await graphsMenu(page);
 await menu.getByRole('button',{name:'Copy graph Alpha'}).click();
 await page.getByLabel('Copy label').fill('Alpha lifecycle copy');
 await page.getByRole('button',{name:'Create copy'}).click();
 await expect(menu.getByRole('checkbox',{name:'Alpha lifecycle copy',exact:true})).toBeVisible();
 const copy=(await(await request.get('/api/graphs')).json()).graphs.find(g=>g.label==='Alpha lifecycle copy');
 expect(copy.owned_store).toBe(true);expect(copy.copied_from).toBeTruthy();
 // Active toggle updates the server-side set.
 await menu.getByRole('button',{name:'Active set Alpha lifecycle copy'}).click();
 await expect.poll(async()=>(await(await request.get('/api/workspace/active-graphs')).json()).graph_ids).toContain(copy.graph_id);
 // Delete requires the exact label.
 await menu.getByRole('button',{name:'Delete graph Alpha lifecycle copy'}).click();
 const dialog=page.getByRole('group',{name:'Delete graph'});
 await expect(dialog).toContainText('0 bridges');await expect(dialog).toContainText('owned');
 await expect(dialog.getByRole('button',{name:'Delete graph'})).toBeDisabled();
 await dialog.getByLabel('Type the graph label to confirm').fill('Alpha lifecycle copy');
 await dialog.getByRole('button',{name:'Delete graph'}).click();
 await expect(menu.getByRole('checkbox',{name:'Alpha lifecycle copy',exact:true})).toHaveCount(0);
 const rest=(await(await request.get('/api/graphs')).json()).graphs;
 expect(rest.find(g=>g.graph_id===copy.graph_id)).toBeUndefined();
 expect((await(await request.get('/api/workspace/active-graphs')).json()).graph_ids).not.toContain(copy.graph_id);
 expect(errors).toEqual([]);
});
