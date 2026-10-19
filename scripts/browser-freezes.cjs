/* Requires a fresh isolated database from seed-browser-test.py. */
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'../browser-tools/node_modules/playwright');
const assert=require('node:assert/strict'),fs=require('node:fs');
const base=process.env.EDUPULSE_TEST_URL||'http://127.0.0.1:8076';
(async()=>{
 const b=await chromium.launch({channel:'chrome',headless:true});
 try{
  const a=await b.newPage({viewport:{width:1440,height:1000},reducedMotion:'reduce'}),t=await b.newPage(),errors=[];
  for(const p of [a,t])p.on('pageerror',e=>errors.push(e.message));
  async function login(p,u,pw){await p.goto(base);await p.getByLabel('登录账号',{exact:true}).fill(u);await p.getByLabel('密码',{exact:true}).fill(pw);await p.getByRole('button',{name:'进入工作台'}).click();await p.locator('.sidebar').waitFor()}
  async function api(p,path,method='GET',body){return p.evaluate(async({path,method,body})=>{const auth=await(await fetch('/api/auth/me')).json();const r=await fetch('/api'+path,{method,headers:{'Content-Type':'application/json','X-CSRF-Token':auth.csrf_token},body:body===undefined?undefined:JSON.stringify(body)});if(!r.ok)throw new Error(await r.text());return r.json()},{path,method,body})}
  await login(a,'browser-admin','BrowserTestOnly2026');const dict=await api(a,'/dictionaries'),campus=dict.campus[0].id;
  const u=await api(a,'/admin/teachers','POST',{display_name:'虚构冻结测试教师',campus_id:campus}),pw=await api(a,`/admin/teachers/${u.id}/issue-password`,'POST');await login(t,pw.username,pw.password);
  const students=[];for(const name of ['演示学生甲','演示学生乙'])students.push(await api(t,'/students','POST',{display_name:name,grade:'高一',campus_id:campus}));
  async function room(subject,cap,ids,name='演示周六一档'){return api(t,'/teacher/classes','POST',{display_name:name,capacity:cap,subject_id:subject,students:ids.map(id=>({student_id:id,level:'B',note:'冻结演示评价',weekly_slots:[{weekday:name==='周三五档'?3:6,slot_number:name==='周三五档'?5:1}]}))})}
  await room(dict.subject[0].id,6,students.map(s=>s.id));await room(dict.subject[1].id,3,[students[0].id]);
  await a.getByRole('button',{name:'数据冻结与对比',exact:true}).click();
  assert.equal(await a.getByRole('button',{name:'开始对比',exact:true}).isDisabled(),true);
  async function capture(title){await a.getByRole('button',{name:'冻结当前数据',exact:true}).click();const dialog=a.getByRole('dialog',{name:'冻结当前数据',exact:true});await dialog.getByLabel('记录名称').fill(title);await dialog.getByLabel('备注',{exact:true}).fill('本记录仅为隔离测试演示');const response=a.waitForResponse(r=>r.url().endsWith('/api/admin/freezes')&&r.request().method()==='POST');await dialog.getByRole('button',{name:'确认冻结',exact:true}).click();assert.equal((await response).status(),200);await dialog.waitFor({state:'hidden'});await a.locator('.freeze-record').filter({hasText:title}).waitFor()}
  await capture('演示旧记录B');const old=(await api(a,'/admin/freezes'))[0];const original=await api(a,`/admin/freezes/${old.id}`);
  const s3=await api(t,'/students','POST',{display_name:'演示新增学生丙',grade:'高一',campus_id:campus});await room(dict.subject[0].id,6,[s3.id],'周三五档');
  await capture('演示新记录A');await a.getByRole('button',{name:'开始对比',exact:true}).click();
  const six=a.getByRole('region',{name:'一对六满班率对比',exact:true}),subjects=a.getByRole('region',{name:'科目比对比',exact:true});
  await six.waitFor();assert.match(await six.innerText(),/33.33%[\s\S]*25.00%/);assert.match(await six.innerText(),/-8.33 个百分点/);assert.match(await six.locator('.freeze-factors.down').innerText(),/周三五档/);
  assert.match(await subjects.innerText(),/1.50 科\/人[\s\S]*1.33 科\/人/);assert.match(await subjects.locator('.freeze-factors.down').innerText(),/演示新增学生丙/);
  await six.locator('.freeze-factors.down summary').click();assert.match(await six.innerText(),/容量：0 → 6/);
  assert.deepEqual(await api(a,`/admin/freezes/${old.id}`),original);
  if(await a.locator('.toast .icon-button').count())await a.locator('.toast .icon-button').click();
  fs.mkdirSync('docs/screenshots/freezes',{recursive:true});await a.screenshot({path:'docs/screenshots/freezes/compare-desktop.png',fullPage:true,animations:'disabled'});
  for(const width of [1440,1280,1024,768,390,360]){await a.setViewportSize({width,height:900});assert.ok(await a.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`overflow ${width}`)}
  await a.screenshot({path:'docs/screenshots/freezes/compare-mobile.png',fullPage:true,animations:'disabled'});
  await a.setViewportSize({width:1440,height:1000});await a.locator('.freeze-record').filter({hasText:'演示旧记录B'}).getByRole('button',{name:'查看冻结数据',exact:true}).click();const dialog=a.getByRole('dialog',{name:'冻结数据详情'});assert.match(await dialog.innerText(),/1.50 科\/人/);await dialog.getByRole('button',{name:'关闭',exact:true}).click();
  const newest=(await api(a,'/admin/freezes'))[0];await a.getByLabel('旧记录B',{exact:true}).selectOption(String(newest.id));assert.equal(await a.getByRole('button',{name:'开始对比',exact:true}).isDisabled(),true);
  await a.reload();await a.getByRole('button',{name:'数据冻结与对比',exact:true}).click();await a.locator('.freeze-record').first().waitFor();assert.equal(await a.locator('.freeze-record').count(),2);
  assert.equal(await t.getByRole('button',{name:'数据冻结与对比',exact:true}).count(),0);assert.deepEqual(errors,[]);
  console.log('PASS: manual capture, named immutable records, teacher writes after freeze, compare factors, old/new guards, stored data inspection, reload persistence and six responsive widths.');
 }finally{await b.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
