/* Run only against an isolated database created by seed-browser-test.py. */
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'../browser-tools/node_modules/playwright');
const assert=require('node:assert/strict');
const base=process.env.EDUPULSE_TEST_URL||'http://127.0.0.1:18765';
(async()=>{
 const browser=await chromium.launch(process.env.PLAYWRIGHT_EXECUTABLE?{executablePath:process.env.PLAYWRIGHT_EXECUTABLE,headless:true,args:['--no-sandbox']}:{channel:'chrome',headless:true});
 try{
  const p=await browser.newPage({viewport:{width:1366,height:900}}),errors=[];
  p.on('pageerror',e=>errors.push(e.message));
  async function login(page,username,password){await page.goto(base);await page.getByLabel('登录账号',{exact:true}).fill(username);await page.getByLabel('密码',{exact:true}).fill(password);await page.getByRole('button',{name:'进入工作台'}).click();await page.locator('.sidebar').waitFor()}
  async function theme(value){await p.waitForFunction(value=>document.documentElement.dataset.adminTheme===value,value)}
  async function api(path,method='GET',data){const auth=await(await p.request.get(base+'/api/auth/me')).json();const r=await p.request.fetch(base+'/api'+path,{method,headers:{'x-csrf-token':auth.csrf_token},data});assert.ok(r.ok(),await r.text());return r.json()}
  await login(p,'browser-admin','BrowserTestOnly2026');await theme('warcraft');
  const summaries={};
  for(const value of ['warcraft','classic']){
   await p.getByRole('button',{name:'设置',exact:true}).click();
   await p.getByRole('radio',{name:new RegExp(value==='warcraft'?'魔兽':'经典')}).check();await theme(value);
   assert.equal(await p.evaluate(()=>localStorage.getItem('edupulse-admin-theme')||'warcraft'),value);
   for(const name of ['概览','教师满班率','教师周课量','学生列表','数据冻结与对比','采集广播','教师账号与密码','设置']){
    await p.getByRole('button',{name,exact:true}).click();await theme(value);
    if(['概览','教师满班率','教师周课量'].includes(name)){
     await p.locator('.report-summary').waitFor();assert.equal(await p.locator('.occupancy-metric').count(),3);assert.equal(await p.locator('.stat-card').count(),4);
     const text=await p.locator('.report-summary').innerText();
     if(value==='warcraft')summaries[name]=text;else assert.equal(text,summaries[name]);
    }
    if(name==='教师满班率'){
     const search=await p.getByLabel('搜索',{exact:true}).boundingBox(),exportButton=await p.getByRole('button',{name:'导出明细 XLSX'}).boundingBox();assert.ok(Math.abs(search.y-exportButton.y)<3);
     const download=p.waitForEvent('download');await p.getByRole('button',{name:'导出明细 XLSX'}).click();assert.equal(await(await download).failure(),null);
    }
    if(name==='教师账号与密码'){
     await p.getByRole('button',{name:'新增教师',exact:true}).click();await p.getByRole('dialog',{name:'新增教师'}).waitFor();
     assert.equal(await p.getByRole('dialog').locator('input').first().isVisible(),true);await p.getByRole('dialog').getByRole('button',{name:'关闭',exact:true}).click();
    }
    if(value==='warcraft'){
     const unreadable=await p.locator('td,.pager,.class-expander summary,.workload-value span').evaluateAll(nodes=>nodes.filter(el=>{
      if(!el.getClientRects().length||!el.textContent.trim())return false;
      const rgb=getComputedStyle(el).color.match(/[\d.]+/g).slice(0,3).map(Number).map(n=>{n/=255;return n<=.04045?n/12.92:((n+.055)/1.055)**2.4});
      const luminance=.2126*rgb[0]+.7152*rgb[1]+.0722*rgb[2];
      return (luminance+.05)/(.022+.05)<4.5;
     }).map(el=>el.textContent.trim().slice(0,50)));
     assert.deepEqual(unreadable,[],`${name}: dark text contrast`);
    }
    assert.equal(await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,`${value}/${name} overflow`);
   }
   await p.reload();await theme(value);await p.getByRole('button',{name:'设置',exact:true}).click();assert.equal(await p.getByRole('radio',{name:new RegExp(value==='warcraft'?'魔兽':'经典')}).isChecked(),true);
  }
  await p.getByRole('radio',{name:/魔兽/}).check();await theme('warcraft');
  if(process.env.EDUPULSE_THEME_SCREENSHOTS){await p.screenshot({path:'/tmp/edupulse-epic-settings.png',fullPage:true});await p.getByRole('button',{name:'教师满班率',exact:true}).click();await p.locator('.report-summary').waitFor();await p.screenshot({path:'/tmp/edupulse-epic-dashboard.png',fullPage:true})}
  for(const width of [1024,768,390]){await p.setViewportSize({width,height:900});if(width<=850)await p.locator('.mobile-toggle').click();await p.getByRole('button',{name:'设置',exact:true}).click();assert.equal(await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,`mobile ${width}`)}
  // Shared browsers must not apply the supervisor's palette to teacher sessions.
  const dict=await api('/dictionaries'),u=await api('/admin/teachers','POST',{display_name:'主题隔离测试教师',campus_id:dict.campus[0].id});
  const credentials=await api(`/admin/teachers/${u.id}/issue-password`,'POST');
  await p.setViewportSize({width:1366,height:900});await p.getByTitle('退出登录',{exact:true}).click();await p.getByLabel('登录账号',{exact:true}).waitFor();await theme('classic');
  await login(p,credentials.username,credentials.password);await theme('classic');assert.equal(await p.locator('.teacher-app').count(),1);
  await p.getByTitle('退出登录',{exact:true}).click();await login(p,'browser-admin','BrowserTestOnly2026');await theme('warcraft');
  assert.deepEqual(errors,[]);console.log('PASS: both themes on all eight admin pages; identical statistics; XLSX exports; dialog; saved selection on reload/login; teacher/login isolation; responsive widths; no browser errors.');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
