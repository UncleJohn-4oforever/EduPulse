/* Use an isolated database with the browser test administrator. */
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'../browser-tools/node_modules/playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const base=process.env.EDUPULSE_TEST_URL||'http://127.0.0.1:8059';
(async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true});
 try {
  const a=await browser.newPage({viewport:{width:1440,height:1000},reducedMotion:'reduce'}),t=await browser.newPage({viewport:{width:1440,height:1000},reducedMotion:'reduce'});
  for(const p of [a,t]){p.on('dialog',d=>d.accept());p.setDefaultTimeout(15000)}
  async function login(p,u,pw){await p.goto(base);await p.getByLabel('登录账号',{exact:true}).fill(u);await p.getByLabel('密码',{exact:true}).fill(pw);await p.getByRole('button',{name:'进入工作台'}).click();await p.locator('.sidebar').waitFor();const close=p.locator('.toast button');if(await close.count())await close.click()}
  async function api(path,method='GET',body){return a.evaluate(async({path,method,body})=>{const auth=await(await fetch('/api/auth/me')).json();const r=await fetch('/api'+path,{method,headers:{'Content-Type':'application/json','X-CSRF-Token':auth.csrf_token},body:body===undefined?undefined:JSON.stringify(body)});if(!r.ok)throw new Error(await r.text());return r.json()},{path,method,body})}
  await login(a,'browser-admin','BrowserTestOnly2026');const teachers=await api('/admin/teachers');const user=teachers[0];const pw=await api(`/admin/teachers/${user.id}/issue-password`,'POST');await login(t,pw.username,pw.password);await t.locator('.class-editor').first().waitFor();await t.locator('.class-editor').first().getByRole('button',{name:'展开编辑',exact:true}).click();
  fs.mkdirSync('docs/screenshots/readability',{recursive:true});
  await a.getByRole('button',{name:'教师满班率',exact:true}).click();await a.locator('tbody td').first().waitFor();
  for(const [page,name] of [[a,'admin'],[t,'teacher']]){
   await page.screenshot({path:`docs/screenshots/readability/${name}-desktop.png`,fullPage:true});
   for(const width of [1440,1280,1024,768,390,360]){
    await page.setViewportSize({width,height:900});await page.evaluate(()=>document.body.offsetWidth);
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`${name}: page overflow at ${width}`);
    const tiny=await page.evaluate(()=>[...document.querySelectorAll('main *,aside *')].filter(e=>e.getClientRects().length&&[...e.childNodes].some(n=>n.nodeType===3&&n.textContent.trim())&&parseFloat(getComputedStyle(e).fontSize)<14).map(e=>({tag:e.tagName,font:getComputedStyle(e).fontSize,text:e.textContent.slice(0,30)})));
    assert.deepEqual(tiny,[],`${name}: text below 14px at ${width}`);
   }
   await page.setViewportSize({width:390,height:844});if(name==='admin')assert.ok(await page.locator('.search-field').evaluate(e=>e.getBoundingClientRect().width>=innerWidth-40),'Mobile search must occupy its own row');await page.screenshot({path:`docs/screenshots/readability/${name}-mobile.png`,fullPage:true});
  }
  assert.equal(await t.locator('.class-editor input').first().evaluate(e=>getComputedStyle(e).fontSize),'16px');
  assert.equal(await a.locator('table').first().evaluate(e=>getComputedStyle(e).fontSize),'16px');
  console.log('PASS: teacher/admin desktop and mobile, six widths 360–1440px, no page overflow, visible text at least 14px, table/input text 16px. Screenshots: docs/screenshots/readability.');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
