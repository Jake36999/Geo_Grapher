const {test,expect}=require('@playwright/test');
const fs=require('node:fs'),ts=require('typescript');
async function editing(){
 const js=ts.transpile(fs.readFileSync('frontend/src/layoutEditing.ts','utf8'),{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext});
 return import('data:text/javascript;base64,'+Buffer.from(js).toString('base64'));
}
test('affine group edits preserve subtrees, source data and endpoint closure',async()=>{
 const {editSelection,editedScene,selectionRoots}=await editing();
 const raw={nodes:[{id:'p',parent_id:null},{id:'a',parent_id:'p'},{id:'b',parent_id:null}],relationships:[{id:'r',source:'a',target:'b'}],spheres:[{node_id:'p',center:[0,0,0],radius:3},{node_id:'a',center:[1,0,0],radius:1},{node_id:'b',center:[10,0,0],radius:1}],curves:[{relationship_id:'r',canonical_source:'a',canonical_target:'b',control_points:[[1,0,0],[4,3,0],[10,0,0]],lane_spacing:.1}]};
 const original=JSON.stringify(raw),edits=new Map();
 expect(selectionRoots(raw,['p','a'])).toEqual(['p']);
 editSelection(raw,edits,['p','a'],[0,0,0],2,[2,1,0]);
 const shown=editedScene(raw,edits);
 expect(shown.spheres[1].center).toEqual([4,1,0]);
 expect(shown.spheres[1].radius).toBe(2);
 expect(shown.spheres[2].center).toEqual([10,0,0]);
 expect(shown.curves[0].control_points[0]).toEqual(shown.spheres[1].center);
 expect(shown.curves[0].control_points.at(-1)).toEqual(shown.spheres[2].center);
 expect(JSON.stringify(raw)).toBe(original);
 const expanded={...raw,nodes:[...raw.nodes,{id:'new',parent_id:'p'}],spheres:[...raw.spheres,{node_id:'new',center:[0,1,0],radius:.5}]};
 expect(editedScene(expanded,edits).spheres.at(-1).center).toEqual([2,3,0]);
 editSelection(raw,edits,['p'],[0,0,0],1e9,[0,0,0]);
 expect(editedScene(raw,edits).spheres[0].radius).toBe(30);
});

async function targets(canvas){if(await canvas.getAttribute('data-layout-targets-revision')!==await canvas.getAttribute('data-layout-revision'))return [];return JSON.parse(await canvas.getAttribute('data-layout-targets')||'[]');}
test('bubble rim hold-wheel resizes and rim drag moves without moving the camera',async({page})=>{
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('/collection/?debug');
 const scene=page.getByRole('region',{name:'Shared detailed scene'}),canvas=scene.locator('canvas');
 await expect(page.locator('.filter-count')).toHaveText(/[1-9]\d* groups/);
 await canvas.scrollIntoViewIfNeeded();
 await page.getByRole('button',{name:'Wider',exact:true}).click();await expect(page.locator('.view-content')).toHaveAttribute('aria-busy','false');await expect.poll(async()=> (await targets(canvas)).length).toBeGreaterThan(2);
 const box=await canvas.boundingBox();
 let target=(await targets(canvas)).filter(p=>p.r>=15&&p.x+p.r<box.x+box.width-10&&p.y>box.y+60&&p.y<box.y+box.height-50).sort((a,b)=>b.r-a.r)[0];
 expect(target).toBeTruthy();const id=target.id,oldRadius=target.r;
 await page.mouse.move(target.x+target.r,target.y);await page.mouse.down();await page.mouse.wheel(0,-180);await page.mouse.up();
 await expect.poll(async()=> (await targets(canvas)).find(p=>p.id===id)?.r??0).toBeGreaterThan(oldRadius*1.15);
 await expect(scene.getByTestId('layout-selection-status')).toHaveText('1 selected');
 target=(await targets(canvas)).find(p=>p.id===id);const oldX=target.x;
 await page.mouse.move(target.x+target.r,target.y);await page.mouse.down();await page.mouse.move(target.x+target.r+45,target.y+15,{steps:5});await page.mouse.up();
 await expect.poll(async()=> (await targets(canvas)).find(p=>p.id===id)?.x??0).toBeGreaterThan(oldX+20);
 await scene.getByRole('button',{name:'Reset layout',exact:true}).click();
 await expect(scene.getByTestId('layout-selection-status')).toHaveText('0 selected');
 await expect.poll(async()=> (await targets(canvas)).find(p=>p.id===id)?.r??0).toBeCloseTo(oldRadius,1);
 target=(await targets(canvas)).find(p=>p.id===id);
 await page.mouse.move(target.x+target.r,target.y);await page.mouse.down();await page.mouse.wheel(0,-180);
 await page.keyboard.press('Escape');await page.mouse.up();
 await expect(scene.getByTestId('layout-selection-status')).toHaveText('0 selected');
 await expect.poll(async()=> (await targets(canvas)).find(p=>p.id===id)?.r??0).toBeCloseTo(oldRadius,1);
 expect(errors).toEqual([]);
});

