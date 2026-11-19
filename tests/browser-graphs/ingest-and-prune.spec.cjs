const {test,expect}=require('@playwright/test');
const {showGraphsMode,showBuildMode,openSettings,useTheme}=require('../browser/panel-helpers.cjs');
async function graphsMenu(page){await showGraphsMode(page);const menu=page.locator('.workspace-graph-picker');if(!await menu.evaluate(e=>e.open))await menu.locator(':scope > summary').click();return page.getByRole('group',{name:'Graphs to display'});}
// Other specs expect only the fixture's Alpha/Beta graphs: delete every graph this file creates.
let baseline=null;
test.beforeAll(async({request})=>{baseline=new Set((await(await request.get('/api/graphs')).json()).graphs.map(g=>g.graph_id));});
test.afterAll(async({request})=>{
 for(const g of (await(await request.get('/api/graphs')).json()).graphs)
  if(!baseline.has(g.graph_id))await request.delete(`/api/graphs/${g.graph_id}`,{data:{confirm_label:g.label}});
});
const watch=page=>{const errors=[];page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});return errors;};

test('add folder: read it, review the folder map, untick a part, ingest; the new graph appears',async({page,request})=>{
 const errors=watch(page);
 const before=(await(await request.get('/api/graphs')).json()).graphs.length;
 await page.goto('/');await expect(page.getByRole('searchbox',{name:'Search entities'})).toBeEnabled();
 await showBuildMode(page);
 await page.getByRole('button',{name:'Add folder…'}).click();
 const panel=page.getByRole('region',{name:'Add folder'});
 await expect(panel.getByTestId('ingest-path')).toContainText('ws');
 await panel.getByRole('button',{name:'Read this folder'}).click();
 const sheet=page.getByRole('dialog',{name:'How this folder was read'});await expect(sheet).toBeVisible();
 const map=sheet.getByRole('list',{name:'Folder map'});
 const boxes=map.getByRole('checkbox');const total=await boxes.count();expect(total).toBeGreaterThan(2);
 for(let i=0;i<total;i++)await expect(boxes.nth(i)).toBeChecked(); // every part starts ticked, the unlicensed one too
 await map.getByRole('checkbox',{name:'Ingest docs',exact:true}).uncheck();
 await sheet.getByRole('button',{name:`Ingest ${total-1} selected part${total-1===1?'':'s'}`}).click();
 await expect(sheet).toBeHidden();
 await expect(panel.getByTestId('ingest-job-state')).toHaveText(/Job done: added \d+ graphs?\. They are in the Graphs tab/,{timeout:60000});
 await expect.poll(async()=>(await(await request.get('/api/graphs')).json()).graphs.length).toBe(before+total-1);
 expect(errors).toEqual([]);
});

