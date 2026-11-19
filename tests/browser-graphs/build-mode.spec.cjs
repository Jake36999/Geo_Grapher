const {test,expect}=require('@playwright/test');
const AxeBuilder=require('@axe-core/playwright').default;
const {showBuildMode,showInspectMode}=require('../browser/panel-helpers.cjs');
async function ready(page){await expect(page.getByRole('searchbox',{name:'Search entities'})).toBeEnabled();await expect(page.locator('.view-content')).toHaveAttribute('aria-busy','false');}

test('the right panel has a Build tab that holds Add a folder, Keep only or remove, Combine, Compare and Link, and the arrow keys cycle all three tabs',async({page})=>{
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('/');await ready(page);
 const tabs=page.getByRole('tablist',{name:'Right panel'}).getByRole('tab');
 await expect(tabs).toHaveText(['Inspect','Graphs','Build']);
 const build=page.getByRole('tab',{name:'Build',exact:true});
 await build.click();await expect(build).toHaveAttribute('aria-selected','true');
 const panel=page.getByRole('tabpanel',{name:'Build'});
 for(const heading of ['Add a folder','Keep only or remove','Combine graphs','Compare graphs','Link graphs'])await expect(panel.getByRole('heading',{name:heading})).toBeVisible();
 await expect(panel.getByRole('button',{name:'Add folder…'})).toBeVisible();
 await expect(panel.getByText('Sources are never changed',{exact:false})).toBeVisible();
 // what moved out of the Graphs tab
 await page.getByRole('tab',{name:'Graphs',exact:true}).click();
 await expect(page.getByRole('button',{name:'Add folder…'})).toHaveCount(0);
 await expect(page.getByText('Create a physically merged graph')).toHaveCount(0);
 // roving tabs: Right from Graphs reaches Build, Right again wraps to Inspect
 await page.getByRole('tab',{name:'Graphs',exact:true}).focus();
 await page.keyboard.press('ArrowRight');await expect(build).toHaveAttribute('aria-selected','true');
 await page.keyboard.press('ArrowRight');await expect(page.getByRole('tab',{name:'Inspect',exact:true})).toHaveAttribute('aria-selected','true');
 await page.keyboard.press('ArrowLeft');await expect(build).toHaveAttribute('aria-selected','true'); // and back round
 expect(errors).toEqual([]);
});

test('the Build tab is remembered for the tab, and picking an entity still returns to Inspect',async({page})=>{
 await page.goto('/');await ready(page);
 await showBuildMode(page);
 await page.reload();await ready(page);
 await expect(page.getByRole('tab',{name:'Build',exact:true})).toHaveAttribute('aria-selected','true');
 await page.getByRole('tab',{name:'Graphs',exact:true}).click();
 await page.locator('.hierarchy-tree button:not([aria-label^="Collapse"]):not([aria-label^="Expand"])').first().click();
 await expect(page.getByRole('tab',{name:'Inspect',exact:true})).toHaveAttribute('aria-selected','true');
 await showInspectMode(page);
});

test('the Build tab and the folder map sheet have no accessibility violations in dark or light',async({page})=>{
 await page.goto('/');await ready(page);
 await showBuildMode(page);
 let results=await new AxeBuilder({page}).include('.inspector-panel').analyze();
 expect(results.violations.map(v=>v.id)).toEqual([]);
 await page.getByRole('button',{name:'Add folder…'}).click();
 const panel=page.getByRole('region',{name:'Add folder'});await expect(panel.getByTestId('ingest-path')).toContainText('ws');
 await panel.getByRole('button',{name:'Read this folder'}).click();
 const sheet=page.getByRole('dialog',{name:'How this folder was read'});await expect(sheet).toBeVisible();
 for(const theme of ['dark','light']){
  await page.evaluate(t=>{document.documentElement.dataset.theme=t;},theme);
  results=await new AxeBuilder({page}).include('dialog.ingest-sheet').analyze();
  expect(results.violations.map(v=>`${theme}: ${v.id}`)).toEqual([]);
 }
 // the sheet fits a phone: no sideways scroll inside it
 await page.setViewportSize({width:390,height:800});
 const fits=await sheet.evaluate(e=>e.scrollWidth<=e.clientWidth+1);
 expect(fits).toBe(true);
 await page.keyboard.press('Escape');await expect(sheet).toBeHidden();
});