test('drag box selects a group; held wheel and drag edit it together; keyboard controls work',async({page})=>{
 await page.goto('/collection/?debug');
 const scene=page.getByRole('region',{name:'Shared detailed scene'}),canvas=scene.locator('canvas');
 await page.getByRole('button',{name:'Wider',exact:true}).click();
 await expect(page.locator('.view-content')).toHaveAttribute('aria-busy','false');
 await expect(page.locator('.filter-count')).toHaveText(/[1-9]\d* groups/);
 await canvas.scrollIntoViewIfNeeded();const bounds=await canvas.boundingBox();
 await page.mouse.move(bounds.x+12,bounds.y+75);await page.keyboard.down('Shift');await page.mouse.down();
 await page.mouse.move(bounds.x+bounds.width-12,bounds.y+bounds.height-45,{steps:8});await page.mouse.up();await page.keyboard.up('Shift');
 await expect.poll(async()=>Number((await scene.getByTestId('layout-selection-status').textContent()).split(' ')[0])).toBeGreaterThan(1);
 const selected=scene.getByTestId('layout-selection');await expect(selected).toBeVisible();
 const before=await selected.boundingBox();const x=before.x+before.width/2,y=before.y+before.height/2;
 await page.mouse.move(x,y);await page.mouse.down();await page.mouse.wheel(0,-140);await page.mouse.move(x+30,y+10,{steps:4});await page.mouse.up();
 await expect.poll(async()=> (await selected.boundingBox()).width).toBeGreaterThan(before.width+5);
 const width=(await selected.boundingBox()).width;
 await scene.getByRole('button',{name:'Size +: enlarge selected nodes',exact:true}).click();
 await expect.poll(async()=> (await selected.boundingBox()).width).toBeGreaterThan(width+3);
 await scene.getByRole('button',{name:'Move selected nodes right',exact:true}).click();
 await scene.getByRole('button',{name:'Reset layout',exact:true}).click();
 await expect(selected).toBeHidden();
 await page.screenshot({path:'output/spatial-controls/manipulation-workspace.png'});
});

test('the integrated main workspace keeps box editing and light-theme controls',async({page,request})=>{
 const AxeBuilder=require('@axe-core/playwright').default;
 const graphs=(await(await request.get('/api/graphs')).json()).graphs;
 const alpha=graphs.find(g=>g.label==='Alpha');
 await page.goto(`/graphs/${alpha.graph_id}/?view=spatial&debug`);
 const canvas=page.locator('canvas');
 await expect(page.getByRole('searchbox',{name:'Search entities'})).toBeEnabled();
 await page.getByRole('button',{name:'Wider',exact:true}).click();
 await expect.poll(async()=> (await targets(canvas)).length).toBeGreaterThan(1);
 const box=await canvas.boundingBox();
 await page.getByRole('button',{name:'Box select',exact:true}).click();
 await page.mouse.move(box.x+12,box.y+80);await page.mouse.down();
 await page.mouse.move(box.x+box.width-12,box.y+box.height-48,{steps:5});await page.mouse.up();
 await expect(page.getByTestId('layout-selection-status')).not.toHaveText('0 selected');
 await page.getByRole('button',{name:'Size +: enlarge selected nodes',exact:true}).click();
 await page.getByRole('button',{name:'Reset layout',exact:true}).click();
 await page.getByRole('button',{name:'Use light theme',exact:true}).click();
 const results=await new AxeBuilder({page}).include('.scene-host').analyze();
 expect(results.violations).toEqual([]);
});
