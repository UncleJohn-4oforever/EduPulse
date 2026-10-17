/* Use a fresh isolated database seeded with seed-browser-test.py. */
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'../browser-tools/node_modules/playwright');
const assert=require('node:assert/strict');
const base=process.env.EDUPULSE_TEST_URL||'http://127.0.0.1:8054';
(async()=>{
 const browser=await chromium.launch({args:['--no-sandbox']});
 try{
  const a=await browser.newPage({viewport:{width:1440,height:1000}}),t=await browser.newPage({viewport:{width:1360,height:1100}}),errors=[];
  for(const p of [a,t]){p.setDefaultTimeout(15000);p.on('dialog',d=>d.accept());p.on('pageerror',e=>errors.push(e.message))}
  async function login(p,u,pw){await p.goto(base);await p.getByLabel('登录账号',{exact:true}).fill(u);await p.getByLabel('密码',{exact:true}).fill(pw);await p.getByRole('button',{name:'进入工作台'}).click();await p.locator('.sidebar').waitFor()}
  async function api(p,path,method='GET',body){return p.evaluate(async({path,method,body})=>{const auth=await(await fetch('/api/auth/me')).json();const r=await fetch('/api'+path,{method,headers:{'Content-Type':'application/json','X-CSRF-Token':auth.csrf_token},body:body===undefined?undefined:JSON.stringify(body)});if(!r.ok)throw new Error(await r.text());return r.json()},{path,method,body})}
  await login(a,'browser-admin','BrowserTestOnly2026');const d=await api(a,'/dictionaries');
  const u=await api(a,'/admin/teachers','POST',{display_name:'虚构撞档验证教师',campus_id:d.campus[0].id});const pw=await api(a,`/admin/teachers/${u.id}/issue-password`,'POST');await login(t,pw.username,pw.password);
  const rooms=[];
  for(const [name,number,start,end] of [['撞档验证甲班',2,'09:00','10:00'],['撞档验证乙班',5,'09:30','10:30']]){
   const s=await api(t,'/students','POST',{display_name:'虚构'+name+'学生',grade:d.grade[0].name,campus_id:d.campus[0].id});
   rooms.push(await api(t,'/teacher/classes','POST',{display_name:name,subject_id:d.subject[0].id,grade:d.grade[0].name,capacity:3,students:[{student_id:s.id,level:'B',note:'',weekly_slots:[{weekday:3,slot_number:number,start_time:start,end_time:end}]}]}));
  }
  await t.reload();await t.locator('.schedule-warnings summary').click();await t.getByText('时间重叠',{exact:true}).waitFor();
  await a.getByRole('button',{name:'教师周课量',exact:true}).click();const row=a.locator('tr').filter({hasText:'虚构撞档验证教师'}).first();await row.locator('.schedule-warnings summary').click();await row.getByText('时间重叠',{exact:true}).waitFor();
  assert.ok((await row.locator('.schedule-warnings').innerText()).includes('撞档验证甲班'));assert.ok((await row.locator('.schedule-warnings').innerText()).includes('撞档验证乙班'));
  const bid=(await api(a,'/admin/broadcasts','POST',{title:'虚构历史核对',starts_at:new Date(Date.now()-60000).toISOString(),deadline_at:new Date(Date.now()+3600000).toISOString(),teacher_ids:[u.id]})).id;
  await a.locator('.broadcast-strip').waitFor();await api(a,`/admin/broadcasts/${bid}/close`,'POST');await a.locator('.broadcast-strip').waitFor({state:'hidden'});
  const snapshot=await api(a,`/admin/broadcasts/${bid}/snapshot`);
  await a.getByLabel('统计范围',{exact:true}).locator(`option[value="${bid}"]`).waitFor({state:'attached'});await a.getByLabel('统计范围',{exact:true}).selectOption(String(bid));await a.locator('.broadcast-strip').waitFor();assert.equal(await a.locator('.schedule-warnings').count(),0);
  await a.getByLabel('统计范围',{exact:true}).selectOption('');await row.locator('.schedule-warnings summary').waitFor();
  const editor=t.locator('section.class-editor').filter({hasText:'撞档验证乙班'});
  await editor.getByLabel('档位',{exact:true}).selectOption('2');await editor.getByLabel('开始时间（可选）').fill('');await editor.getByLabel('结束时间（可选）').fill('');
  await editor.getByRole('button',{name:'保存班级更改'}).click();await t.getByText('可能撞档，待核对',{exact:true}).waitFor();
  await row.locator('.schedule-warnings summary').click();await row.getByText('可能撞档，待核对',{exact:true}).waitFor();
  await t.setViewportSize({width:390,height:844});assert.ok(await t.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  await editor.getByLabel('星期',{exact:true}).selectOption('4');await editor.getByRole('button',{name:'保存班级更改'}).click();await t.locator('.schedule-warnings').waitFor({state:'hidden'});await a.locator('.schedule-warnings').waitFor({state:'hidden'});
  assert.equal((await api(a,'/admin/reports/workload'))[0].weekly_lessons,2);assert.deepEqual(await api(a,`/admin/broadcasts/${bid}/snapshot`),snapshot);assert.deepEqual(errors,[]);
  console.log('PASS: teacher and admin warnings, different-period time overlap, possible same-period clash, non-blocking UI save, warning removal, unchanged workload/snapshot, no closed broadcast on live reports, historical warning isolation and mobile layout.');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
