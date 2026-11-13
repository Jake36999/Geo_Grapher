const {defineConfig}=require('@playwright/test');
const origin='http://127.0.0.1:'+(process.env.QA_REAL_PORT||'8786');
module.exports=defineConfig({testDir:'tests/browser-real',workers:1,timeout:120000,
 expect:{timeout:20000},outputDir:process.env.QA_REAL_OUTPUT||'output/qa-real/test-results',
 reporter:[['list'],['json',{outputFile:process.env.QA_REAL_REPORT||'output/qa-real/results-first.json'}]],
 use:{baseURL:origin,browserName:'chromium',channel:'msedge',viewport:{width:1440,height:900},
 reducedMotion:'reduce',trace:'retain-on-failure',screenshot:'only-on-failure'},
 webServer:{command:'uvx --refresh-package geo-grapher --from output/phase67-gates/wave4/frontdoor-final-dist/geo_grapher-0.1.1-py3-none-any.whl python scripts/qa_real_store_server.py',env:{PYTHONPATH:''},
 url:origin+'/api/graphs',reuseExistingServer:false,timeout:120000}});