test('a wrong role guess is corrected in the sheet: the labels follow and only the correction is sent',async({page})=>{
 await page.goto('/');await ready(page);await showBuildMode(page);
 let sent;
 // the ingest itself is covered elsewhere; here only what the sheet sends matters
 await page.route('**/api/workspace/ingest-execute',async route=>{sent=route.request().postDataJSON();await route.fulfill({json:{job_id:'job_fake'}});});
 await page.route('**/api/workspace/jobs/job_fake',route=>route.fulfill({json:{state:'done',reports:[],error:null}}));
 await page.getByRole('button',{name:'Add folder…'}).click();
 const panel=page.getByRole('region',{name:'Add folder'});await expect(panel.getByTestId('ingest-path')).toContainText('ws');
 await panel.getByRole('button',{name:'Read this folder'}).click();
 const sheet=page.getByRole('dialog',{name:'How this folder was read'});await expect(sheet).toBeVisible();
 const role=sheet.getByRole('combobox',{name:'Role of vendor'});
 await expect(role).toHaveValue('third_party');
 await expect(sheet.getByText('cited, not published as our own',{exact:true})).toBeVisible();
 await expect(sheet.getByText('no licence file',{exact:true})).toBeVisible();
 // the person says this is their own work
 await role.selectOption('current');
 await expect(sheet.getByText('cited, not published as our own',{exact:true})).toHaveCount(0);
 await expect(sheet.getByText('no licence file',{exact:true})).toHaveCount(0);
 await expect(sheet.getByText('you chose “own”; the scan suggested “third-party”')).toBeVisible();
 await expect(sheet.getByText('1 role changed by you')).toBeVisible();
 // the pasteable text follows the correction too
 await sheet.getByText('Text version').click();
 await expect(sheet.locator('#ingest-map-text')).not.toContainText('third-party');
 await sheet.getByRole('button',{name:/^Ingest \d+ selected parts?$/}).click();
 await expect.poll(()=>sent).toBeTruthy();
 expect(sent.role_overrides).toEqual({vendor:'current'}); // only what the person changed
 expect(sent.approved_keys).toContain('vendor');
 await expect(panel.getByTestId('ingest-job-state')).toContainText('done');
});

test('the sheet sends no corrections when none were made, and choosing the suggestion again clears one',async({page})=>{
 await page.goto('/');await ready(page);await showBuildMode(page);
 let sent;
 await page.route('**/api/workspace/ingest-execute',async route=>{sent=route.request().postDataJSON();await route.fulfill({json:{job_id:'job_fake'}});});
 await page.route('**/api/workspace/jobs/job_fake',route=>route.fulfill({json:{state:'done',reports:[],error:null}}));
 await page.getByRole('button',{name:'Add folder…'}).click();
 await page.getByRole('region',{name:'Add folder'}).getByRole('button',{name:'Read this folder'}).click();
 const sheet=page.getByRole('dialog',{name:'How this folder was read'});
 const role=sheet.getByRole('combobox',{name:'Role of vendor'});
 await role.selectOption('docs');await expect(sheet.getByText('1 role changed by you')).toBeVisible();
 await role.selectOption('third_party');await expect(sheet.getByText('role changed by you')).toHaveCount(0);
 await sheet.getByRole('button',{name:/^Ingest \d+ selected parts?$/}).click();
 await expect.poll(()=>sent).toBeTruthy();
 expect(sent.role_overrides).toEqual({});
});

test('compare two graphs: counts first, a sample behind each, and neither graph changes',async({page,request})=>{
 const before=(await(await request.get('/api/graphs')).json()).graphs.map(g=>g.snapshot_id).sort();
 await page.goto('/');await ready(page);await showBuildMode(page);
 const section=page.getByRole('region',{name:'Compare graphs'});
 await expect(section.getByRole('combobox',{name:/First/})).not.toHaveValue(await section.getByRole('combobox',{name:/Second/}).inputValue());
 await section.getByRole('button',{name:'Compare',exact:true}).click();
 const result=section.getByTestId('compare-result');await expect(result).toBeVisible();
 // Alpha and Beta carry the same two functions; Alpha has one more (util), which only it has
 await expect(result.getByRole('list',{name:'Comparison counts'})).toContainText(/2\s+Identical/);
 await expect(result.getByRole('list',{name:'Comparison counts'})).toContainText(/1\s+Only in Alpha/);
 await expect(result.getByRole('list',{name:'Comparison counts'})).toContainText(/0\s+Only in Beta/);
 await result.getByText(/^Only in Alpha \(1\)/).click();
 await expect(result.locator('.compare-list code',{hasText:'util'})).toBeVisible();
 await expect(result).toContainText('Compared: functions, methods and classes');
 await result.getByText(/^Identical \(2\)/).click();
 await expect(result.locator('.compare-list code').first()).toBeVisible();
 // a result belongs to the pair it was made for: choosing the other graph first swaps the pair
 await section.getByRole('combobox',{name:/First/}).selectOption({index:1});
 await expect(result).toHaveCount(0);
 for(const theme of ['dark','light']){
  await page.evaluate(t=>{document.documentElement.dataset.theme=t;},theme);
  const results=await new AxeBuilder({page}).include('.inspector-panel').analyze();
  expect(results.violations.map(v=>`${theme}: ${v.id}`)).toEqual([]);
 }
 expect((await(await request.get('/api/graphs')).json()).graphs.map(g=>g.snapshot_id).sort()).toEqual(before);
});

