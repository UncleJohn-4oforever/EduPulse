// Run after the launcher generates an entry page for the isolated 8077 server.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE);
const {pathToFileURL}=require('node:url');
const path=require('node:path');
const fs=require('node:fs');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1366,height:900}}),errors=[];
  page.on('pageerror',error=>errors.push(error.message));
  await page.addInitScript(()=>Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:async value=>{window.copiedUrl=value}}}));
  await page.goto(pathToFileURL(path.resolve('.logs/登录入口.html')).href);
  await page.getByRole('heading',{name:'校区统一登录网址',exact:true}).waitFor();
  const inputs=page.locator('section input');assert.ok(await inputs.count()>=2,'Teacher network URL must be available on this connected test host');
  for(const detail of await page.locator('details').all())await detail.evaluate(el=>el.open=true);
  for(let index=0;index<await inputs.count();index++){
   const input=inputs.nth(index),url=await input.inputValue();assert.equal(new URL(url).port,process.env.ENTRY_TEST_PORT||'8077');
   await page.locator('section').nth(index).getByRole('button',{name:'复制网址',exact:true}).click();
   assert.equal(await page.evaluate(()=>window.copiedUrl),url);
   assert.equal(await page.locator('section').nth(index).getByRole('link',{name:'打开网页'}).getAttribute('href'),url);
  }
  for(const detail of await page.locator('details').all())await detail.evaluate(el=>el.open=false);
  await page.evaluate(()=>{navigator.clipboard.writeText=async()=>{throw Error('clipboard unavailable')};document.execCommand=command=>{window.fallbackCopy=command==='copy';return true}});
  await page.getByRole('button',{name:'复制网址',exact:true}).first().click();assert.equal(await page.evaluate(()=>window.fallbackCopy),true);
  await page.evaluate(()=>{document.execCommand=()=>false});await page.getByRole('button',{name:'复制网址',exact:true}).first().click();await page.getByRole('status').filter({hasText:'Ctrl+C'}).waitFor();
  fs.mkdirSync('exports/login-entry-preview',{recursive:true});await page.screenshot({path:'exports/login-entry-preview/desktop.png',fullPage:true});
  await page.setViewportSize({width:390,height:844});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));await page.screenshot({path:'exports/login-entry-preview/mobile.png',fullPage:true});
  assert.deepEqual(errors,[]);console.log('PASS: supervisor and teacher addresses, custom port, copy buttons, fallback/manual copying, desktop and mobile layout.');
 }finally{await browser.close()}
})().catch(error=>{console.error(error);process.exitCode=1});
