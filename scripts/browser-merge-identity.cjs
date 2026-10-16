/* Fresh isolated seed-browser-test.py database only. */
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'../browser-tools/node_modules/playwright');
const assert=require('node:assert/strict');
(async()=>{
 const b=await chromium.launch({channel:'chrome',headless:true});
 try{
  const p=await b.newPage({viewport:{width:1440,height:1000}});
  await p.goto(process.env.EDUPULSE_TEST_URL||'http://127.0.0.1:8079');await p.getByLabel('登录账号',{exact:true}).fill('browser-admin');await p.getByLabel('密码',{exact:true}).fill('BrowserTestOnly2026');await p.getByRole('button',{name:'进入工作台'}).click();await p.locator('.sidebar').waitFor();
  async function api(path,method='GET',body){return p.evaluate(async({path,method,body})=>{const auth=await(await fetch('/api/auth/me')).json();const r=await fetch('/api'+path,{method,headers:{'Content-Type':'application/json','X-CSRF-Token':auth.csrf_token},body:body===undefined?undefined:JSON.stringify(body)});if(!r.ok)throw new Error(await r.text());return r.json()},{path,method,body})}
  const dict=await api('/dictionaries'),campus=dict.campus[0].id,profiles=[];
  for(const name of ['演示误录档案','演示保留档案'])profiles.push(await api('/students','POST',{display_name:name,grade:'高一',campus_id:campus}));
  await p.getByRole('button',{name:'设置',exact:true}).click();const panel=p.locator('section.panel').filter({has:p.getByRole('heading',{name:'人工合并重复学生',exact:true})}),source=panel.getByLabel('待合并的学生编号',{exact:true}),target=panel.getByLabel('保留的学生编号',{exact:true}),submit=panel.getByRole('button',{name:'确认合并档案',exact:true});
  assert.equal(await submit.isDisabled(),true);await source.fill(String(profiles[0].id));await panel.getByText(`演示误录档案 · #${profiles[0].id}`,{exact:true}).waitFor();await target.fill('999999');await panel.getByRole('alert').waitFor();assert.equal(await submit.isDisabled(),true);
  await target.fill(String(profiles[0].id));await panel.getByText('请选择两个不同的学生编号。',{exact:true}).waitFor();assert.equal(await submit.isDisabled(),true);
  // A slow result for the old number must never replace the newly typed identity.
  let startedResolve,release;const started=new Promise(r=>startedResolve=r),gate=new Promise(r=>release=r);
  await p.route(`**/api/admin/students/${profiles[1].id}/deletion-preview`,async route=>{const response=await route.fetch();startedResolve();await gate;await route.fulfill({response})});
  await source.fill(String(profiles[1].id));await started;await source.fill(String(profiles[0].id));await panel.locator('.manual-merge-field').first().getByText(`演示误录档案 · #${profiles[0].id}`,{exact:true}).waitFor();const delayed=p.waitForResponse(r=>r.url().includes(`/api/admin/students/${profiles[1].id}/deletion-preview`));release();await delayed;await p.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));assert.equal(await panel.locator('.manual-merge-field').first().locator('strong').innerText(),`演示误录档案 · #${profiles[0].id}`);await p.unroute(`**/api/admin/students/${profiles[1].id}/deletion-preview`);
  await target.fill(String(profiles[1].id));await panel.getByText(`演示保留档案 · #${profiles[1].id}`,{exact:true}).waitFor();assert.equal(await submit.isDisabled(),false);
  for(const width of [1440,1024,768,390,360]){await p.setViewportSize({width,height:900});assert.ok(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`overflow ${width}`)}
  let prompt='';p.once('dialog',async d=>{prompt=d.message();await d.accept()});await submit.click();await p.waitForFunction(()=>document.querySelector('input[type="number"]')?.value==='');assert.ok(prompt.includes(`演示误录档案 #${profiles[0].id}`)&&prompt.includes(`演示保留档案 #${profiles[1].id}`));assert.equal((await api('/admin/reports?search_type=student')).students.length,1);assert.equal(await submit.isDisabled(),true);
  console.log('PASS: exact-ID names, grade/campus, absent ID and duplicate ID blocking, stale-response protection, names in final confirmation, merge/reset and five screen widths.');
 }finally{await b.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
