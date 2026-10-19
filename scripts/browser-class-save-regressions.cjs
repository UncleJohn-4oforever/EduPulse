// Regression checks against the isolated test server on port 8077.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE);
const assert=require('node:assert/strict');
const fs=require('node:fs');
const base='http://127.0.0.1:8077';
(async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true});
 try{
  const admin=await browser.newContext(),teacher=await browser.newContext();
  const auth=await(await admin.request.post(base+'/api/auth/login',{data:{username:'browser-admin',password:'BrowserTestOnly2026'}})).json();
  const call=async(ctx,path,method='GET',body)=>{const a=await(await ctx.request.get(base+'/api/auth/me')).json();return ctx.request.fetch(base+'/api'+path,{method,headers:{'X-CSRF-Token':a.csrf_token},data:body})};
  const dict=await(await call(admin,'/dictionaries')).json(),campus=dict.campus[0].id,subject=dict.subject[0].id;
  const owner=await(await call(admin,'/admin/teachers','POST',{display_name:'独立排查老师',campus_id:campus})).json();
  const cred=await(await call(admin,`/admin/teachers/${owner.id}/issue-password`,'POST',{})).json();
  assert.equal((await teacher.request.post(base+'/api/auth/login',{data:{username:cred.username,password:cred.password}})).status(),200);
  const first=await(await call(teacher,'/students','POST',{display_name:'排查原有学生',grade:'高一',campus_id:campus})).json();
  const shared={weekday:6,slot_number:1,start_time:'08:00',end_time:'10:00'};
  const seed=await(await call(teacher,'/teacher/classes','POST',{display_name:'并发排查班',subject_id:subject,capacity:6,class_slot:shared,students:[{student_id:first.id,level:'A',note:'',weekly_slots:[shared]}]})).json();
  const p=await teacher.newPage();await p.setViewportSize({width:1440,height:1000});p.on('dialog',d=>d.accept());await p.goto(base);await p.getByRole('button',{name:'新增班级',exact:true}).waitFor();
  // A class-level schedule should survive even before its first student joins.
  await p.getByRole('button',{name:'新增班级',exact:true}).click();const draft=p.locator('.class-editor').filter({hasText:'待保存'});
  await draft.getByLabel('整班星期',{exact:true}).selectOption('5');await draft.getByLabel('整班档位',{exact:true}).selectOption('1');await draft.getByLabel('整班开始时间',{exact:true}).fill('08:00');await draft.getByLabel('整班结束时间',{exact:true}).fill('10:00');await draft.getByRole('button',{name:'保存班级',exact:true}).click();
  await p.waitForTimeout(500);
  const empty=(await(await call(teacher,'/teacher/classes')).json()).find(c=>!c.students.length);
  assert.ok(empty);assert.equal(empty.display_name,'周五一档');assert.equal(empty.weekly_slots.length,1);assert.deepEqual(empty.class_slot,{weekday:5,slot_number:1,start_time:'08:00',end_time:'10:00'});
  const emptyEditor=p.locator('.class-editor').filter({has:p.getByText('周五一档',{exact:true})});await emptyEditor.waitFor();
  const wrongDisplayed=await emptyEditor.locator('.class-shared-slot').innerText();assert.ok(wrongDisplayed.includes('周五'));await p.reload();await p.locator('.class-editor').filter({has:p.getByText('周五一档',{exact:true})}).getByRole('button',{name:'展开编辑',exact:true}).click();assert.equal(await p.locator('.class-editor').filter({has:p.getByText('周五一档',{exact:true})}).getByLabel('整班星期',{exact:true}).inputValue(),'5');
  await p.screenshot({path:'exports/fixed-empty-class.png',fullPage:true});
  // A concurrent edit must reject the entire class-and-student operation.
  const editor=p.locator('.class-editor').filter({has:p.getByText('并发排查班',{exact:true})});await editor.getByRole('button',{name:'展开编辑',exact:true}).click();await editor.getByRole('button',{name:'添加学生',exact:true}).click();await editor.getByLabel('学生姓名',{exact:true}).last().fill('保存失败遗留学生');
  const body={teacher_id:owner.id,display_name:'并发排查班',name_is_manual:true,subject_id:subject,capacity:6,version:seed.version,class_slot:shared,students:[{student_id:first.id,level:'A',note:'主管已修改',weekly_slots:[shared]}]};
  assert.equal((await call(admin,`/admin/classes/${seed.id}`,'PATCH',body)).status(),200);
  const rejected=p.waitForResponse(r=>r.url().endsWith(`/api/teacher/classes/${seed.id}`)&&r.request().method()==='PATCH'&&r.status()===409);
  await editor.getByRole('button',{name:'保存班级',exact:true}).click();await rejected;
  const matches=await(await call(teacher,'/students/search?q='+encodeURIComponent('保存失败遗留学生'))).json();assert.equal(matches.length,0,'Failed class save must not create a student profile');
  const second=await(await call(teacher,'/students','POST',{display_name:'多档拒绝测试学生',grade:'高一',campus_id:campus})).json();
  const legacy=await call(teacher,'/teacher/classes','POST',{display_name:'旧入口多档班',subject_id:subject,capacity:3,students:[{student_id:first.id,weekly_slots:[{weekday:5,slot_number:1}]},{student_id:second.id,weekly_slots:[{weekday:7,slot_number:3}]}]});
  assert.equal(legacy.status(),422);
  console.log('PASS: empty class schedule survives save and reload; stale UI save creates no student; mixed-period API writes rejected.');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
