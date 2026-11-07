const { defineConfig } = require('@playwright/test');
const path = require('node:path');
module.exports=defineConfig({
  testDir:'tests/browser-graphs',testMatch:['integrated-workspace.spec.cjs','layout-editing.spec.cjs'],workers:1,
  timeout:60000,expect:{timeout:15000},outputDir:'output/integrated-workspace/browser-artifacts',
  reporter:[['list'],['json',{outputFile:'output/integrated-workspace/browser-results.json'}]],
  use:{baseURL:'http://127.0.0.1:8775',browserName:'chromium',channel:'msedge',viewport:{width:1440,height:1000},reducedMotion:'reduce',trace:'retain-on-failure',screenshot:'only-on-failure'},
  webServer:{command:'"'+path.join(__dirname,'output/wheel-env/Scripts/python.exe')+'" scripts/qa_graph_workspace_server.py',
    url:'http://127.0.0.1:8775/api/graphs',reuseExistingServer:false,timeout:120000,stdout:'ignore',stderr:'pipe'},
});
