const {test,expect}=require('@playwright/test');
const {openSettings}=require('../browser/panel-helpers.cjs');
async function ready(page){await expect(page.getByRole('searchbox',{name:'Search entities'})).toBeEnabled();await expect(page.locator('.view-content')).toHaveAttribute('aria-busy','false');}

// Floating panels close with Escape or a press outside, and open under their own trigger.
test('Scope & filters opens under its trigger and closes with Escape or a press outside',async({page})=>{
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('/');await ready(page);
 const scope=page.locator('details.popover',{has:page.locator(':scope > summary',{hasText:'Scope & filters'})});
 const summary=scope.locator(':scope > summary');
 await summary.click();await expect(scope).toHaveAttribute('open','');
 const [trigger,panel]=await Promise.all([summary.boundingBox(),scope.locator('.filter-popover').boundingBox()]);
 expect(panel.y).toBeGreaterThanOrEqual(trigger.y+trigger.height); // never over its own trigger
 expect(panel.x).toBeLessThan(trigger.x+trigger.width);
 await page.keyboard.press('Escape');
 await expect(scope).not.toHaveAttribute('open','');
 await expect(summary).toBeFocused();
 await summary.click();await expect(scope).toHaveAttribute('open','');
 await page.locator('.workspace-heading h1').click();
 await expect(scope).not.toHaveAttribute('open','');
 await summary.click();await scope.getByRole('checkbox',{name:'Static'}).focus(); // a press inside keeps it open
 await scope.locator('.filter-popover').click({position:{x:4,y:4}});
 await expect(scope).toHaveAttribute('open','');
 expect(errors).toEqual([]);
});

test('Configure rules (opened from Scope & filters) and Coverage close with Escape',async({page})=>{
 await page.goto('/');await ready(page);
 const scope=page.locator('details.popover',{has:page.locator(':scope > summary',{hasText:'Scope & filters'})});
 await scope.locator(':scope > summary').click();
 await scope.getByRole('button',{name:'Configure rules'}).click();
 await expect(scope).not.toHaveAttribute('open',''); // the panel steps aside for the editor it opens
 await expect(page.getByRole('region',{name:'Rules configuration'})).toBeVisible();
 await page.keyboard.press('Escape');
 await expect(page.getByRole('region',{name:'Rules configuration'})).toBeHidden();
 await page.locator('button[aria-expanded]',{hasText:'Coverage'}).click();
 await expect(page.locator('.coverage-popover')).toBeVisible();
 await page.keyboard.press('Escape');
 await expect(page.locator('.coverage-popover')).toBeHidden();
});

test('Settings closes with Escape or a press outside, and holds the theme and panel widths',async({page})=>{
 await page.goto('/');await ready(page);
 const menu=page.locator('.settings-menu');
 await openSettings(page);await expect(menu).toHaveAttribute('open','');
 await expect(page.getByRole('slider',{name:'Hierarchy panel width'})).toBeVisible();
 await expect(page.getByRole('slider',{name:'Inspector panel width'})).toBeVisible();
 await page.getByRole('button',{name:'Use light theme',exact:true}).click();
 await expect(page.locator('html')).toHaveAttribute('data-theme','light');
 await page.keyboard.press('Escape');await expect(menu).not.toHaveAttribute('open','');
 await openSettings(page);await page.locator('.workspace-heading h1').click();
 await expect(menu).not.toHaveAttribute('open','');
});
