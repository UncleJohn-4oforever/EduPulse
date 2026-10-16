/* Run against an isolated test database only. Creates fictitious records. */
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'../browser-tools/node_modules/playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const base=process.env.EDUPULSE_TEST_URL||'http://127.0.0.1:8017';
const errors=[];
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const adminContext=await browser.newContext({viewport:{width:1440,height:1000}}), teacherContext=await browser.newContext({viewport:{width:1360,height:1100}}), secondContext=await browser.newContext();
 const admin=await adminContext.newPage(), teacher=await teacherContext.newPage(), second=await secondContext.newPage();
 for(const p of [admin,teacher,second]){p.on('dialog',d=>d.accept());p.on('pageerror',e=>errors.push(e.message));}
 const login=async(p,username,password)=>{await p.goto(base);await p.getByLabel('登录账号',{exact:true}).fill(username);await p.getByLabel('密码',{exact:true}).fill(password);await p.getByRole('button',{name:'进入工作台'}).click();await p.locator('.sidebar').waitFor()};
 const request=async(p,path,method='GET',body)=>p.evaluate(async({path,method,body})=>{const auth=await (await fetch('/api/auth/me')).json();const r=await fetch('/api'+path,{method,headers:{'Content-Type':'application/json','X-CSRF-Token':auth.csrf_token},body:body===undefined?undefined:JSON.stringify(body)});if(!r.ok)throw new Error(await r.text());return r.json()},{path,method,body});
 await login(admin,process.env.EDUPULSE_TEST_ADMIN||'browser-admin',process.env.EDUPULSE_TEST_PASSWORD||'BrowserTestOnly2026');
 await admin.getByRole('button',{name:'教师账号与密码',exact:true}).click();
 const accounts=[];
 for(const name of ['测试张老师','测试李老师']){
   await admin.getByRole('button',{name:'新增教师',exact:true}).click();await admin.getByLabel('教师姓名',{exact:true}).fill(name);await admin.getByRole('button',{name:'保存教师名单'}).click();await admin.locator('.modal').waitFor({state:'hidden'});
   await admin.locator('tr').filter({hasText:name}).getByRole('button',{name:'生成初始密码'}).click();await admin.locator('.credential code').waitFor();
   const code=await admin.locator('.credential code').innerText();accounts.push({username:code.match(/账号：(\S+)/)[1],password:code.match(/密码：(\S+)/)[1]});
   await admin.getByRole('button',{name:'关闭',exact:true}).click();await admin.locator('.modal').waitFor({state:'hidden'});
 }
 await login(teacher,accounts[0].username,accounts[0].password);
 await teacher.getByRole('button',{name:'新增班级',exact:true}).click();
 await teacher.getByLabel('班级显示名称',{exact:true}).fill('测试 · 高一数学周三三档');
 await teacher.getByLabel('科目',{exact:true}).selectOption({label:'数学'});
 await teacher.getByRole('button',{name:'添加学生 · 搜索已有 / 新建'}).click();
 await teacher.getByLabel('先搜索姓名或内部编号').fill('测试学生A');await teacher.getByRole('button',{name:'新建「测试学生A」并加入'}).click();
 await teacher.locator('.modal').waitFor({state:'hidden'});
 for(const name of ['测试学生B','测试学生C']){await teacher.getByRole('button',{name:'添加学生 · 搜索已有 / 新建'}).click();await teacher.getByLabel('先搜索姓名或内部编号').fill(name);await teacher.getByRole('button',{name:`新建「${name}」并加入`}).click();await teacher.locator('.modal').waitFor({state:'hidden'});}
 await teacher.locator('.student-card').nth(0).getByLabel('A',{exact:true}).check();
 await teacher.locator('.student-card').nth(0).getByLabel('文字评价',{exact:true}).fill('验收用虚构评价：函数基础扎实。');
 await teacher.locator('.student-card').nth(1).getByLabel('B',{exact:true}).check();await teacher.locator('.student-card').nth(2).getByLabel('C',{exact:true}).check();
 await teacher.getByRole('button',{name:'保存班级更改',exact:true}).click();await teacher.locator('.badge').filter({hasText:'已保存'}).waitFor();
 await teacher.reload();await teacher.locator('.student-card').nth(2).waitFor();assert.equal(await teacher.locator('.student-card').filter({hasText:'测试学生A'}).getByLabel('文字评价',{exact:true}).inputValue(),'验收用虚构评价：函数基础扎实。');
 const classes=await request(teacher,'/teacher/classes');assert.equal(classes.length,1);const sid=classes[0].students[0].student_id;
 await login(second,accounts[1].username,accounts[1].password);await second.getByRole('button',{name:'新增班级',exact:true}).click();await second.getByLabel('班级显示名称',{exact:true}).fill('测试 · 高一英语一对三');await second.getByLabel('科目',{exact:true}).selectOption({label:'英语'});await second.getByLabel('班型 / 容量',{exact:true}).selectOption('3');
 await second.getByRole('button',{name:'添加学生 · 搜索已有 / 新建'}).click();await second.getByLabel('先搜索姓名或内部编号').fill(String(sid));await second.locator('.search-results button').filter({hasText:'测试学生A'}).click();await second.locator('.modal').waitFor({state:'hidden'});await second.getByLabel('文字评价',{exact:true}).fill('验收用虚构评价：英语词汇需要巩固。');await second.getByRole('button',{name:'保存班级更改'}).click();await second.locator('.badge').filter({hasText:'已保存'}).waitFor();
 await admin.getByRole('button',{name:'采集广播',exact:true}).click();await admin.getByRole('button',{name:'发起核对广播',exact:true}).click();await admin.getByLabel('任务标题').fill('测试 · 本周教学数据核对');await admin.getByRole('button',{name:'创建并广播'}).click();await admin.locator('.modal').waitFor({state:'hidden'});
 await teacher.locator('.teacher-broadcast').waitFor();await second.locator('.teacher-broadcast').waitFor();
 await teacher.getByRole('button',{name:'数据无变化，确认提交',exact:true}).click();await second.getByRole('button',{name:'数据无变化，确认提交',exact:true}).click();
 await admin.locator('.broadcast-fraction strong').filter({hasText:'2 / 2'}).waitFor();
 await admin.getByRole('button',{name:'概览',exact:true}).click();await admin.locator('.stat-card').first().waitFor();
 const data=await request(admin,'/admin/reports');const z=data.teachers.find(t=>t.username===accounts[0].username);assert.equal(z.small_rate,0.5);assert.equal(z.weekly_lessons,1);const s=data.students.find(s=>s.id===sid);assert.equal(s.subject_count,2);assert.equal(s.details.length,2);
 fs.mkdirSync('docs/screenshots',{recursive:true});await admin.screenshot({path:'docs/screenshots/admin-overview.png',fullPage:true,animations:'disabled',style:'.toast {visibility:hidden}'});
 for(const [name,ext] of [['导出看板 PNG','png'],['导出明细 XLSX','xlsx']]){const promise=admin.waitForEvent('download');await admin.getByRole('button',{name,exact:true}).click();const dl=await promise;assert.equal(await dl.failure(),null);assert.ok(dl.suggestedFilename().endsWith(ext));if(ext==='png')await dl.saveAs('docs/screenshots/report-export.png');}
 await teacher.setViewportSize({width:390,height:844});await teacher.screenshot({path:'docs/screenshots/teacher-mobile.png',fullPage:true,animations:'disabled',style:'.toast {visibility:hidden}'});assert.ok(await teacher.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),'Mobile layout overflows viewport');
 await teacher.setViewportSize({width:1360,height:1100});await teacher.screenshot({path:'docs/screenshots/teacher-desktop.png',fullPage:true,animations:'disabled',style:'.toast {visibility:hidden}'});
 await teacher.getByRole('button',{name:'退出登录'}).click();await teacher.getByRole('button',{name:'进入工作台'}).waitFor();await teacher.goBack();assert.equal(await teacher.locator('.student-card').count(),0);await teacher.goto(base);await teacher.getByRole('button',{name:'进入工作台'}).waitFor();assert.equal(await teacher.locator('.student-card').count(),0);
 assert.deepEqual(errors,[]);console.log('PASS: UI credentials, two teacher forms, persistence, shared student, real-time broadcast, 2/2 confirmations, true reports, PNG/XLSX downloads, mobile layout and logout.');await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
