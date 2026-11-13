const {test,expect}=require('@playwright/test');
const fs=require('fs');const path=require('path');
const root=path.resolve(process.env.QA_REAL_ROOT);
let baseline=[];
test.beforeAll(async({request})=>{baseline=(await(await request.get('/api/graphs')).json()).graphs;});
test.afterAll(async({request})=>{
 const graphs=(await(await request.get('/api/graphs')).json()).graphs;
 for(const g of graphs)if(!baseline.some(b=>b.graph_id===g.graph_id))expect((await request.delete('/api/graphs/'+g.graph_id,{data:{confirm_label:g.label}})).ok()).toBe(true);
 const cleanup=await(await request.post('/__qa/cleanup',{data:{}})).json();expect(cleanup.extra_graphs).toEqual([]);
 expect(cleanup.baseline_preserved).toBe(true);
});
const graph=label=>baseline.find(g=>g.label===label).graph_id;

test('foreign and opaque origins cannot reach mutation routes; hostile Host is refused',async({request})=>{
 const a=graph('librarian-v2'),b=graph('librarian-survey-worktree'),tool=graph('ToolSet');
 const routes=[['post','/api/workspace/ingest-preview',{root:path.join(root,'browse','project')}],
 ['post','/api/workspace/ingest-execute',{plan_id:'unknown',approved_keys:['residual']}],
 ['post',`/api/graphs/${tool}/prune`,{exclude_rel_paths:['skip'],label:'security-blocked'}],
 ['post','/api/graphs/bridge-proposals',{graph_a:a,graph_b:b,kind:'reference',limit:1}],
 ['post','/api/graphs/bridge-proposals/unknown',{decision:'reject',rationale:'security test'}],
 ['delete',`/api/graphs/${tool}`,{confirm_label:'not-the-label'}]];
 for(const origin of ['https://evil.invalid','null','http://127.0.0.1.evil.invalid'])for(const [method,url,data] of routes){
  const response=await request[method](url,{headers:{Origin:origin},data});expect(response.status(),`${origin} ${url}`).toBe(403);
 }
 const host=await request.get('/api/graphs',{headers:{Host:'evil.invalid'}});expect([400,403,421]).toContain(host.status());
 expect((await(await request.get('/api/graphs')).json()).graphs.map(g=>[g.graph_id,g.snapshot_id])).toEqual(baseline.map(g=>[g.graph_id,g.snapshot_id]));
});

test('picker and ingest preview enforce the browse root including same-root junctions',async({request})=>{
 expect((await request.get('/api/fs/list',{params:{path:path.join(root,'browse')}})).ok()).toBe(true);
 for(const folder of ['..','\\\\localhost\\C$',path.join(root,'outside-browse'),path.join(root,'browse','junction'),path.join(root,'browse','inside-link'),'http://example.invalid']){
  expect((await request.get('/api/fs/list',{params:{path:folder}})).status(),folder).toBe(403);
  expect((await request.post('/api/workspace/ingest-preview',{data:{root:folder}})).status(),folder).toBe(403);
 }
});

test('preview roots are revalidated before an ingest job starts',async({request})=>{
 const project=path.join(root,'browse','security-project'),saved=project+'-saved';
 expect(path.resolve(project).startsWith(root+path.sep)&&path.resolve(saved).startsWith(root+path.sep)).toBe(true);
 const response=await request.post('/api/workspace/ingest-preview',{data:{root:project}});expect(response.ok()).toBe(true);
 const plan=await response.json();expect(plan.partitions.length).toBeGreaterThan(0);
 fs.renameSync(project,saved);
 try{
  fs.symlinkSync(path.join(root,'outside-browse'),project,'junction');
  const execution=await request.post('/api/workspace/ingest-execute',{data:{plan_id:plan.plan_id,approved_keys:[plan.partitions[0].key]}});
  if(execution.status()===200){const job=await execution.json();await expect.poll(async()=> (await(await request.get('/api/workspace/jobs/'+job.job_id)).json()).state,{timeout:30000}).toBe('failed');}
  expect(execution.status()).toBe(403);
 }finally{
  if(fs.lstatSync(project).isSymbolicLink())fs.unlinkSync(project);
  expect(path.resolve(saved).startsWith(root+path.sep)).toBe(true);fs.renameSync(saved,project);
 }
});

test('invalid plans, pruning paths, payloads and job IDs fail without source mutation',async({request})=>{
 expect((await request.post('/api/workspace/ingest-execute',{data:{plan_id:'missing',approved_keys:[]}})).status()).toBe(400);
 expect((await request.get('/api/workspace/jobs/unknown')).status()).toBe(404);
 expect((await request.post(`/api/graphs/${graph('ToolSet')}/prune`,{data:{exclude_rel_paths:['../outside'],label:'not-created'}})).status()).toBe(400);
 expect((await request.post('/api/workspace/ingest-preview',{data:'x'.repeat(4194305),headers:{'Content-Type':'application/json'}})).status()).toBe(413);
 for(const url of ['/api/workspace/ingest-execute','/api/graphs/bridge-proposals']){
  const malformed=await request.post(url,{data:'{',headers:{'Content-Type':'application/json'}});expect([400,403]).toContain(malformed.status());
 }
 expect((await(await request.get('/api/graphs')).json()).graphs.map(g=>[g.graph_id,g.snapshot_id])).toEqual(baseline.map(g=>[g.graph_id,g.snapshot_id]));
});

test('real proposal decisions require rationale and cannot be replayed',async({request})=>{
 const a=graph('librarian-v2'),b=graph('librarian-survey-worktree');
 expect((await request.post('/api/graphs/bridge-proposals',{data:{graph_a:a,graph_b:b,kind:'invalid',limit:1}})).status()).toBe(400);
 expect((await request.post('/api/graphs/bridge-proposals',{data:{graph_a:a,graph_b:b,kind:'reference',limit:501}})).status()).toBe(400);
 const response=await request.post('/api/graphs/bridge-proposals',{data:{graph_a:a,graph_b:b,kind:'reference',limit:1}});expect(response.ok()).toBe(true);
 const proposals=(await response.json()).proposals;expect(proposals.length).toBeGreaterThan(0);
 const url='/api/graphs/bridge-proposals/'+proposals[0].proposal_id;
 expect((await request.post(url,{data:{decision:'reject',rationale:''}})).status()).toBe(400);
 expect((await request.post(url,{data:{decision:'reject',rationale:'Security QA: no inferred equivalence is accepted.'}})).ok()).toBe(true);
 expect((await request.post(url,{data:{decision:'reject',rationale:'Repeated decision must fail.'}})).status()).toBe(409);
});

test('an opaque-origin browser page cannot submit a JSON mutation',async({page,baseURL})=>{
 await page.goto('data:text/html,<title>Untrusted test origin</title>');
 const result=await page.evaluate(async({url,root})=>{try{return(await fetch(url+'/api/workspace/ingest-preview',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({root})})).status;}catch{return 'blocked';}}, {url:baseURL,root:path.join(root,'browse','project')});
 expect(result).toBe('blocked');
});
