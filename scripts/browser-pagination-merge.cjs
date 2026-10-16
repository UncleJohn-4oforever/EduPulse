/* Requires a fresh isolated database seeded with seed-browser-test.py. */
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'../browser-tools/node_modules/playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const base=process.env.EDUPULSE_TEST_URL||'http://127.0.0.1:8074';
(async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true});
 try{
  const a=await browser.newPage({viewport:{width:1440,height:1000}}),t=await browser.newPage(),errors=[];
  for(const p of [a,t]){p.on('pageerror',e=>errors.push(e.message));p.on('dialog',d=>d.accept())}
  async function login(p,u,pw){await p.goto(base);await p.getByLabel('登录账号',{exact:true}).fill(u);await p.getByLabel('密码',{exact:true}).fill(pw);await p.getByRole('button',{name:'进入工作台'}).click();await p.locator('.sidebar').waitFor()}
  async function api(p,path,method='GET',body){return p.evaluate(async({path,method,body})=>{const auth=await(await fetch('/api/auth/me')).json();const r=await fetch('/api'+path,{method,headers:{'Content-Type':'application/json','X-CSRF-Token':auth.csrf_token},body:body===undefined?undefined:JSON.stringify(body)});if(!r.ok)throw new Error(await r.text());return r.json()},{path,method,body})}
  await login(a,'browser-admin','BrowserTestOnly2026');const dict=await api(a,'/dictionaries'),campus=dict.campus[0].id;
  const teachers=await api(a,'/admin/teachers/import','POST',{teachers:Array.from({length:25},(_,i)=>({display_name:`分页演示教师${String(i).padStart(2,'0')}`,campus_id:campus}))});
  const u=teachers[0],pw=await api(a,`/admin/teachers/${u.id}/issue-password`,'POST');await login(t,pw.username,pw.password);
  const students=[];for(let i=0;i<25;i++)students.push(await api(t,'/students','POST',{display_name:i<3?'重名演示学生':i<5?'同班重名演示':`分页演示学生${i}`,grade:'高一',campus_id:campus}));
  async function room(subject,ids){return api(t,'/teacher/classes','POST',{display_name:'合并演示班',capacity:3,subject_id:subject,students:ids.map(id=>({student_id:id,level:'A',note:`保留评价${id}`,weekly_slots:[{weekday:6,slot_number:1,start_time:'08:00',end_time:'10:00'}]}))})}
  await room(dict.subject[0].id,[students[0].id]);await room(dict.subject[1].id,[students[1].id]);await room(dict.subject[0].id,[students[3].id,students[4].id]);
  const b=await api(a,'/admin/broadcasts','POST',{title:'合并前历史快照',starts_at:new Date(Date.now()-60000).toISOString(),deadline_at:new Date(Date.now()+3600000).toISOString(),teacher_ids:[u.id]});await api(a,`/admin/broadcasts/${b.id}/close`,'POST');const snapshot=await api(a,`/admin/broadcasts/${b.id}/snapshot`);
  await a.reload();
  for(const page of ['概览','教师满班率','教师负荷']){await a.getByRole('button',{name:page,exact:true}).click();await a.getByLabel('每页显示条数').selectOption('10');assert.equal(await a.locator('tbody>tr:not(.class-expander)').count(),10);await a.getByRole('button',{name:'下一页',exact:true}).click();assert.equal(await a.locator('tbody>tr:not(.class-expander)').count(),10);await a.getByLabel('每页显示条数').selectOption('50');assert.equal(await a.locator('tbody>tr:not(.class-expander)').count(),25)}
  await a.getByRole('button',{name:'教师账号与密码',exact:true}).click();assert.equal(await a.getByLabel('每页显示条数').inputValue(),'50');await a.waitForFunction(()=>document.querySelectorAll('tbody>tr').length===25);await a.getByLabel('每页显示条数').selectOption('10');await a.getByRole('button',{name:'下一页',exact:true}).click();await a.getByPlaceholder('搜索姓名 / 登录账号').fill('分页演示教师00');await a.waitForFunction(()=>document.querySelectorAll('tbody>tr').length===1);
  await a.getByRole('button',{name:'学生列表',exact:true}).click();await a.locator('.duplicate-students details>summary').click();await a.getByLabel('每页显示条数').selectOption('10');assert.equal(await a.locator('.student-detail').count(),10);await a.getByRole('button',{name:'下一页',exact:true}).click();assert.equal(await a.locator('.student-detail').count(),10);await a.getByLabel('每页显示条数').selectOption('100');assert.equal(await a.locator('.student-detail').count(),25);
  assert.equal(await a.locator('.duplicate-group').count(),2);
  // Duplicate detection includes unassigned records and is independent of filters.
  await a.getByLabel('搜索',{exact:true}).fill('分页演示学生24');await a.waitForFunction(()=>document.querySelectorAll('.student-detail').length===1);assert.equal(await a.locator('.duplicate-group').count(),2);
  const group=a.locator('.duplicate-group').filter({hasText:'重名演示学生'});await group.getByRole('button',{name:'核对并合并',exact:true}).click();const dialog=a.getByRole('dialog');assert.match(await dialog.innerText(),/保留编号/);await dialog.getByLabel('待合并编号').selectOption(String(students[1].id));await dialog.getByLabel('保留编号').selectOption(String(students[0].id));await dialog.getByRole('button',{name:'确认身份一致并合并'}).click();await dialog.waitFor({state:'hidden'});
  const report=await api(a,'/admin/reports?search_type=student');assert.equal(report.students.length,24);const merged=report.students.find(s=>s.id===students[0].id);assert.equal(merged.details.length,2);assert.ok(merged.details.some(d=>d.note===`保留评价${students[1].id}`));assert.ok(merged.details.every(d=>d.weekly_slots[0].start_time==='08:00'));assert.deepEqual(await api(a,`/admin/broadcasts/${b.id}/snapshot`),snapshot);assert.ok((await api(a,'/admin/audit')).some(x=>x.action==='student.merge'));
  await a.locator('.duplicate-group').filter({hasText:'同班重名演示'}).getByRole('button',{name:'核对并合并',exact:true}).click();assert.equal(await dialog.getByRole('button',{name:'确认身份一致并合并'}).isDisabled(),true);assert.match(await dialog.innerText(),/人工处理重复关联/);await dialog.getByRole('button',{name:'关闭',exact:true}).click();
  const denied=await t.evaluate(async({source_id,target_id})=>{const auth=await(await fetch('/api/auth/me')).json();return(await fetch('/api/admin/students/merge',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':auth.csrf_token},body:JSON.stringify({source_id,target_id})})).status},{source_id:students[2].id,target_id:students[0].id});assert.equal(denied,403);
  await a.getByLabel('搜索',{exact:true}).fill('');await a.waitForFunction(()=>document.querySelectorAll('.student-detail').length===24);
  fs.mkdirSync('docs/screenshots/pagination-merge',{recursive:true});await a.screenshot({path:'docs/screenshots/pagination-merge/students-desktop.png',fullPage:true});
  for(const width of [1440,1024,768,390,360]){await a.setViewportSize({width,height:900});assert.ok(await a.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`overflow ${width}`)}await a.screenshot({path:'docs/screenshots/pagination-merge/students-mobile.png',fullPage:true});
  await a.setViewportSize({width:1440,height:1000});await a.reload();await a.getByRole('button',{name:'学生列表',exact:true}).click();assert.equal(await a.getByLabel('每页显示条数').inputValue(),'100');
  await a.getByLabel('统计范围',{exact:true}).selectOption(String(b.id));await a.waitForFunction(()=>document.querySelectorAll('.student-detail').length===25);assert.equal(await a.locator('.duplicate-students').count(),0);
  await a.getByRole('button',{name:'采集广播',exact:true}).click();await a.getByLabel('每页显示条数').waitFor();await a.getByRole('button',{name:'设置',exact:true}).click();await a.getByLabel('每页显示条数').waitFor();
  assert.deepEqual(errors,[]);console.log('PASS: page sizes, navigation/reset/persistence across all admin lists, global duplicate alerts, three-record merge, identity/evaluation/slot preservation, same-class blocking, teacher authorization, immutable history and responsive layout.');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
