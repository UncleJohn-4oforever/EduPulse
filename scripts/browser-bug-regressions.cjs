/* Isolated test database only. No production data. */
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'../browser-tools/node_modules/playwright');
const assert=require('node:assert/strict');
const base=process.env.EDUPULSE_TEST_URL||'http://127.0.0.1:8040';
(async()=>{
 const browser=await chromium.launch({args:['--no-sandbox']});const errors=[];const failures=[];
 const adminContext=await browser.newContext({viewport:{width:1440,height:1000}});
 await adminContext.addInitScript(()=>Object.defineProperty(navigator,'clipboard',{value:undefined,configurable:true}));
 const admin=await adminContext.newPage();admin.setDefaultTimeout(10000);admin.on('dialog',d=>d.accept());admin.on('pageerror',e=>errors.push(e.message));
 async function login(p,username,password){await p.goto(base);await p.getByLabel('登录账号',{exact:true}).fill(username);await p.getByLabel('密码',{exact:true}).fill(password);await p.getByRole('button',{name:'进入工作台'}).click();await p.locator('.sidebar').waitFor()}
 async function request(p,path,method='GET',body){return p.evaluate(async({path,method,body})=>{const auth=await(await fetch('/api/auth/me')).json();const r=await fetch('/api'+path,{method,headers:{'Content-Type':'application/json','X-CSRF-Token':auth.csrf_token},body:body===undefined?undefined:JSON.stringify(body)});if(!r.ok)throw new Error('HTTP '+r.status);return r.json()},{path,method,body})}
 async function run(name,fn){try{await fn();console.log('PASS: '+name)}catch(e){failures.push(name+': '+e.message);console.log('FAIL: '+name+': '+e.message)}}
 await login(admin,'browser-admin','BrowserTestOnly2026');const dict=await request(admin,'/dictionaries');
 const u=await request(admin,'/admin/teachers','POST',{display_name:'表单测试教师',campus_id:dict.campus[0].id});
 const credentials=await request(admin,`/admin/teachers/${u.id}/issue-password`,'POST');
 const context=await browser.newContext({viewport:{width:1440,height:1000}});const teacher=await context.newPage();teacher.setDefaultTimeout(10000);teacher.on('dialog',d=>d.accept());teacher.on('pageerror',e=>errors.push(e.message));
 let unblockDict;let dictArrived;const dictBlocked=new Promise(r=>dictArrived=r);const dictWait=new Promise(r=>unblockDict=r);
 await teacher.route('**/api/dictionaries',async route=>{dictArrived();await dictWait;await route.continue()});
 await login(teacher,credentials.username,credentials.password);await dictBlocked;
 await run('new class waits for loaded dictionaries',async()=>{assert.equal(await teacher.getByRole('button',{name:'新增班级',exact:true}).isDisabled(),true)});
 unblockDict();await teacher.unroute('**/api/dictionaries');
 for(const name of ['第一班','第二班'])await request(teacher,'/teacher/classes','POST',{display_name:name,subject_id:dict.subject[0].id,grade:'高一',capacity:3,students:[]});
 await teacher.reload();await teacher.locator('.class-editor').nth(1).waitFor();
 let release;let reached;const arrived=new Promise(r=>reached=r);const hold=new Promise(r=>release=r);
 const classes=await request(teacher,'/teacher/classes');const first=teacher.locator('.class-editor').nth(0);
 await teacher.route('**/api/teacher/classes/'+classes[0].id,async route=>{if(route.request().method()==='PATCH'){reached();await hold}await route.continue()});
 await first.getByLabel('班级显示名称',{exact:true}).fill('保存期间测试');await first.getByRole('button',{name:'保存班级更改'}).click();await arrived;
 await run('editing controls are locked during save',async()=>{assert.equal(await first.getByLabel('班级显示名称',{exact:true}).isDisabled(),true);assert.equal(await first.getByRole('button',{name:'添加学生 · 搜索已有 / 新建'}).isDisabled(),true)});
 const saved=teacher.waitForResponse(r=>r.url().endsWith('/api/teacher/classes/'+classes[0].id)&&r.request().method()==='PATCH');release();await saved;await teacher.unroute('**/api/teacher/classes/'+classes[0].id);await teacher.reload();await teacher.locator('.class-editor').nth(1).waitFor();
 const second=teacher.locator('.class-editor').nth(1);await second.getByLabel('班级显示名称',{exact:true}).fill('不能丢失的本地草稿');
 const fresh=await request(teacher,'/teacher/classes');const remote=fresh[1];
 await request(teacher,`/teacher/classes/${remote.id}`,'PATCH',{display_name:'另一个窗口的修改',subject_id:remote.subject_id,grade:remote.grade,capacity:remote.capacity,students:[],version:remote.version});
 await first.getByLabel('班级显示名称',{exact:true}).fill('保存另一个班');
 const reloaded=teacher.waitForResponse(r=>r.url().endsWith('/api/teacher/classes')&&r.request().method()==='GET');await first.getByRole('button',{name:'保存班级更改'}).click();await reloaded;
 await run('saving another class preserves a dirty editor across remote updates',async()=>{assert.equal(await second.getByLabel('班级显示名称',{exact:true}).inputValue(),'不能丢失的本地草稿')});
 await run('stale draft conflicts without overwriting remote data',async()=>{assert.equal(await second.getByRole('button',{name:'保存班级更改'}).isDisabled(),false);const reply=teacher.waitForResponse(r=>r.url().endsWith(`/api/teacher/classes/${remote.id}`)&&r.request().method()==='PATCH');await second.getByRole('button',{name:'保存班级更改'}).click();assert.equal((await reply).status(),409);assert.equal(await second.getByLabel('班级显示名称',{exact:true}).inputValue(),'不能丢失的本地草稿')});
 await request(admin,'/admin/teachers','POST',{display_name:'剪贴板测试教师',campus_id:dict.campus[0].id});await admin.getByRole('button',{name:'教师账号与密码',exact:true}).click();await admin.locator('tr').filter({hasText:'剪贴板测试教师'}).getByRole('button',{name:'生成初始密码'}).click();await admin.locator('.credential').waitFor();
 await run('HTTP clipboard unavailable has a safe manual-copy fallback',async()=>{await admin.getByRole('button',{name:'复制',exact:true}).click();await admin.locator('.toast').filter({hasText:'请选中文字手动复制'}).waitFor();assert.deepEqual(errors,[])});
 await admin.getByRole('button',{name:'关闭',exact:true}).click();
 await run('teacher identity refreshes after administrator rename',async()=>{await request(admin,`/admin/teachers/${u.id}`,'PATCH',{display_name:'更新的教师姓名',campus_id:dict.campus[0].id,enabled:true});await teacher.getByRole('heading',{level:1,name:'更新的教师姓名，我的班级',exact:true}).waitFor()});
 await run('student-only filters do not silently carry into teacher reports',async()=>{
   await admin.getByRole('button',{name:'学生列表',exact:true}).click();await admin.getByLabel('年级',{exact:true}).selectOption('高一');await admin.getByLabel('教师',{exact:true}).selectOption(String(u.id));await admin.getByLabel('搜索',{exact:true}).fill('测试搜索');
   const response=admin.waitForResponse(r=>{const url=new URL(r.url());return url.pathname==='/api/admin/reports'&&url.searchParams.get('search_type')==='teacher'&&!url.searchParams.has('q')&&!url.searchParams.has('teacher_id')&&!url.searchParams.has('grade')});
   await admin.getByRole('button',{name:'概览',exact:true}).click();await response;assert.equal(await admin.getByLabel('搜索',{exact:true}).inputValue(),'');
 });
 await browser.close();if(failures.length){console.error(failures.join('\n'));process.exitCode=1}else console.log('PASS: all browser bug regressions, no uncaught page errors.');
})().catch(e=>{console.error(e);process.exit(1)});
