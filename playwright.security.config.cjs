const {defineConfig}=require('@playwright/test');
const base=require('./playwright.real.config.cjs');
module.exports=defineConfig({...base,testDir:'tests/security-real',timeout:120000,
 outputDir:process.env.QA_REAL_OUTPUT||'output/qa-real/security-artifacts',
 reporter:[['list'],['json',{outputFile:process.env.QA_REAL_REPORT||'output/qa-real/security-results.json'}]]});
