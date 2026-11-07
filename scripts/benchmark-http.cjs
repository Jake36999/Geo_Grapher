const fs=require('fs');
const percentile=(xs,p)=>[...xs].sort((a,b)=>a-b)[Math.ceil(xs.length*p)-1];
(async()=>{
 const root='http://127.0.0.1:8766';const bootstrap=await (await fetch(root+'/api/v1/bootstrap')).json(),s=bootstrap.snapshots[0];
 const base=()=>({schema_version:'1.0',request_id:crypto.randomUUID(),snapshot_id:s.snapshot_id,budget:{limit_tokens:32768,tokenizer:'o200k_base',allow_byte_fallback:false}});
 const filter={repo_ids:[],families:['static'],subtypes:[],resolution_statuses:['exact'],include_tests:false,include_generated:false,include_vendor:false,include_external:true,runtime_window:null};
 const request={...base(),focus_id:'bench:repo',revealed_ids:['bench:workspace','bench:repo'],pins:[],context_radius:1,filter,layout_version:'sphere-pack-v1',seed:'geographer-workspace-v1',beta:.8,edge_lens:{enabled:false,center:[0,0,0],radius:5,strength:.8},node_budget:500,curve_budget:2000,viewport:{width_px:1440,height_px:900,device_pixel_ratio:1},camera:{eye:[20,14,26],target:[0,0,0],up:[0,1,0],fov_y_degrees:45,near:.01,far:1000000}};
 async function call(path,body){const start=performance.now();const r=await fetch(root+path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const data=await r.json();if(data.error)throw new Error(JSON.stringify(data));return {ms:performance.now()-start,data};}
 const frame=[];let first;
 for(let i=0;i<21;i++){const r=await call('/api/v1/viewport/frame',{...request,request_id:crypto.randomUUID()});first??=r.data;frame.push(r.ms);}
 const relation=first.data.relationships[0];if(!relation)throw new Error('Expected reference relationship');
 const witness=[];for(let i=0;i<21;i++){const r=await call('/api/v1/inspect_relationship_witnesses',{...base(),view_id:relation.view_id,projection_id:relation.id,relationship_id:null,evidence_page_size:3,evidence_cursor:null,page_size:20,cursor:null});witness.push(r.ms);}
 const report={dataset:{entities:50000,relationships:150000,seed:'geographer-benchmark-v1'},state:'server graph/encoders preloaded; first operation plan cold, subsequent 20 calls warm',viewport_first_page:{first_ms:frame[0],warm_p95_ms:percentile(frame.slice(1),.95),samples:frame},witness_first_page:{first_ms:witness[0],warm_p95_ms:percentile(witness.slice(1),.95),samples:witness},returned:{nodes:first.data.nodes.length,curves:first.data.curves.length,region_tokens:first.budget.used_tokens},host:'Ryzen 7 5800X / 31.9 GiB; not C14 target'};
 fs.writeFileSync('output/browser/http-performance.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));
})().catch(e=>{console.error(e);process.exitCode=1;});