test('declare a link between two graphs and take it back: the graphs do not change',async({page,request})=>{
 const before=(await(await request.get('/api/graphs')).json()).graphs.map(g=>g.snapshot_id).sort();
 await page.goto('/');await ready(page);await showBuildMode(page);
 const section=page.getByRole('region',{name:'Link graphs'});
 const links=section.getByRole('list',{name:'Declared links'}).getByRole('listitem');
 const already=await links.count();expect(already).toBeGreaterThanOrEqual(1); // the fixture declares one, and an earlier spec may have accepted another
 const form=section.getByRole('form',{name:'Declare a link'});
 await expect(form.getByRole('button',{name:'Declare link'})).toBeDisabled(); // nothing chosen yet
 await form.getByRole('group',{name:'From'}).getByRole('button',{name:'Whole graph'}).click();
 await form.getByRole('group',{name:'To'}).getByRole('button',{name:'Whole graph'}).click();
 await expect(form.getByRole('button',{name:'Declare link'})).toBeDisabled(); // a reason is required
 await form.getByLabel('Why this link').fill('Alpha documents Beta in its README');
 await form.getByRole('button',{name:'Declare link'}).click();
 await expect(section.getByRole('status')).toContainText('Link declared');
 await expect(links).toHaveCount(already+1);
 const mine=links.filter({hasText:'Alpha documents Beta'});await expect(mine).toContainText('in force');await expect(mine).toContainText('declared by a person, not checked against the code');
 // taking it back asks first, and keeping it changes nothing
 await mine.getByRole('button',{name:/Take back the link/}).click();
 await mine.getByRole('button',{name:'Keep it'}).click();await expect(links).toHaveCount(already+1);
 await mine.getByRole('button',{name:/Take back the link/}).click();
 await mine.getByRole('button',{name:'Take it back'}).click();
 await expect(section.getByRole('status')).toContainText('Link taken back');
 await expect(links).toHaveCount(already);
 expect((await(await request.get('/api/graphs')).json()).graphs.map(g=>g.snapshot_id).sort()).toEqual(before);
});

test('the item selected on the canvas can be one end of a link, and a bad reference is refused with a reason',async({page})=>{
 await page.goto('/');await ready(page);
 await page.getByRole('tab',{name:'Graphs',exact:true}).click();
 await page.locator('.hierarchy-tree').getByRole('button',{name:'app.py',exact:true}).click();
 await showBuildMode(page);
 const section=page.getByRole('region',{name:'Link graphs'});
 await expect(section.getByRole('list',{name:'Declared links'}).getByRole('listitem').first()).toBeVisible(); // the list has loaded
 const already=await section.getByRole('list',{name:'Declared links'}).getByRole('listitem').count();
 const form=section.getByRole('form',{name:'Declare a link'});
 const from=form.getByRole('group',{name:'From'});
 await from.getByRole('button',{name:'Use the selected item'}).click();
 await expect(from.getByRole('textbox',{name:'From reference'})).toHaveValue(/^entity:/);
 await expect(from.getByText('app.py')).toBeVisible();
 // the other end is in another graph, so the selection cannot be used there
 await expect(form.getByRole('group',{name:'To'}).getByRole('button',{name:'Use the selected item'})).toBeDisabled();
 await form.getByRole('group',{name:'To'}).getByRole('textbox',{name:'To reference'}).fill('doc:99');
 await form.getByLabel('Why this link').fill('should be refused');
 await form.getByRole('button',{name:'Declare link'}).click();
 await expect(section.getByRole('alert')).toBeVisible();
 await expect(section.getByRole('list',{name:'Declared links'}).getByRole('listitem')).toHaveCount(already);
});

