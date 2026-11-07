const {chromium,expect}=require('@playwright/test');
const AxeBuilder=require('@axe-core/playwright').default;
const fs=require('fs');
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try{
 const context=await browser.newContext({viewport:{width:1440,height:900},deviceScaleFactor:1,reducedMotion:'reduce'});const page=await context.newPage();const errors=[],external=[],scans=[];
 page.on('pageerror',e=>errors.push(String(e)));page.on('request',r=>{if(!r.url().startsWith('http://127.0.0.1:8765'))external.push(r.url());});
 await page.goto('http://127.0.0.1:8765/?debug');await page.waitForFunction(()=>window.__geographerMetrics?.nodeCount>0,null,{timeout:120000});
 async function scan(name){const r=await new AxeBuilder({page}).analyze();scans.push({name,violations:r.violations.map(v=>({id:v.id,impact:v.impact,nodes:v.nodes.map(n=>n.target)}))});await page.screenshot({path:`output/browser/${name}.png`});}
 await scan('dark-overview');
 // The keyboard hierarchy and global search both provide entry without ray picking.
 const branch=page.locator('.node-select').filter({hasText:'aletheia_toolchain'});await branch.focus();await branch.press('Shift+Enter');
 await expect(page.getByRole('heading',{level:1})).toHaveText('aletheia_toolchain');
 await page.getByRole('searchbox',{name:'Search entities'}).fill('validate_config');
 await page.locator('.search-results button').filter({hasText:'config.py.validate_config'}).first().click();
 await expect(page.locator('.entity-heading h2')).toHaveText('validate_config');
 await page.getByRole('button',{name:'Inspect source',exact:true}).click();
 await expect(page.locator('.source-code')).toContainText('def validate_config', {timeout:30000});
 await scan('source-evidence');
 await page.getByRole('tab',{name:'Overview',exact:true}).click();await page.getByRole('button',{name:'Find dependants',exact:true}).click();await expect(page.locator('.result-box')).toBeVisible({timeout:30000});
 await page.getByText('Advanced diagnostics',{exact:true}).click();await expect(page.locator('.advanced-values')).toBeVisible({timeout:30000});
 await page.getByRole('button',{name:'Enter / frame',exact:true}).click();await expect(page.getByRole('heading',{level:1})).toHaveText('validate_config');
 await page.waitForFunction(()=>!document.querySelector('main')?.querySelector('[aria-busy=true]'),null,{timeout:120000});
 await page.getByRole('button',{name:'Matrix',exact:true}).click();await expect(page.getByRole('table')).toBeVisible();
 const cell=page.locator('.matrix-cell').first();if(await cell.count()){await cell.click();if(await page.locator('.pick-menu').count())await page.locator('.pick-menu button').first().click();await page.getByRole('button',{name:'Inspect witnesses',exact:true}).click();await expect(page.locator('.witness-card').first()).toBeVisible({timeout:30000});}
 await scan('dependency-matrix');
 await page.getByRole('tab',{name:'Agent context',exact:true}).click();await expect(page.locator('.agent-json')).toContainText('query_digest',{timeout:30000});
 await page.getByRole('button',{name:'Save view',exact:true}).click();await page.getByLabel('View name',{exact:true}).fill('QA source scope');await page.getByRole('button',{name:'Save',exact:true}).click();
 await page.getByRole('button',{name:'Home',exact:true}).click();await page.getByLabel('Restore saved view').selectOption('QA source scope');await expect(page.getByRole('heading',{level:1})).toHaveText('validate_config').catch(async e=>{console.log(await page.locator('.error-banner').allTextContents(),await page.evaluate(()=>localStorage.getItem('geographer.views.v1')));throw e;});
 await page.getByRole('button',{name:'Use light theme'}).click();await scan('light-inspector');
 await page.setViewportSize({width:1280,height:800});await scan('laptop');
 await page.setViewportSize({width:390,height:844});await page.getByRole('button',{name:'List',exact:true}).click();await scan('phone-list');
 await page.getByRole('button',{name:'Inspector',exact:true}).click();await expect(page.getByRole('button',{name:'Close inspector'})).toBeVisible();await page.getByRole('button',{name:'Close inspector'}).click();
 await page.getByRole('button',{name:'Hierarchy',exact:true}).click();await expect(page.getByRole('button',{name:'Close hierarchy'})).toBeVisible();await scan('phone-hierarchy');
 await expect(page.locator('body')).toHaveJSProperty('scrollWidth',390);
 const report={browser:browser.version(),errors,external,scans};fs.writeFileSync('output/browser/workflows.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));expect(errors).toEqual([]);expect(external).toEqual([]);expect(scans.flatMap(s=>s.violations)).toEqual([]);
 // A failed graphics context preserves the task-equivalent list route.
 const fallback=await context.newPage();await fallback.addInitScript(()=>{const original=HTMLCanvasElement.prototype.getContext;HTMLCanvasElement.prototype.getContext=function(kind,...args){if(String(kind).startsWith('webgl'))return null;return original.call(this,kind,...args);};});await fallback.goto('http://127.0.0.1:8765/');await expect(fallback.getByRole('heading',{name:'Visible architecture groups'})).toBeVisible({timeout:120000});
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
