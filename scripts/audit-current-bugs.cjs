/* Diagnostic reproductions. These assert observed bugs, not desired behavior.
   Use only with a fresh isolated database from seed-browser-test.py. */
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'../browser-tools/node_modules/playwright');
const assert=require('node:assert/strict'),fs=require('node:fs');
const base=process.env.EDUPULSE_TEST_URL||'http://127.0.0.1:8078';
(async()=>{
 const b=await chromium.launch({channel:'chrome',headless:true});
 try{
  const a=await b.newPage({viewport:{width:1440,height:1000}}),t=await b.newPage();
  async function login(p,u,pw){await p.goto(base);await p.getByLabel('登录账号',{exact:true}).fill(u);await p.getByLabel('密码',{exact:true}).fill(pw);await p.getByRole('button',{name:'进入工作台'}).click();await p.locator('.sidebar').waitFor()}
  async function api(p,path,method='GET',body){return p.evaluate(async({path,method,body})=>{const auth=await(await fetch('/api/auth/me')).json();const r=await fetch('/api'+path,{method,headers:{'Content-Type':'application/json','X-CSRF-Token':auth.csrf_token},body:body===undefined?undefined:JSON.stringify(body)});if(!r.ok)throw new Error(await r.text());return r.json()},{path,method,body})}
  await login(a,'browser-admin','BrowserTestOnly2026');const dict=await api(a,'/dictionaries'),campus=dict.campus[0].id,math=dict.subject[0].id,english=dict.subject[1].id;
  const u=await api(a,'/admin/teachers','POST',{display_name:'本轮审计演示教师',campus_id:campus}),pw=await api(a,`/admin/teachers/${u.id}/issue-password`,'POST');await login(t,pw.username,pw.password);
  const students=[];for(const name of ['已排课演示学生','尚未排课演示学生'])students.push(await api(t,'/students','POST',{display_name:name,grade:'高一',campus_id:campus}));
  await api(t,'/teacher/classes','POST',{display_name:'审计演示数学班',capacity:6,subject_id:math,students:[{student_id:students[0].id,level:'B',note:'审计测试',weekly_slots:[{weekday:6,slot_number:1}]}]});
  fs.mkdirSync('docs/bug-audit-current',{recursive:true});const findings=[];
  const all=await api(a,'/admin/reports'),filtered=await api(a,`/admin/reports?campus_id=${campus}`);
  const ratio=data=>data.students.reduce((n,s)=>n+s.subject_count,0)/data.students.length;
  assert.equal(all.students.length,2);assert.equal(filtered.students.length,1);assert.equal(ratio(all),.5);assert.equal(ratio(filtered),1);
  findings.push({id:1,bug:'Campus filter excludes unassigned student profiles and inflates subject ratio',all_students:2,filtered_students:1,all_ratio:.5,filtered_ratio:1});
  // The UI keeps data from the old filter when the new report request fails.
  await a.reload();const ratioCard=a.locator('.report-secondary .stat-card').filter({hasText:'科目比'});await ratioCard.waitFor();
  let blockedResolve;const blocked=new Promise(resolve=>blockedResolve=resolve);
  await a.route('**/api/admin/reports?**',async route=>{const url=new URL(route.request().url());if(url.searchParams.get('subject_id')===String(english)){await route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'审计模拟读取失败'})});blockedResolve()}else await route.continue()});
  const previous=await ratioCard.innerText();await a.getByLabel('科目',{exact:true}).selectOption(String(english));await blocked;await a.getByRole('status').filter({hasText:'审计模拟读取失败'}).waitFor();
  assert.equal(await ratioCard.innerText(),previous);assert.equal(await a.locator('tbody>tr:not(.class-expander)').count(),1);
  await a.unroute('**/api/admin/reports?**');
  const correct=await api(a,`/admin/reports?subject_id=${english}`);assert.equal(correct.teachers.length,0);
  await a.screenshot({path:'docs/bug-audit-current/failed-filter.png',fullPage:true});
  findings.push({id:2,bug:'Failed filter request leaves old report visible under new subject selection',selected_subject:dict.subject[1].name,displayed_teacher_rows:1,correct_teacher_rows:0});
  await a.unroute('**/api/admin/reports?**');
  // Delay comparison, then create C while B->A is in flight.
  const old=await api(a,'/admin/freezes','POST',{title:'审计B'}),newer=await api(a,'/admin/freezes','POST',{title:'审计A'});
  await a.getByRole('button',{name:'数据冻结与对比',exact:true}).click();await a.getByLabel('旧记录B',{exact:true}).selectOption(String(old.id));await a.getByLabel('新记录A',{exact:true}).selectOption(String(newer.id));
  let startResolve,release;const started=new Promise(resolve=>startResolve=resolve),gate=new Promise(resolve=>release=resolve);
  await a.route('**/api/admin/freezes/compare?**',async route=>{const response=await route.fetch();startResolve();await gate;await route.fulfill({response})});
  await a.getByRole('button',{name:'开始对比',exact:true}).click();await started;
  await a.getByRole('button',{name:'冻结当前数据',exact:true}).click();const form=a.getByRole('dialog',{name:'冻结当前数据',exact:true});await form.getByLabel('记录名称').fill('审计C');await form.getByRole('button',{name:'确认冻结',exact:true}).click();await form.waitFor({state:'hidden'});await a.locator('.freeze-record').filter({hasText:'审计C'}).waitFor();
  const selectedOld=await a.getByLabel('旧记录B',{exact:true}).inputValue(),selectedNew=await a.getByLabel('新记录A',{exact:true}).inputValue();assert.equal(selectedOld,String(newer.id));assert.notEqual(selectedNew,String(newer.id));
  release();await a.locator('.freeze-comparison-title').waitFor();const resultTitle=await a.locator('.freeze-comparison-title h2').innerText();assert.equal(resultTitle,'审计B → 审计A');
  if(await a.locator('.toast .icon-button').count())await a.locator('.toast .icon-button').click();await a.screenshot({path:'docs/bug-audit-current/stale-freeze-comparison.png',fullPage:true});
  findings.push({id:3,bug:'A delayed comparison overwrites results after a new freeze changes the selected pair',selected_old_id:selectedOld,selected_new_id:selectedNew,displayed_result:resultTitle});
  fs.writeFileSync('docs/bug-audit-current/reproductions.json',JSON.stringify(findings,null,2));console.log(JSON.stringify(findings,null,2));
 }finally{await b.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