test('each graph has its own colour beside its name, which can be changed and is remembered',async({page})=>{
 await page.goto('/');await ready(page);
 await page.getByRole('tab',{name:'Graphs',exact:true}).click();
 await page.locator('.workspace-graph-picker > summary').click();
 const alpha=page.getByRole('combobox',{name:'Colour of Alpha'}),beta=page.getByRole('combobox',{name:'Colour of Beta'});
 await expect(page.locator('.workspace-graph-choice .graph-swatch')).toHaveCount(2);
 const first=await alpha.inputValue();expect(first).not.toBe(await beta.inputValue());
 const other=await beta.inputValue();
 await alpha.selectOption(other); // a person's choice wins; the other graph steps aside
 await expect(alpha).toHaveValue(other);await expect(beta).not.toHaveValue(other);
 await page.reload();await ready(page);
 await page.getByRole('tab',{name:'Graphs',exact:true}).click();
 await page.locator('.workspace-graph-picker > summary').click();
 await expect(page.getByRole('combobox',{name:'Colour of Alpha'})).toHaveValue(other);
 await page.evaluate(()=>localStorage.removeItem('geographer.accents.v1')); // leave the next test as it found it
});

test('an empty catalogue shows a way to add the first folder, not a loading message that never ends',async({page})=>{
 await page.route('**/api/graphs',route=>route.request().method()==='GET'?route.fulfill({json:{graphs:[]}}):route.continue());
 await page.goto('/');
 await expect(page.getByRole('heading',{name:'Geo Grapher'})).toBeVisible();
 await expect(page.getByText('There are no graphs yet.')).toBeVisible();
 await expect(page.getByText('Opening project graphs…')).toHaveCount(0);
 await page.getByRole('button',{name:'Add folder…'}).click();
 const panel=page.getByRole('region',{name:'Add folder'});await expect(panel.getByTestId('ingest-path')).toContainText('ws');
 await expect(panel.getByRole('button',{name:'Read this folder'})).toBeEnabled();
});

test('a file selected in the hierarchy can start a cut without the box tool, and says how to use the tool',async({page})=>{
 await page.goto('/');await ready(page);
 await page.getByRole('tab',{name:'Graphs',exact:true}).click();
 await page.locator('.hierarchy-tree').getByRole('button',{name:'app.py',exact:true}).click();
 await showBuildMode(page);
 const section=page.getByRole('region',{name:'Keep only or remove'});
 await expect(section).toContainText('Box select');
 await section.getByRole('button',{name:/^Use the selected file or folder: app\.py/}).click();
 const form=section.getByRole('form',{name:'Keep only or remove the selection'});
 await expect(form.getByTestId('derive-preview')).toContainText(/^Keeps 1 of 2 files/);
 await form.getByRole('button',{name:'Clear selection'}).click();
 await expect(form).toHaveCount(0);
});

test('Reveal nearby detail never sits on the canvas help text, at any width',async({page,request})=>{
 const alpha=(await(await request.get('/api/graphs')).json()).graphs.find(g=>g.label==='Alpha');
 // one graph on show (the button only appears then), whatever else the library holds
 await page.addInitScript(id=>localStorage.setItem('geographer.graphs.v1',JSON.stringify([id])),alpha.graph_id);
 for(const [width,height] of [[1440,1000],[768,1024],[375,812]]){
  await page.setViewportSize({width,height});
  await page.goto(`/graphs/${alpha.graph_id}/?view=spatial`);await ready(page);
  await page.getByRole('button',{name:'Path',exact:true}).click();
  const reveal=page.getByRole('button',{name:'Reveal nearby detail'});await expect(reveal).toBeVisible();
  const [a,b]=await Promise.all([reveal.boundingBox(),page.locator('.scene-edit-help').first().boundingBox()]);
  const apart=a.x+a.width<=b.x||b.x+b.width<=a.x||a.y+a.height<=b.y||b.y+b.height<=a.y;
  expect(apart,`${width}px: reveal ${JSON.stringify(a)} vs help ${JSON.stringify(b)}`).toBe(true);
 }
});

test('in a library\'s Geo, an empty folder picker says how to attach a folder instead of naming a command-line flag',async({page})=>{
 await page.route('**/api/fs/roots',route=>route.fulfill({json:{roots:[]}}));
 await page.route('**/api/workspace/context',route=>route.fulfill({json:{library_name:'Parallax',librarian_url:'http://127.0.0.1:1/',can_close:false,max_graphs:3}}));
 await page.goto('/');await ready(page);await showBuildMode(page);
 await page.getByRole('button',{name:'Add folder…'}).click();
 const panel=page.getByRole('region',{name:'Add folder'});
 await expect(panel).toContainText('Settings → Project folders');
 await expect(panel).toContainText('Parallax');
 await expect(panel).not.toContainText('--browse-root');
});
