/* Run only against an isolated database seeded by seed-browser-test.py. */
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'../browser-tools/node_modules/playwright');
const assert=require('node:assert/strict');
const base=process.env.EDUPULSE_TEST_URL||'http://127.0.0.1:8052';
(async()=>{
 const browser=await chromium.launch({args:['--no-sandbox']});
 try {
  const a=await browser.newPage(),t=await browser.newPage();
  for(const p of [a,t]){p.setDefaultTimeout(15000);p.on('dialog',d=>d.accept())}
  async function login(p,u,pw){await p.goto(base);await p.getByLabel('登录账号',{exact:true}).fill(u);await p.getByLabel('密码',{exact:true}).fill(pw);await p.getByRole('button',{name:'进入工作台'}).click();await p.locator('.sidebar').waitFor()}
  async function api(p,path,method='GET',body){return p.evaluate(async({path,method,body})=>{const auth=await(await fetch('/api/auth/me')).json();const r=await fetch('/api'+path,{method,headers:{'Content-Type':'application/json','X-CSRF-Token':auth.csrf_token},body:body===undefined?undefined:JSON.stringify(body)});if(!r.ok)throw new Error('HTTP '+r.status);return r.json()},{path,method,body})}
  await login(a,'browser-admin','BrowserTestOnly2026');
  const d=await api(a,'/dictionaries');
  const u=await api(a,'/admin/teachers','POST',{display_name:'中断检查虚构教师',campus_id:d.campus[0].id});
  const pw=await api(a,`/admin/teachers/${u.id}/issue-password`,'POST');await login(t,pw.username,pw.password);
  await api(t,'/students','POST',{display_name:'中断检查虚构学生',grade:d.grade[0].name,campus_id:d.campus[0].id});
  await t.getByRole('button',{name:'新增班级',exact:true}).click();await t.getByLabel('班型 / 容量').selectOption('1');
  await t.getByRole('button',{name:'添加学生 · 搜索已有 / 新建'}).click();await t.getByLabel('先搜索姓名或内部编号').fill('中断检查虚构学生');await t.locator('.search-results button').waitFor();
  let release,entered;const gate=new Promise(r=>release=r),pending=new Promise(r=>entered=r);
  await t.route('**/api/students',async route=>{if(route.request().method()==='POST'){entered();await gate}await route.continue()});
  await t.getByRole('button',{name:'新建「中断检查虚构学生」并加入'}).click();await pending;
  const choice=t.locator('.search-results button');
  if(!await choice.isDisabled()){
   // Reproduce choosing an existing student before the new student arrives.
   await choice.click();release();await t.waitForResponse(r=>r.url().endsWith('/api/students')&&r.request().method()==='POST');
   await t.waitForFunction(()=>document.querySelectorAll('.student-card').length>=2);
   assert.equal(await t.locator('.student-card').count(),1,'pending creation must not add a second student to a one-seat class');
  }else{
   assert.ok(await t.getByLabel('先搜索姓名或内部编号').isDisabled());
   await t.getByRole('button',{name:'关闭',exact:true}).click();assert.ok(await t.locator('.modal').isVisible());
   const response=t.waitForResponse(r=>r.url().endsWith('/api/students')&&r.request().method()==='POST');release();await response;
   await t.locator('.modal').waitFor({state:'hidden'});assert.equal(await t.locator('.student-card').count(),1);
   await t.getByLabel('班级显示名称',{exact:true}).fill('虚构中断回归班');await t.getByRole('button',{name:'保存班级更改'}).click();await t.locator('.badge').filter({hasText:'已保存'}).waitFor();
   assert.equal((await api(t,'/teacher/classes'))[0].students.length,1);
  }
  console.log('PASS: pending student creation cannot select another student, close the picker, or overflow class capacity; saved enrollment verified.');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
