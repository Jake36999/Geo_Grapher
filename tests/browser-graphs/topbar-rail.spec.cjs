const {test,expect}=require('@playwright/test');
const {showGraphsMode,showInspectMode}=require('../browser/panel-helpers.cjs');
async function ready(page){await expect(page.getByRole('searchbox',{name:'Search entities'})).toBeEnabled();await expect(page.locator('.view-content')).toHaveAttribute('aria-busy','false');}

test('one top bar holds back, up, home, the path and a search that takes the rest',async({page})=>{
 await page.goto('/');await ready(page);
 const header=page.locator('header.app-header');
 for(const name of ['Navigate back','Enter parent container','Home'])await expect(header.getByRole('button',{name,exact:true})).toBeVisible();
 await expect(header.getByRole('navigation',{name:'Containment path'})).toBeVisible();
 await expect(page.locator('.navigation-bar')).toHaveCount(0); // the second bar is gone
 const [bar,search]=await Promise.all([header.boundingBox(),page.getByRole('searchbox',{name:'Search entities'}).boundingBox()]);
 expect(bar.height).toBeLessThan(70);
 expect(search.width).toBeGreaterThan(200);
 // the buttons are icons with names, never bare glyphs
 for(const name of ['Navigate back','Enter parent container','Home'])await expect(header.getByRole('button',{name,exact:true}).locator('svg')).toHaveCount(1);
});

test('the heading is one slim line and the graph gets most of the column',async({page})=>{
 await page.goto('/');await ready(page);
 await expect(page.getByText('ARCHITECTURE AT A GLANCE')).toHaveCount(0);
 const heading=await page.locator('.workspace-heading').boundingBox();
 expect(heading.height).toBeLessThan(60);
 const [canvas,main]=await Promise.all([page.locator('canvas').boundingBox(),page.locator('main#main-view').boundingBox()]);
 expect(canvas.height/main.height).toBeGreaterThan(0.7);
});

test('the zoom slider follows Zoom in, Zoom out and Fit, and sets the camera',async({page})=>{
 await page.goto('/');await ready(page);
 const slider=page.getByRole('slider',{name:'Zoom',exact:true});
 await expect(slider).toBeVisible();
 await expect.poll(async()=>Number(await slider.inputValue())).toBeCloseTo(0,0);
 await page.getByRole('button',{name:'Zoom in',exact:true}).click();
 await expect.poll(async()=>Number(await slider.inputValue())).toBeGreaterThan(0.2);
 await page.getByRole('button',{name:'Zoom out',exact:true}).click();await page.getByRole('button',{name:'Zoom out',exact:true}).click();
 await expect.poll(async()=>Number(await slider.inputValue())).toBeLessThan(-0.2);
 await slider.focus();await page.keyboard.press('End'); // a keyboard user reaches the ends too
 await expect(slider).toHaveAttribute('aria-valuetext','32.00 times the fitted size');
 await page.keyboard.press('Home');
 await expect(slider).toHaveAttribute('aria-valuetext','0.13 times the fitted size');
 await page.getByRole('button',{name:/^Fit /}).click();
 await expect.poll(async()=>Math.abs(Number(await slider.inputValue()))).toBeLessThan(0.1);
});

test('the tool rail shows the selection tools only when something is selected',async({page,request})=>{
 const alpha=(await(await request.get('/api/graphs')).json()).graphs.find(g=>g.label==='Alpha');
 await page.goto(`/graphs/${alpha.graph_id}/?view=spatial&debug`);await ready(page);
 await page.getByRole('button',{name:'Wider',exact:true}).click();
 const canvas=page.locator('canvas');await expect.poll(async()=>(await canvas.boundingBox()).height).toBeGreaterThan(200);
 const rail=page.getByRole('group',{name:'Layout tools'});
 await expect(rail.getByRole('button',{name:'Box select'})).toBeVisible();
 await expect(rail.getByRole('button',{name:'Reset layout'})).toBeVisible();
 await expect(rail.getByRole('button',{name:/^Size \+/})).toHaveCount(0);
 const box=await canvas.boundingBox();
 await rail.getByRole('button',{name:'Box select'}).click();
 await page.mouse.move(box.x+64,box.y+80);await page.mouse.down();
 await page.mouse.move(box.x+box.width-12,box.y+box.height-48,{steps:5});await page.mouse.up();
 await expect(page.getByTestId('layout-selection-status')).not.toHaveText('0 selected');
 await expect(rail.getByRole('button',{name:/^Size \+/})).toBeVisible();
 await expect(rail.getByRole('button',{name:'Move selected nodes left'})).toBeVisible();
 await rail.getByRole('button',{name:'Reset layout'}).click();
 await expect(rail.getByRole('button',{name:/^Size \+/})).toHaveCount(0);
});

test('the right panel has Inspect and Graphs modes; picking something returns to Inspect',async({page})=>{
 await page.goto('/');await ready(page);
 const inspect=page.getByRole('tab',{name:'Inspect',exact:true}),graphs=page.getByRole('tab',{name:'Graphs',exact:true});
 await expect(inspect).toHaveAttribute('aria-selected','true');
 await expect(page.getByRole('combobox',{name:'Active graph'})).toHaveCount(0);
 await graphs.click();
 await expect(graphs).toHaveAttribute('aria-selected','true');
 for(const control of [page.getByRole('combobox',{name:'Active graph'}),page.getByRole('combobox',{name:'Repository snapshot'}),page.getByRole('button',{name:'Save view',exact:true}),page.getByRole('combobox',{name:'Restore saved view'})])await expect(control).toBeVisible();
 await page.keyboard.press('ArrowLeft'); // roving tabs: arrows move between the two
 await expect(inspect).toHaveAttribute('aria-selected','true');
 await showGraphsMode(page);
 await page.locator('.hierarchy-tree button:not([aria-label^="Collapse"]):not([aria-label^="Expand"])').first().click();
 await expect(inspect).toHaveAttribute('aria-selected','true'); // choosing an entity shows it
 await showInspectMode(page);
});
