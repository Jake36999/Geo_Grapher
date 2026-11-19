const {test,expect}=require('@playwright/test');
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

test('the Graphs picker, Configure rules and Coverage close with Escape',async({page})=>{
 await page.goto('/');await ready(page);
 const picker=page.locator('details.workspace-graph-picker');
 await picker.locator(':scope > summary').click();await expect(picker).toHaveAttribute('open','');
 await page.keyboard.press('Escape');await expect(picker).not.toHaveAttribute('open','');
 await picker.locator(':scope > summary').click();await expect(picker).toHaveAttribute('open','');
 await page.locator('canvas').first().click({position:{x:20,y:200}});
 await expect(picker).not.toHaveAttribute('open','');
 await page.getByRole('button',{name:'Configure rules'}).click();
 await expect(page.getByRole('region',{name:'Rules configuration'})).toBeVisible();
 await page.keyboard.press('Escape');
 await expect(page.getByRole('region',{name:'Rules configuration'})).toBeHidden();
 await page.locator('button[aria-expanded]',{hasText:'Coverage'}).click();
 await expect(page.locator('.coverage-popover')).toBeVisible();
 await page.keyboard.press('Escape');
 await expect(page.locator('.coverage-popover')).toBeHidden();
});
