/* Isolated database only; test the old-backend validation response and retry. */
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'../browser-tools/node_modules/playwright');
const assert=require('node:assert/strict');
const base=process.env.EDUPULSE_TEST_URL||'http://127.0.0.1:8068';
(async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true});
 try{
  const a=await browser.newPage(),t=await browser.newPage();for(const p of [a,t])p.on('dialog',d=>d.accept());
  async function login(p,u,pw){await p.goto(base);await p.getByLabel('登录账号',{exact:true}).fill(u);await p.getByLabel('密码',{exact:true}).fill(pw);await p.getByRole('button',{name:'进入工作台'}).click();await p.locator('.sidebar').waitFor()}
  async function api(p,path,method='GET',body){return p.evaluate(async({path,method,body})=>{const auth=await(await fetch('/api/auth/me')).json();const r=await fetch('/api'+path,{method,headers:{'Content-Type':'application/json','X-CSRF-Token':auth.csrf_token},body:body===undefined?undefined:JSON.stringify(body)});if(!r.ok)throw new Error(await r.text());return r.json()},{path,method,body})}
  await login(a,'browser-admin','BrowserTestOnly2026');const d=await api(a,'/dictionaries');const user=await api(a,'/admin/teachers','POST',{display_name:'字段兼容测试',campus_id:d.campus[0].id});const pw=await api(a,`/admin/teachers/${user.id}/issue-password`,'POST');await login(t,pw.username,pw.password);
  await t.getByRole('button',{name:'新增班级',exact:true}).click();const editor=t.locator('.class-editor').first();await editor.getByRole('button',{name:'添加学生',exact:true}).click();const name='兼容测试学生-'+Date.now();await editor.getByLabel('学生姓名',{exact:true}).fill(name);await editor.getByLabel('星期',{exact:true}).selectOption('6');await editor.getByLabel('档位',{exact:true}).selectOption('1');
  let submitted;await t.route('**/api/teacher/classes',route=>{if(route.request().method()==='POST'){submitted=route.request().postDataJSON();return route.fulfill({status:422,contentType:'application/json',body:JSON.stringify({detail:[{type:'extra_forbidden',loc:['body','name_is_manual'],msg:'Extra inputs are not permitted',input:false},{type:'missing',loc:['body','grade'],msg:'Field required'}]})})}return route.continue()});
  await editor.getByRole('button',{name:'保存班级',exact:true}).click();await t.locator('.toast').filter({hasText:'旧版服务'}).waitFor();assert.equal(await editor.getByLabel('学生姓名',{exact:true}).inputValue(),name);assert.equal(await editor.getByLabel('星期',{exact:true}).inputValue(),'6');assert.equal(submitted.name_is_manual,false);assert.ok(!('grade' in submitted));assert.ok(!(await t.locator('.toast').innerText()).includes('Extra inputs'));
  const firstIds=(await api(t,'/students/search?q='+encodeURIComponent(name))).map(s=>s.id);assert.equal(firstIds.length,1);
  await t.unroute('**/api/teacher/classes');await editor.getByRole('button',{name:'保存班级',exact:true}).click();await t.locator('.class-editor.collapsed').waitFor();const rooms=await api(t,'/teacher/classes');assert.equal(rooms.length,1);assert.equal(rooms[0].display_name,'周六一档');assert.equal(rooms[0].name_is_manual,false);assert.equal(rooms[0].students[0].student_id,firstIds[0]);assert.deepEqual((await api(t,'/students/search?q='+encodeURIComponent(name))).map(s=>s.id),firstIds);
  console.log('PASS: old-service 422 displays Chinese explanation, preserves student/form data, and retry against the updated service saves once without duplicate student creation.');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
