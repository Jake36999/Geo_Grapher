const {test,expect}=require('@playwright/test');
const AxeBuilder=require('@axe-core/playwright').default;
const {showBuildMode,showInspectMode}=require('../browser/panel-helpers.cjs');
async function ready(page){await expect(page.getByRole('searchbox',{name:'Search entities'})).toBeEnabled();await expect(page.locator('.view-content')).toHaveAttribute('aria-busy','false');}

test('the right panel has a Build tab that holds Add a folder, Combine and Link, and the arrow keys cycle all three tabs',async({page})=>{
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('/');await ready(page);
 const tabs=page.getByRole('tablist',{name:'Right panel'}).getByRole('tab');
 await expect(tabs).toHaveText(['Inspect','Graphs','Build']);
 const build=page.getByRole('tab',{name:'Build',exact:true});
 await build.click();await expect(build).toHaveAttribute('aria-selected','true');
 const panel=page.getByRole('tabpanel',{name:'Build'});
 for(const heading of ['Add a folder','Combine graphs','Link graphs'])await expect(panel.getByRole('heading',{name:heading})).toBeVisible();
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
