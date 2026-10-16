/* Only use a fresh isolated database with seed-browser-test.py. */
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'../browser-tools/node_modules/playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const base=process.env.EDUPULSE_TEST_URL||'http://127.0.0.1:8071';
(async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true});
 try{
  const a=await browser.newPage({viewport:{width:1440,height:1000},reducedMotion:'reduce'}),t=await browser.newPage(),other=await browser.newPage(),errors=[];
  for(const p of [a,t,other]){p.setDefaultTimeout(15000);p.on('pageerror',e=>errors.push(e.message));p.on('dialog',d=>d.accept())}
  async function login(p,u,pw){await p.goto(base);await p.getByLabel('登录账号',{exact:true}).fill(u);await p.getByLabel('密码',{exact:true}).fill(pw);await p.getByRole('button',{name:'进入工作台'}).click();await p.locator('.sidebar').waitFor()}
  async function api(p,path,method='GET',body){return p.evaluate(async({path,method,body})=>{const auth=await(await fetch('/api/auth/me')).json();const r=await fetch('/api'+path,{method,headers:{'Content-Type':'application/json','X-CSRF-Token':auth.csrf_token},body:body===undefined?undefined:JSON.stringify(body)});if(!r.ok)throw new Error(await r.text());return r.json()},{path,method,body})}
  await login(a,'browser-admin','BrowserTestOnly2026');const dict=await api(a,'/dictionaries');const campus=dict.campus[0].id,branch=(await api(a,'/admin/dictionaries','POST',{kind:'campus',name:'演示分校'})).id;
  for(const [p,name,site] of [[t,'演示教师甲',campus],[other,'演示教师乙',branch]]){const u=await api(a,'/admin/teachers','POST',{display_name:name,campus_id:site});const pw=await api(a,`/admin/teachers/${u.id}/issue-password`,'POST');await login(p,pw.username,pw.password)}
  const ids=[],rooms=[];let n=0;
  async function room(p,cap,count,subject,site){const students=[];for(let i=0;i<count;i++){const sid=(await api(p,'/students','POST',{display_name:`虚构学生${++n}`,grade:'高一',campus_id:site})).id;ids.push(sid);students.push({student_id:sid,level:'B',note:'',weekly_slots:[{weekday:6,slot_number:1}]})}return api(p,'/teacher/classes','POST',{display_name:`演示班${n}-${cap}-${rooms.length}`,capacity:cap,subject_id:subject,students})}
  for(const count of [1,1,1,2])rooms.push(await room(t,3,count,dict.subject[0].id,campus));
  for(const count of [2,2,2,1,1,1,1,1,1])rooms.push(await room(t,6,count,dict.subject[1].id,campus));
  await room(t,1,1,dict.subject[0].id,campus);await room(other,3,3,dict.subject[0].id,branch);await room(other,3,0,dict.subject[0].id,branch);
  await a.reload();await a.getByRole('button',{name:'教师满班率',exact:true}).click();await a.locator('.occupancy-metric.three strong').waitFor();
  async function metric(key,pct,size){const m=a.locator('.occupancy-metric.'+key);await a.waitForFunction(({key,pct})=>document.querySelector('.occupancy-metric.'+key+' strong')?.textContent===pct,{key,pct});assert.equal(await m.locator('.class-size b').innerText(),size)}
  await metric('three','44.44%','1.33');await metric('six','22.22%','1.33');await metric('combined','27.78%','1.33');
  await a.getByLabel('校区',{exact:true}).selectOption(String(campus));await metric('three','41.67%','1.25');await metric('six','22.22%','1.33');await metric('combined','25.76%','1.31');
  const teacherRow=a.locator('tbody tr').filter({hasText:'演示教师甲'}).first();assert.deepEqual(await teacherRow.locator('.class-size b').allInnerTexts(),['1.25','1.33','1.31']);
  fs.mkdirSync('docs/screenshots/occupancy',{recursive:true});await a.screenshot({path:'docs/screenshots/occupancy/occupancy-desktop.png',fullPage:true});
  for(const width of [1440,1280,1024,768,390,360]){await a.setViewportSize({width,height:900});assert.ok(await a.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`overflow ${width}`)}await a.setViewportSize({width:390,height:844});await a.screenshot({path:'docs/screenshots/occupancy/occupancy-mobile.png',fullPage:true});await a.setViewportSize({width:1440,height:1000});
  await a.getByLabel('科目',{exact:true}).selectOption(String(dict.subject[0].id));await metric('six','—','—');await metric('three','41.67%','1.25');await metric('combined','41.67%','1.25');
  const user=(await api(t,'/auth/me')).user;const bid=(await api(a,'/admin/broadcasts','POST',{title:'演示历史核对',starts_at:new Date(Date.now()-60000).toISOString(),deadline_at:new Date(Date.now()+3600000).toISOString(),teacher_ids:[user.id]})).id;await api(a,`/admin/broadcasts/${bid}/close`,'POST');const frozen=await api(a,`/admin/broadcasts/${bid}/snapshot`);
  const first=rooms[0];await api(t,`/teacher/classes/${first.id}`,'PATCH',{display_name:first.display_name,capacity:first.capacity,subject_id:first.subject_id,version:first.version,students:[...first.students.map(s=>({student_id:s.student_id,level:s.level,note:s.note,weekly_slots:s.weekly_slots.map(({weekday,slot_number,start_time,end_time})=>({weekday,slot_number,start_time,end_time}))})),{student_id:ids[1],level:'B',note:'',weekly_slots:[{weekday:6,slot_number:1}]}]});await metric('three','50.00%','1.50');
  await a.getByLabel('统计范围',{exact:true}).selectOption(String(bid));await metric('three','41.67%','1.25');assert.deepEqual(await api(a,`/admin/broadcasts/${bid}/snapshot`),frozen);
  await a.getByLabel('统计范围',{exact:true}).selectOption('');await a.getByLabel('科目',{exact:true}).selectOption('');await a.getByLabel('校区',{exact:true}).selectOption(String(branch));await metric('three','50.00%','1.50');await metric('six','—','—');await metric('combined','50.00%','1.50');
  // An existing empty class must contribute to the average denominator.
  const emptyRow=(await api(other,'/teacher/classes')).find(c=>!c.students.length);assert.ok(emptyRow);assert.deepEqual(errors,[]);
  console.log('PASS: exact example values, weighted aggregation, teacher averages, empty-class denominator, one-to-one exclusion, subject/campus filters, immutable historical snapshots and six screen widths.');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