test('the folder map labels an unlicensed source as cited, never withholds it; the text version copies',async({page,request,context})=>{
 const errors=watch(page);
 await context.grantPermissions(['clipboard-read','clipboard-write']);
 await page.goto('/');await expect(page.getByRole('searchbox',{name:'Search entities'})).toBeEnabled();
 await showBuildMode(page);
 await page.getByRole('button',{name:'Add folder…'}).click();
 const panel=page.getByRole('region',{name:'Add folder'});await expect(panel.getByTestId('ingest-path')).toContainText('ws');
 await panel.getByRole('button',{name:'Read this folder'}).click();
 const sheet=page.getByRole('dialog',{name:'How this folder was read'});await expect(sheet).toBeVisible();
 const map=sheet.getByRole('list',{name:'Folder map'});
 // the innermost list item holding the vendor checkbox is the vendor row (the root item holds it too)
 const vendor=map.getByRole('listitem').filter({has:page.getByRole('checkbox',{name:'Ingest vendor',exact:true})}).last();
 await expect(vendor).toContainText('third-party');
 await expect(vendor).toContainText('cited, not published as our own');
 await expect(vendor).toContainText('no licence file');
 await expect(map.getByRole('checkbox',{name:'Ingest vendor',exact:true})).toBeChecked(); // labelled, not left out
 await expect(sheet).toContainText('is still brought in and copied');
 // the text version
 await sheet.getByText('Text version',{exact:true}).click();
 const text=sheet.locator('#ingest-map-text');await expect(text).toBeVisible();
 await expect(text).toContainText('├─ docs/');
 await expect(text).toContainText('third-party · cited, not published as our own · no licence file');
 await sheet.getByRole('button',{name:'Copy as ASCII'}).click();
 await expect(sheet.getByRole('status')).toHaveText('Copied the text map.');
 const pasted=await page.evaluate(()=>navigator.clipboard.readText());
 expect(pasted.replace(/\r\n/g,'\n')).toBe((await text.innerText()).replace(/\n$/,'')); // Windows' clipboard stores CRLF
 // Escape closes the sheet without ingesting
 await page.keyboard.press('Escape');await expect(sheet).toBeHidden();
 await expect(panel.getByRole('button',{name:'Review the folder map'})).toBeVisible();
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
 // the function `util`, found by its own label: it lives in one of Alpha's two files, so the selection is a part
 // of the graph and there is something to cut (a fixed rectangle would depend on how many graphs are showing)
 const label=await page.getByText('util',{exact:true}).first().boundingBox();expect(label).toBeTruthy();
 const centre=label.x+label.width/2;
 await page.mouse.move(centre-40,label.y+label.height+4);await page.mouse.down();
 await page.mouse.move(centre+40,label.y+label.height+84,{steps:5});await page.mouse.up();
 await expect(page.getByTestId('layout-selection-status')).not.toHaveText('0 selected'); // util and its module scope: both in util.py
 await page.getByRole('button',{name:'Keep only or remove selection…'}).click();
 // the choice is made in the Build tab, which opens by itself
 await expect(page.getByRole('tab',{name:'Build',exact:true})).toHaveAttribute('aria-selected','true');
 const form=page.getByRole('form',{name:'Keep only or remove the selection'});await expect(form).toBeVisible();
 // the counts come first, from the source graph, before anything is made
 await expect(form.getByTestId('derive-preview')).toContainText(/^Keeps 1 of 2 files/);
 await form.getByRole('radio',{name:'Remove these'}).check();
 await expect(form.getByTestId('derive-preview')).toContainText(/^Removes 1 of 2 files/);
 await form.getByRole('radio',{name:'Keep only these'}).check();
 await expect(form.getByTestId('derive-preview')).toContainText(/^Keeps 1 of 2 files/);
 await expect(form.getByRole('button',{name:'Create graph of only these'})).toBeDisabled(); // no name yet
 await form.getByLabel('New graph name').fill('Alpha pruned');
 await form.getByRole('button',{name:'Create graph of only these'}).click();
 await expect(form.getByRole('status')).toContainText('Made “Alpha pruned”',{timeout:60000});
 const after=(await(await request.get('/api/graphs')).json()).graphs;
 expect(after.find(g=>g.label==='Alpha pruned')).toBeTruthy();
 expect(after.find(g=>g.graph_id===alpha.graph_id).snapshot_id).toBe(alpha.snapshot_id);
 expect(errors).toEqual([]);
});

test('selecting every file cannot make a graph: the counts say nothing would change and the button stays off',async({page})=>{
 const graphs=(await(await page.request.get('/api/graphs')).json()).graphs;const alpha=graphs.find(g=>g.label==='Alpha');
 await page.goto(`/graphs/${alpha.graph_id}/?view=spatial&debug`);
 await expect(page.getByRole('searchbox',{name:'Search entities'})).toBeEnabled();
 await page.getByRole('button',{name:'Wider',exact:true}).click();
 const box=await page.locator('canvas').boundingBox();
 await page.getByRole('button',{name:'Box select',exact:true}).click();
 await page.mouse.move(box.x+64,box.y+80);await page.mouse.down();
 await page.mouse.move(box.x+box.width-12,box.y+box.height-48,{steps:5});await page.mouse.up();
 await page.getByRole('button',{name:'Keep only or remove selection…'}).click();
 const form=page.getByRole('form',{name:'Keep only or remove the selection'});
 await form.getByLabel('New graph name').fill('Everything');
 await expect(form.getByTestId('derive-preview')).toContainText('covers every file, so keeping only it would change nothing');
 await expect(form.getByRole('button',{name:'Create graph of only these'})).toBeDisabled();
 await form.getByRole('radio',{name:'Remove these'}).check();
 await expect(form.getByTestId('derive-preview')).toContainText('nothing would be left');
 await expect(form.getByRole('button',{name:'Create graph without these'})).toBeDisabled();
 await form.getByRole('button',{name:'Clear selection'}).click();
 await expect(page.getByRole('form',{name:'Keep only or remove the selection'})).toHaveCount(0);
 expect((await(await page.request.get('/api/graphs')).json()).graphs.some(g=>g.label==='Everything')).toBe(false);
});
