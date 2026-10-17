/* Run only against a fresh isolated database seeded by seed-browser-test.py. */
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'../browser-tools/node_modules/playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const base=process.env.EDUPULSE_TEST_URL||'http://127.0.0.1:8073';
(async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true});
 try {
  const admin=await browser.newPage({viewport:{width:1440,height:1000}}),teacher=await browser.newPage(),errors=[];
  for(const p of [admin,teacher])p.on('pageerror',e=>errors.push(e.message));
  async function login(p,u,pw){await p.goto(base);await p.getByLabel('登录账号',{exact:true}).fill(u);await p.getByLabel('密码',{exact:true}).fill(pw);await p.getByRole('button',{name:'进入工作台'}).click();await p.locator('.sidebar').waitFor()}
  async function api(p,path,method='GET',body){return p.evaluate(async({path,method,body})=>{const auth=await(await fetch('/api/auth/me')).json();const r=await fetch('/api'+path,{method,headers:{'Content-Type':'application/json','X-CSRF-Token':auth.csrf_token},body:body===undefined?undefined:JSON.stringify(body)});if(!r.ok)throw new Error(await r.text());return r.json()},{path,method,body})}
  await login(admin,'browser-admin','BrowserTestOnly2026');
  const dict=await api(admin,'/dictionaries'),campus=dict.campus[0].id,subject=dict.subject[0].id;
  const u=await api(admin,'/admin/teachers','POST',{display_name:'负荷演示教师',campus_id:campus});
  const pw=await api(admin,`/admin/teachers/${u.id}/issue-password`,'POST');await login(teacher,pw.username,pw.password);
  await admin.getByRole('button',{name:'教师周课量',exact:true}).click();
  async function check(n,pct){await admin.waitForFunction(({n,pct})=>{const el=document.querySelector('.workload-value');return el?.querySelector('strong')?.textContent===`${n}/15`&&el?.querySelector('span')?.textContent===pct},{n,pct})}
  async function refresh(n,pct){await admin.reload();await admin.getByRole('button',{name:'教师周课量',exact:true}).click();await check(n,pct)}
  await check(0,'0.00%');
  let serial=0;
  async function room(cap,count,memberCount=1){const students=[];for(let i=0;i<memberCount;i++){const s=await api(teacher,'/students','POST',{display_name:`负荷虚构学生${++serial}`,grade:'高一',campus_id:campus});students.push({student_id:s.id,level:'B',note:'',weekly_slots:Array.from({length:count},(_,j)=>({weekday:Math.floor(j/6)+1,slot_number:j%6+1}))})}return api(teacher,'/teacher/classes','POST',{display_name:`负荷演示班${serial}`,subject_id:subject,capacity:cap,students})}
  // Two students in the same class/slots count as two lessons, not four.
  await room(1,3);await room(3,2,2);await room(6,2);await refresh(7,'46.67%');
  const cells=await admin.locator('tbody tr').first().locator('td').allInnerTexts();assert.deepEqual(cells.slice(1,4),['3','2','2']);
  const broadcast=await api(admin,'/admin/broadcasts','POST',{title:'负荷历史演示',starts_at:new Date(Date.now()-60000).toISOString(),deadline_at:new Date(Date.now()+3600000).toISOString(),teacher_ids:[u.id]});
  await api(admin,`/admin/broadcasts/${broadcast.id}/close`,'POST');
  await room(6,8);await refresh(15,'100.00%');
  await room(3,3);await refresh(18,'120.00%');
  await admin.getByLabel('科目',{exact:true}).selectOption(String(subject));await check(18,'120.00%');
  await admin.getByLabel('校区',{exact:true}).selectOption(String(campus));await check(18,'120.00%');
  await admin.getByLabel('统计范围',{exact:true}).selectOption(String(broadcast.id));await check(7,'46.67%');
  await admin.getByLabel('统计范围',{exact:true}).selectOption('');await check(18,'120.00%');
  fs.mkdirSync('docs/screenshots/workload',{recursive:true});
  await admin.screenshot({path:'docs/screenshots/workload/workload-desktop.png',fullPage:true});
  for(const width of [1440,1280,1024,768,390,360]){await admin.setViewportSize({width,height:900});assert.ok(await admin.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`overflow at ${width}`);await check(18,'120.00%')}
  await admin.screenshot({path:'docs/screenshots/workload/workload-mobile.png',fullPage:true});
  assert.deepEqual(errors,[]);
  console.log('PASS: 0/7/15/18 lessons, uncapped rates, all class types, within-class deduplication, campus/subject filters, historical snapshot and six viewport widths.');
 } finally {await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
