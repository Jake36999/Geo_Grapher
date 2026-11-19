const {test,expect}=require('@playwright/test');
async function ready(page){await expect(page.getByRole('searchbox',{name:'Search entities'})).toBeEnabled();await expect(page.locator('.view-content')).toHaveAttribute('aria-busy','false');await expect(page.getByText('Loading selected graphs…',{exact:true})).toHaveCount(0);await expect(page.getByRole('alert')).toHaveCount(0);await expect(page.locator('.filter-count')).toHaveText(/[1-9]\d* groups/);}

// Counts 30-degree hue bins holding saturated, non-background pixels.
async function hueBins(page,min){
 const png=(await page.locator('canvas').first().screenshot()).toString('base64');
 return page.evaluate(async([data,floor])=>{
  const img=new Image();img.src='data:image/png;base64,'+data;await img.decode();
  const c=document.createElement('canvas');c.width=img.width;c.height=img.height;const g=c.getContext('2d');g.drawImage(img,0,0);
  const px=g.getImageData(0,0,c.width,c.height).data,bins=new Array(12).fill(0);
  for(let i=0;i<px.length;i+=4){
   const r=px[i]/255,gr=px[i+1]/255,b=px[i+2]/255,max=Math.max(r,gr,b),min=Math.min(r,gr,b),d=max-min;
   if(max<0.25||d/max<0.4)continue;
   let h=d===0?0:max===r?((gr-b)/d)%6:max===gr?(b-r)/d+2:(r-gr)/d+4;h=(h*60+360)%360;bins[Math.floor(h/30)%12]++;
  }
  return bins.filter(n=>n>=floor).length;
 },[png,min]);
}

test('edge legend explains colour, direction, pattern and size laws; edges show distinct hues',async({page})=>{
 const errors=[];page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
 await page.goto('/');await ready(page);
 await page.getByRole('button',{name:'3D space',exact:true}).click();await expect(page.locator('canvas')).toBeVisible();
 // The legend waits behind a toggle until it is wanted.
 await expect(page.locator('.legend')).toBeHidden();await page.getByRole('button',{name:'Legend',exact:true}).click();
 const legend=page.locator('.legend');
 await expect(legend).toContainText('Colour = relationship: orange call/data · violet hierarchy · cyan design rationale · sky describes · teal cites · gold bridge · red violation');
 await expect(legend).toContainText('Direction: bright at the source, fading into the target');
 await expect(legend).toContainText('Pattern: solid exact · dashed candidate · dotted expected only · pulsing observed at runtime');
 await expect(legend).toContainText('Size: content & packing share · Radial depth: coreness vs. indifference · Angle: relational affinity');
 await expect(page.locator('.view-content')).toHaveAttribute('aria-busy','false');
 await expect.poll(()=>hueBins(page,8),{timeout:15000}).toBeGreaterThanOrEqual(2);
 expect(errors).toEqual([]);
});

test('hovering a declared link between two graphs says who it joins, how, and why',async({page})=>{
 await page.goto('/?view=spatial&debug');await ready(page);
 const canvas=page.locator('canvas').first();
 // the debug build reports where each declared thread is on screen (its middle)
 await expect.poll(async()=>JSON.parse(await canvas.getAttribute('data-declared-threads')||'[]').length,{timeout:20000}).toBeGreaterThan(0);
 const threads=JSON.parse(await canvas.getAttribute('data-declared-threads'));
 const tooltip=page.locator('.scene-tooltip');
 // the thread is thin, so look for it a few pixels either side of its middle
 let shown=false;
 for(const dy of [0,-3,3,-6,6,-9,9]){
  await page.mouse.move(threads[0].x-40,threads[0].y+dy);await page.mouse.move(threads[0].x,threads[0].y+dy,{steps:3});
  await page.waitForTimeout(120);
  if(await tooltip.isVisible()){shown=true;break;}
 }
 expect(shown,'hovering the declared thread shows its words').toBe(true);
 // who it joins, how, and why: the same kind of line every other thread gives
 await expect(tooltip).toContainText('Alpha → Beta');
 await expect(tooltip).toContainText('declared reference');
 await expect(tooltip).toContainText('in force');
 // two declared links join Alpha and Beta by now (the fixture's, and the one an earlier spec accepted) and they draw on top of each other
 await expect(tooltip).toContainText(/Synthetic QA reference|Reviewed: same helper in both fixtures/);
 // leaving the thread takes the words away
 await page.mouse.move(threads[0].x,threads[0].y+300);await page.waitForTimeout(150);
 await expect(tooltip).toBeHidden();
});
